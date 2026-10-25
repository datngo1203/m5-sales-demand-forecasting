"""Freeze V3 procedure from existing V2 validation arrays only; no training."""
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"code"))
import numpy as np
import pyarrow.dataset as ds
import forecast_v3 as v3
from run_forecast_v2 import dump, fingerprint


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    output=ROOT/"outputs/forecast_v3"
    if (output/"frozen.json").exists():
        raise ValueError("V3 procedure already frozen")
    sets=[]
    rows=[]
    evidence=[]
    paths=[]
    for store in ("CA_1","CA_2"):
        for panel in ("recent","legacy"):
            path=ROOT/"outputs/forecast_v2"/store/panel/"validation_predictions.npz"
            paths.append(path)
            with np.load(path,allow_pickle=False) as data:
                ks,_,origin_rows,summary=v3.validation(data)
            sets.append(summary)
            rows.extend({"store":store,"panel":panel,**r} for r in origin_rows)
            evidence.append({"store":store,"panel":panel,"k_by_seed":ks,"summary":summary})
    decision=v3.select(sets)
    source=Path(json.loads((ROOT/"outputs/forecast_v2/prepared.json").read_text())["source"])
    inventory=ds.dataset(str(source),format="parquet",exclude_invalid_files=True).to_table(
        columns=["store_id"],filter=(ds.field("date")==v3.v2.SELECTION_DATE)&
        (ds.field("item_id")=="FOODS_3_090"))
    available=sorted(set(inventory.column("store_id").to_pylist())-{"CA_1","CA_2"})
    stores=[s for s in ("CA_3","TX_1","WI_1") if s in available]
    stores+=( [s for s in available if s not in stores][:3-len(stores)] )
    if len(stores)!=3:
        raise ValueError("Need three unused stores")
    frozen={"created_at_utc":datetime.now(timezone.utc).isoformat(),"choice":decision["choice"],
        "selection":decision,"stores":stores,"panels":["recent","legacy"],
        "config":v3.v2.CONFIG,"blend_weight":.5,"k_policy":"fit from each store/panel validation, per seed",
        "validation_hashes":fingerprint(paths),"procedure_hashes":fingerprint([ROOT/p for p in
            ("code/forecast_v3.py","code/forecast_v2.py","code/v2_panel.py","code/13_forecasting_v1.py",
             "docs/review/V3_PLAN.md","scripts/select_forecast_v3.py","scripts/run_forecast_v3.py")])}
    dump(output/"selection.json",{"decision":decision,"sets":evidence})
    v3.v2.v1.write_csv(output/"development_origin_metrics.csv",rows)
    dump(output/"frozen.json",frozen)
    dump(ROOT/"docs/review/V3_SELECTION.json",{"decision":decision,"sets":evidence})
    dump(ROOT/"docs/review/V3_FROZEN.json",frozen)
    print(json.dumps(decision,indent=2))


if __name__=="__main__":
    main()
