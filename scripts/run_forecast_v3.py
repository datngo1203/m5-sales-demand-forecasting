"""Fresh-store RF-only validation and one guarded final test under the frozen V3 procedure."""
import argparse
from datetime import date, timedelta, datetime, timezone
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("OMP_NUM_THREADS","2")
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"code"))
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import forecast_v3 as v3
import v2_panel
from run_forecast_v2 import dump, read, fingerprint, spark_session

OUTPUT=ROOT/"outputs/forecast_v3"


def verify():
    frozen=read(OUTPUT/"frozen.json")
    for key in ("procedure_hashes","validation_hashes"):
        if fingerprint([ROOT/p for p in frozen[key]])!=frozen[key]:
            raise ValueError("Frozen V3 procedure/development evidence changed")
    return frozen


def rf_fit(values,dates,origin,seed):
    end=dates.index(origin)+1
    x,y=v3.v2.v1.training_data(values[:,:end],dates[:end],end,window_days=v3.v2.WINDOW)
    return RandomForestRegressor(random_state=seed,**v3.v2.CONFIG["rf"]).fit(x,y)


def predict(rf,values,dates,origin):
    end=dates.index(origin)+1
    days=[origin+timedelta(days=h) for h in range(1,29)]
    known=values[:,:end]
    x,_=v3.v2.historical_features(known,dates[:end],origin,days)
    return {"random_forest":v3.v2.v1.recursive_predict(rf,known,days,dates[0]),
            "weekday_mean4":x[:,0].reshape(len(values),28),
            "seasonal_naive":v3.v2.v1.recursive_predict(None,known,days,dates[0])}


def prepare():
    frozen=verify()
    source=Path(read(ROOT/"outputs/forecast_v2/prepared.json")["source"])
    spark=spark_session()
    try:
        for store in frozen["stores"]:
            panels=v2_panel.load_panels(spark,str(source),store)
            for panel,selected in panels.items():
                path=OUTPUT/store/panel
                path.mkdir(parents=True,exist_ok=True)
                if (path/"prepared_complete.json").exists():
                    print(f"reuse completed {store}/{panel}",flush=True)
                    continue
                if (path/"history_validation.npz").exists():
                    with np.load(path/"history_validation.npz",allow_pickle=False) as data:
                        values=data["values"]
                        dates=[date.fromisoformat(d) for d in data["dates"].tolist()]
                else:
                    dates,values=v2_panel.load_values(spark,str(source),store,selected,v3.v2.TEST_ORIGIN)
                    np.savez_compressed(path/"history_validation.npz",values=values,dates=np.array(list(map(str,dates))))
                    dump(path/"panel.json",{"store":store,"panel":panel,"selected":selected})
                if not (path/"validation_predictions.npz").exists():
                    actual,known=[],[]
                    forecasts={name:[] for name in ("random_forest","weekday_mean4","seasonal_naive")}
                    for fold,origin in enumerate(v3.v2.origins()):
                        end=dates.index(origin)+1
                        actual.append(values[:,end:end+28])
                        known.append(values[:,end-28:end])
                        preds={name:[] for name in forecasts}
                        for seed in v3.v2.SEEDS:
                            rf=rf_fit(values,dates,origin,seed)
                            for name,pred in predict(rf,values,dates,origin).items():
                                preds[name].append(pred)
                        for name in forecasts:
                            forecasts[name].append(preds[name])
                        print(f"validation {store}/{panel} {fold+1}/13",flush=True)
                    np.savez_compressed(path/"validation_predictions.npz",actual=actual,known=known,
                                        **{k:np.asarray(v) for k,v in forecasts.items()})
                with np.load(path/"validation_predictions.npz",allow_pickle=False) as data:
                    ks,_,rows,summary=v3.validation(data)
                dump(path/"validation_summary.json",{"k_by_seed":ks,"summary":summary})
                v3.v2.v1.write_csv(path/"validation_metrics.csv",rows)
                if not (path/"test_forecasts.npz").exists():
                    forecasts={name:[] for name in ("random_forest","weekday_mean4","seasonal_naive")}
                    for seed in v3.v2.SEEDS:
                        model_path=path/f"rf_{seed}.joblib"
                        if model_path.exists():
                            rf=v3.v2.v1.joblib.load(model_path)
                        else:
                            rf=rf_fit(values,dates,v3.v2.TEST_ORIGIN,seed)
                            v3.v2.v1.joblib.dump(rf,model_path)
                        for name,pred in predict(rf,values,dates,v3.v2.TEST_ORIGIN).items():
                            forecasts[name].append(pred)
                    candidates=v3.candidates(np.asarray(forecasts["random_forest"]),
                        np.asarray(forecasts["weekday_mean4"]),ks)
                    candidates["seasonal_naive"]=np.asarray(forecasts["seasonal_naive"])
                    np.savez_compressed(path/"test_forecasts.npz",**candidates)
                dump(path/"prepared_complete.json",{"procedure_sha256":fingerprint([OUTPUT/"frozen.json"]),
                    "files":fingerprint([path/f for f in ("panel.json","history_validation.npz",
                        "validation_predictions.npz","validation_summary.json","test_forecasts.npz")])})
        dump(OUTPUT/"prepared.json",{"stores":frozen["stores"],"source_sha256":
             read(ROOT/"outputs/forecast_v2/prepared.json")["source_sha256"]})
    finally:
        spark.stop()


