"""Verify every exported HDFS aggregate against the local reference, without changing it."""
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = {"daily_category_store": ["date", "cat_id", "store_id"],
          "daily_sales": ["date"], "category_sales": ["cat_id"], "store_sales": ["store_id"]}


def verify(reference, result):
    old = json.loads((reference / "analysis_report.json").read_text(encoding="utf-8"))
    new = json.loads((result / "analysis_report.json").read_text(encoding="utf-8"))
    if old["status"] != "success" or new["status"] != "success" or new["input_mode"] != "hdfs":
        raise ValueError("Require successful local and HDFS results")
    if new["quality"] != old["quality"] or new["output_rows"] != old["output_rows"]:
        raise ValueError("Input quality or output row counts differ")
    checked = {}
    for name, keys in TABLES.items():
        before, after = [pd.read_csv(folder / f"{name}.csv").sort_values(keys).reset_index(drop=True)
                         for folder in (reference, result)]
        pd.testing.assert_frame_equal(before, after, check_exact=False, rtol=1e-10, atol=1e-6)
        checked[name] = len(after)
    return {"status": "verified", "input": new["input"], "quality": new["quality"],
            "tables_checked": checked, "totals": new["totals"], "environment": new["environment"],
            "scope": "One NameNode and one DataNode in Docker on one machine; Spark local[2] reads HDFS",
            "report_sha256": hashlib.sha256((result / "analysis_report.json").read_bytes()).hexdigest()}


if __name__ == "__main__":
    result = ROOT / "outputs/analysis_hdfs"
    proof = verify(ROOT / "outputs/analysis", result)
    (result / "verification.json").write_text(json.dumps(proof, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(proof, indent=2, ensure_ascii=False))
