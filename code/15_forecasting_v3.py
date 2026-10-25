"""V2 pipeline with the V3-frozen candidate; reuse predictions before considering any fit."""
import argparse
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"code"),str(ROOT/"scripts")]
import numpy as np
import forecast_v3 as v3
import v2_panel
from run_forecast_v2 import read,dump,fingerprint,spark_session
from run_forecast_v3 import rf_fit,predict


def cached_bundle(source,store,panel):
    registry_path=ROOT/"outputs/forecast_v2/prepared.json"
    if not registry_path.exists():
        return None
    registry=read(registry_path)
    if Path(source).resolve()!=Path(registry["source"]).resolve():
        return None
    path=ROOT/"outputs"/("forecast_v2" if store in ("CA_1","CA_2") else "forecast_v3")/store/panel
    test_file=path/("test_predictions.npz" if store in ("CA_1","CA_2") else "test_forecasts.npz")
    if not test_file.exists():
        return None
    if fingerprint(sorted(Path(source).glob("*.parquet")))!=registry["source_sha256"]:
        raise ValueError("Source changed; cannot replay cached forecasts")
    with np.load(path/"history_validation.npz",allow_pickle=False) as data:
        history=data["values"]
        dates=[date.fromisoformat(d) for d in data["dates"].tolist()]
    with np.load(path/"validation_predictions.npz",allow_pickle=False) as data:
        validation={k:data[k] for k in ("actual","known","random_forest","weekday_mean4","seasonal_naive")}
    with np.load(test_file,allow_pickle=False) as data:
        test={k:data[k] for k in ("random_forest","weekday_mean4","seasonal_naive")}
        if "actual" in data.files:
            actual=data["actual"]
        else:
            with np.load(path/"test_actual.npz",allow_pickle=False) as labels:
                actual=labels["actual"]
    return {"selected":read(path/"panel.json")["selected"],"dates":dates,
            "history":history,"validation":validation,"test":test,"actual":actual,"reused":True}


def obtain_bundle(source,store,panel,cache):
    source=Path(source).resolve()
    existing=cached_bundle(source,store,panel)
    if existing is not None:
        return existing
    # A genuinely new store estimates k from its own validation under the same fixed procedure.
    path=cache/store/panel
    source_hash=fingerprint(sorted(Path(source).glob("*.parquet")))
    if (path/"complete.json").exists():
        meta=read(path/"complete.json")
        if meta["source_sha256"]!=source_hash:
            raise ValueError("Pipeline cache source changed; use a new cache directory")
        if meta["procedure_config"]!=v3.v2.CONFIG:
            raise ValueError("Pipeline cache configuration changed; use a new cache directory")
        with np.load(path/"bundle.npz",allow_pickle=False) as data:
            result={"selected":meta["selected"],"dates":[date.fromisoformat(d) for d in data["dates"].tolist()],
                    "history":data["history"],"actual":data["actual"],"reused":True,
                    "validation":{k:data["val_"+k] for k in ("actual","known","random_forest","weekday_mean4","seasonal_naive")},
                    "test":{k:data["test_"+k] for k in ("random_forest","weekday_mean4","seasonal_naive")}}
        return result
    spark=spark_session()
    try:
        selected=v2_panel.load_panels(spark,str(source),store)[panel]
        dates,history=v2_panel.load_values(spark,str(source),store,selected,v3.v2.TEST_ORIGIN)
        val={k:[] for k in ("actual","known","random_forest","weekday_mean4","seasonal_naive")}
        for origin in v3.v2.origins():
            end=dates.index(origin)+1
            val["actual"].append(history[:,end:end+28]); val["known"].append(history[:,end-28:end])
            preds={k:[] for k in ("random_forest","weekday_mean4","seasonal_naive")}
            for seed in v3.v2.SEEDS:
                for name,pred in predict(rf_fit(history,dates,origin,seed),history,dates,origin).items():
                    preds[name].append(pred)
            for name in preds: val[name].append(preds[name])
        val={k:np.asarray(x) for k,x in val.items()}
        # Complete calibration before opening test labels, even when the frozen blend does not use k.
        v3.estimate_k(val["actual"],val["random_forest"])
        test={k:[] for k in ("random_forest","weekday_mean4","seasonal_naive")}
        for seed in v3.v2.SEEDS:
            for name,pred in predict(rf_fit(history,dates,v3.v2.TEST_ORIGIN,seed),history,dates,v3.v2.TEST_ORIGIN).items():
                test[name].append(pred)
        test={k:np.asarray(x) for k,x in test.items()}
        _,full=v2_panel.load_values(spark,str(source),store,selected,v3.v2.TEST_ORIGIN+timedelta(days=28))
        assert np.array_equal(full[:,:-28],history)
        actual=full[:,-28:]
        path.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(path/"bundle.npz",history=history,actual=actual,dates=np.array(list(map(str,dates))),
                            **{"val_"+k:x for k,x in val.items()},**{"test_"+k:x for k,x in test.items()})
        dump(path/"complete.json",{"selected":selected,"source_sha256":source_hash,"procedure_config":v3.v2.CONFIG})
        return {"selected":selected,"dates":dates,"history":history,"validation":val,"test":test,
                "actual":actual,"reused":False}
    finally:
        spark.stop()