def test():
    frozen=verify()
    for store in frozen["stores"]:
        for panel in frozen["panels"]:
            proof=read(OUTPUT/store/panel/"prepared_complete.json")
            assert proof["procedure_sha256"]==fingerprint([OUTPUT/"frozen.json"])
            assert proof["files"]==fingerprint([ROOT/p for p in proof["files"]])
    with (OUTPUT/"test_started.json").open("x",encoding="utf-8") as stream:
        json.dump({"started_at_utc":datetime.now(timezone.utc).isoformat(),
                   "frozen_sha256":fingerprint([OUTPUT/"frozen.json"])},stream,indent=2)
    source=Path(read(ROOT/"outputs/forecast_v2/prepared.json")["source"])
    assert fingerprint(sorted(source.glob("*.parquet")))==read(OUTPUT/"prepared.json")["source_sha256"]
    spark=spark_session()
    all_rows=[]
    seeds=[]
    bias=[]
    try:
        for store in frozen["stores"]:
            for panel in frozen["panels"]:
                path=OUTPUT/store/panel
                selected=read(path/"panel.json")["selected"]
                _,values=v2_panel.load_values(spark,str(source),store,selected,v3.v2.TEST_ORIGIN+timedelta(days=28))
                with np.load(path/"history_validation.npz",allow_pickle=False) as old:
                    assert np.array_equal(old["values"],values[:,:-28])
                actual,known=values[:,-28:],values[:,-56:-28]
                forecasts=np.load(path/"test_forecasts.npz",allow_pickle=False)
                models=list(dict.fromkeys((frozen["choice"],"random_forest","weekday_mean4","seasonal_naive")))
                for model in models:
                    rows=[]
                    for s,seed in enumerate(v3.v2.SEEDS):
                        pred=forecasts[model][s]
                        metric=v3.v2.metrics(actual,pred,known,forecasts["seasonal_naive"][s])
                        rows.append(metric)
                        seeds.append({"store":store,"panel":panel,"seed":seed,"model":model,**metric})
                        for h in range(28):
                            b=float(np.sum(pred[:,h]-actual[:,h]))
                            sn=float(np.sum(forecasts["seasonal_naive"][s,:,h]-actual[:,h]))
                            bias.append({"store":store,"panel":panel,"seed":seed,"model":model,"horizon":h+1,
                                         "bias_units":b,"B_SN":sn,"delta_bias":b-sn})
                    all_rows.append({"store":store,"panel":panel,"model":model,
                        **{k:float(np.mean([r[k] for r in rows])) if rows[0][k] is not None else None for k in rows[0]}})
                np.savez_compressed(path/"test_actual.npz",actual=actual,known=known)
                forecasts.close()
    finally:
        spark.stop()
    v3.v2.v1.write_csv(OUTPUT/"test_metrics.csv",all_rows)
    v3.v2.v1.write_csv(OUTPUT/"test_seed_metrics.csv",seeds)
    v3.v2.v1.write_csv(OUTPUT/"test_bias_by_h.csv",bias)
    decision=v3.integration_gate(all_rows,frozen["choice"],frozen["stores"])
    dump(OUTPUT/"integration.json",decision)
    dump(OUTPUT/"test_complete.json",{"completed_at_utc":datetime.now(timezone.utc).isoformat(),
        "frozen_sha256":fingerprint([OUTPUT/"frozen.json"]),"integration":decision})
    print(json.dumps(decision,indent=2),flush=True)


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("prepare","test"))
    args=parser.parse_args()
    {"prepare":prepare,"test":test}[args.stage]()