def export(bundle,source,output,store,choice):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    (output/"forecast_report.json").unlink(missing_ok=True)
    data=bundle["validation"]
    ks=v3.estimate_k(data["actual"],data["random_forest"])
    val=v3.candidates(data["random_forest"],data["weekday_mean4"],ks)
    test=v3.candidates(bundle["test"]["random_forest"],bundle["test"]["weekday_mean4"],ks)
    val["seasonal_naive"]=data["seasonal_naive"]; test["seasonal_naive"]=bundle["test"]["seasonal_naive"]
    val["selected_forecast"]=val[choice]; test["selected_forecast"]=test[choice]
    selected=bundle["selected"]
    dates=bundle["dates"]+[v3.v2.TEST_ORIGIN+timedelta(days=h) for h in range(1,29)]
    values=np.concatenate([bundle["history"],bundle["actual"]],axis=1)
    v3.v2.v1.write_csv(output/"selected_series.csv",[{"rank":i+1,"item_id":r["item_id"],"store_id":store,
        "train_units":r["train_units"]} for i,r in enumerate(selected)])
    v3.v2.v1.write_csv(output/"history.csv",[{"date":day,"item_id":r["item_id"],"store_id":store,"units":values[i,t]}
        for i,r in enumerate(selected) for t,day in enumerate(dates)])
    predictions,metrics=[],[]
    for split,origin,actual,preds in (("validation",v3.v2.origins()[-1],data["actual"][-1],{k:x[-1,0] for k,x in val.items()}),
                                    ("test",v3.v2.TEST_ORIGIN,bundle["actual"],{k:x[0] for k,x in test.items()})):
        for name in ("seasonal_naive","weekday_mean4","random_forest","selected_forecast"):
            predicted=preds[name]
            metrics.append({"split":split,"model":name,"item_id":"ALL","store_id":store,
                            "observations":actual.size,**v3.v2.v1.scores(actual,predicted)})
            for i,item in enumerate(selected):
                metrics.append({"split":split,"model":name,"item_id":item["item_id"],"store_id":store,
                                "observations":28,**v3.v2.v1.scores(actual[i],predicted[i])})
                for h in range(28):
                    predictions.append({"split":split,"model":name,"item_id":item["item_id"],"store_id":store,
                        "origin_date":origin,"date":origin+timedelta(days=h+1),"horizon":h+1,
                        "actual":actual[i,h],"prediction":predicted[i,h]})
    v3.v2.v1.write_csv(output/"predictions.csv",predictions)
    v3.v2.v1.write_csv(output/"metrics.csv",metrics)
    v3.v2.v1.write_csv(output/"model_selection.csv",[{"item_id":r["item_id"],"store_id":store,"model":choice,
        "baseline_mae":v3.v2.v1.scores(data["actual"][:,i],data["seasonal_naive"][:,0,i])["mae"],
        "rf_mae":v3.v2.v1.scores(data["actual"][:,i],data["random_forest"][:,0,i])["mae"]}
        for i,r in enumerate(selected)])
    v3.v2.v1.write_csv(output/"rolling_metrics.csv",[{"fold":fold+1,"candidate":name,
        "origin_date":origin,"item_id":item["item_id"],"store_id":store,
        **v3.v2.v1.scores(data["actual"][fold,i],val[name][fold,0,i])}
        for fold,origin in enumerate(v3.v2.origins()) for name in
        ("seasonal_naive","weekday_mean4","random_forest","selected_forecast") for i,item in enumerate(selected)])
    report={"status":"success","input":v3.v2.v1.analysis.input_uri(str(source)),"store_id":store,
        "series_count":len(selected),"pipeline_version":"v2","selected_candidate":choice,
        "selected_params":{**v3.v2.CONFIG["rf"],"window_days":180,"strategy":choice},
        "selected_models":{r["item_id"]:choice for r in selected},"k_seed42":ks[0],
        "calibration":"k fit on this store/panel validation only; applied only for rf_calibrated",
        "reused_predictions":bundle["reused"],"published_seed":42,
        "model_artifact":None,
        "model_artifact_note":"CSV replay; any existing random_forest.joblib is a V1 artifact, not the V2 selected model",
        "train":{"start":str(dates[0]),"end":str(v3.v2.SELECTION_DATE)},
        "validation":{"start":"2015-12-07","end":"2016-03-27","windows":13},
        "validation_display":{"start":"2016-02-29","end":"2016-03-27"},
        "test":{"start":"2016-03-28","end":"2016-04-24"},
        "metrics":[r for r in metrics if r["item_id"]=="ALL"],
        "protocol":["V3 frozen candidate, same protocol for new stores; no test tuning",
                    "13 overlapping weekly origins in four nonoverlapping phases",
                    "Published seed42; three-seed research metrics live in docs/review/V3_RESULTS.md",
                    "Observed sales only, no inference of stockouts or latent demand"]}
    dump(output/"forecast_report.json",report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=ROOT/"GuiDat/data/processed_m5")
    parser.add_argument("--output",type=Path,default=ROOT/"outputs/forecast")
    parser.add_argument("--store",default="CA_1")
    parser.add_argument("--panel",choices=("recent","legacy"),default="recent")
    args=parser.parse_args()
    args.input=args.input.resolve()
    if not read(ROOT/"docs/review/V3_INTEGRATION.json")["integrate"]:
        raise ValueError("V3 did not pass the registered integration gate")
    choice=read(ROOT/"docs/review/V3_FROZEN.json")["choice"]
    bundle=obtain_bundle(args.input,args.store,args.panel,ROOT/"outputs/forecast_v3_pipeline_cache")
    report=export(bundle,args.input,args.output,args.store,choice)
    print(f"V2 {choice}: {args.store}/{args.panel}; reused={report['reused_predictions']}; seed42")


if __name__=="__main__": main()
