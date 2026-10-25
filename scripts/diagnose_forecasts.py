"""Read existing CSV/Parquet only; print diagnosis measurements as JSON, never fit models.

Run from any directory: .venv/Scripts/python.exe scripts/diagnose_forecasts.py
Dependencies: numpy and pyarrow, already pinned in requirements-*.txt.
"""

import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import statistics

import numpy as np
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def trend(values):
    y = np.asarray(values, dtype=float)
    x = np.arange(1, len(y) + 1)
    return {
        "slope_units_per_item_per_h": float(np.polyfit(x, y, 1)[0]),
        "pearson_r": float(np.corrcoef(x, y)[0, 1]) if np.std(y) else None,
        "increasing_steps": int(np.sum(np.diff(y) > 0)),
        "decreasing_steps": int(np.sum(np.diff(y) < 0)),
        "weekly_mean_bias": [float(np.mean(w)) for w in y.reshape(4, 7)],
    }


def describe(rows):
    zero = [r for r in rows if r["demand"] == 0]
    null = sum(r["sell_price"] is None for r in zero)
    return {
        "days": len(rows), "units": sum(r["demand"] for r in rows),
        "price_null_days": sum(r["sell_price"] is None for r in rows),
        "zero_days": len(zero), "zero_price_null": null,
        "zero_price_present": len(zero) - null,
        "pct_null_given_zero": 100 * null / len(zero) if zero else None,
        "pct_present_given_zero": 100 * (len(zero) - null) / len(zero) if zero else None,
        "pct_zero_and_null_all_days": 100 * null / len(rows),
        "pct_zero_and_present_all_days": 100 * (len(zero) - null) / len(rows),
        "present_prices": sorted({r["sell_price"] for r in rows if r["sell_price"] is not None}),
    }


def main():
    # Small independent checks of formulas, without importing forecasting/training code.
    assert np.isclose(trend(range(28))["slope_units_per_item_per_h"], 1)
    assert statistics.pstdev([0, 2]) == 1
    assert describe([{"demand": 0, "sell_price": None},
                     {"demand": 0, "sell_price": 1}])["pct_null_given_zero"] == 50
    forecast = ROOT / "outputs/forecast"
    required = [forecast / name for name in
                ("history.csv", "predictions.csv", "selected_series.csv", "forecast_report.json")]
    source = ROOT / "GuiDat/data/processed_m5"
    missing = [str(p.relative_to(ROOT)) for p in required if not p.is_file()]
    parquet = sorted(source.glob("*.parquet"))
    if not parquet:
        missing.append("GuiDat/data/processed_m5/*.parquet")
    if missing:
        print(json.dumps({"missing": missing, "recreate_outputs":
              "Restore source Parquet per DATA_SOURCE.md, then ./run_pipeline.ps1 -SkipInstall. "
              "Pipeline retrains models: do not run under diagnosis-only authorization."}, indent=2))
        return

    selected = read_csv(forecast / "selected_series.csv")
    items = sorted(r["item_id"] for r in selected)
    assert len(set(items)) == 20 and {r["store_id"] for r in selected} == {"CA_1"}
    history = read_csv(forecast / "history.csv")
    lookup = {(r["item_id"], r["date"]): float(r["units"]) for r in history}
    assert len(lookup) == len(history) == 20 * 1913
    assert {r["item_id"] for r in history} == set(items)
    assert {r["store_id"] for r in history} == {"CA_1"}
    predictions = read_csv(forecast / "predictions.csv")
    report = json.loads((forecast / "forecast_report.json").read_text(encoding="utf-8"))
    assert "strategy" not in report["selected_params"], "RF must be recursive for this diagnosis"
    keys = [(r["split"], r["model"], r["item_id"], r["date"]) for r in predictions]
    assert len(set(keys)) == len(keys) == 3360
    for r in predictions:
        assert float(r["actual"]) == lookup[r["item_id"], r["date"]]
        assert (date.fromisoformat(r["date"]) - date.fromisoformat(r["origin_date"])).days == int(r["horizon"])

    result = {"input": {"history_rows": len(history), "prediction_rows": len(predictions),
              "history_start": min(r["date"] for r in history),
              "history_end": max(r["date"] for r in history), "parquet_files": len(parquet),
              "selected_params": report["selected_params"], "sha256": {
                  str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in required}},
              "review_files": {}}
    # Read all review artifacts; compare full snapshots or sparse extracts to their owners.
    for path in sorted((ROOT / "docs/review").iterdir()):
        if path.suffix not in (".csv", ".json"):
            continue
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            result["review_files"][path.name] = {"status": value.get("status")}
        else:
            result["review_files"][path.name] = {"rows": len(read_csv(path))}
        owner = forecast / path.name
        if owner.is_file():
            assert path.read_bytes() == owner.read_bytes(), f"Stale review snapshot: {path.name}"
            result["review_files"][path.name]["identical_to_output"] = True
        elif path.name == "sparse_history.csv":
            assert all(float(r["units"]) == lookup[r["item_id"], r["date"]] for r in read_csv(path))
        elif path.name == "sparse_predictions.csv":
            assert all(r in predictions for r in read_csv(path))

    weekly = []
    for group in [items, ["FOODS_3_120"], ["FOODS_3_090"], ["FOODS_3_587"]]:
        totals = []
        for start in (date(2016, 3, 21), date(2016, 3, 28)):
            totals.append(sum(lookup[item, (start + timedelta(days=d)).isoformat()]
                              for item in group for d in range(7)))
        # All prior complete Monday-Sunday weeks: descriptive historical context only.
        start = date(2011, 1, 31)
        past = []
        while start + timedelta(days=6) < date(2016, 3, 21):
            past.append(sum(lookup[item, (start + timedelta(days=d)).isoformat()]
                            for item in group for d in range(7)))
            start += timedelta(days=7)
        weekly.append({"item": "ALL" if len(group) == 20 else group[0],
                       "origin_week": totals[0], "next_week": totals[1],
                       "origin_vs_next_pct": 100 * (totals[0] / totals[1] - 1) if totals[1] else None,
                       "prior_weeks": len(past), "prior_median": statistics.median(past),
                       "prior_p95": float(np.percentile(past, 95)),
                       "prior_weeks_le_origin_pct": 100 * sum(v <= totals[0] for v in past) / len(past)})
    result["weeks"] = weekly

    table = ds.dataset([str(p) for p in parquet], format="parquet").to_table(
        columns=["item_id", "store_id", "date", "demand", "sell_price", "event_name_1", "event_name_2"],
        filter=(ds.field("store_id") == "CA_1") & ds.field("item_id").isin(items))
    raw = table.to_pylist()
    assert len(raw) == len(history)
    assert len({(r["item_id"], r["date"]) for r in raw}) == len(raw)
    for r in raw:
        assert r["demand"] == lookup[r["item_id"], r["date"].isoformat()]
        assert r["sell_price"] is None or np.isfinite(r["sell_price"])
    result["prices"] = {"all": describe(raw), "per_item": {
        item: describe([r for r in raw if r["item_id"] == item]) for item in items}}
    for name, start, end in (("december_090", date(2015, 12, 1), date(2015, 12, 31)),
                              ("fold1_090", date(2015, 12, 7), date(2016, 1, 3))):
        rows = [r for r in raw if r["item_id"] == "FOODS_3_090" and start <= r["date"] <= end]
        assert len(rows) == (end - start).days + 1
        result["prices"][name] = describe(rows)
        result["prices"][name]["daily"] = [{"date": r["date"].isoformat(), "demand": r["demand"],
                                             "sell_price": r["sell_price"]} for r in sorted(rows, key=lambda r: r["date"])]
    result["origin_sunday_events"] = sorted({str(r[k]) for r in raw if r["date"] == date(2016, 3, 27)
                                             for k in ("event_name_1", "event_name_2")})

    result["bias"] = {}
    result["dispersion"] = {}
    for split in ("validation", "test"):
        result["bias"][split] = {}
        result["dispersion"][split] = []
        for model in ("seasonal_naive", "random_forest"):
            rows = [r for r in predictions if r["split"] == split and r["model"] == model]
            assert len(rows) == 560 and {r["item_id"] for r in rows} == set(items)
            assert len({r["origin_date"] for r in rows}) == 1
            horizon = []
            for h in range(1, 29):
                subset = [r for r in rows if int(r["horizon"]) == h]
                assert len(subset) == 20
                actual = sum(float(r["actual"]) for r in subset)
                pred = sum(float(r["prediction"]) for r in subset)
                horizon.append({"h": h, "actual_sum": actual, "predicted_sum": pred,
                                "bias_sum": pred - actual, "bias_mean": (pred - actual) / 20})
            bias_sum = sum(r["bias_sum"] for r in horizon)
            metric = next(r for r in report["metrics"] if r["split"] == split and r["model"] == model)
            assert np.isclose(bias_sum, metric["bias_units"])
            result["bias"][split][model] = {"origin": rows[0]["origin_date"], "horizons": horizon,
                "total_bias": bias_sum, **trend([r["bias_mean"] for r in horizon])}
            if model != "random_forest":
                continue
            for item in items:
                subset = sorted([r for r in rows if r["item_id"] == item], key=lambda r: int(r["horizon"]))
                a = np.array([float(r["actual"]) for r in subset])
                p = np.array([float(r["prediction"]) for r in subset])
                assert np.all(p >= 0)
                sd_a, sd_p = float(np.std(a)), float(np.std(p))
                result["dispersion"][split].append({"item": item, "actual_sum": float(a.sum()),
                    "predicted_sum": float(p.sum()), "actual_std": sd_a, "prediction_std": sd_p,
                    "std_ratio": sd_p / sd_a if sd_a else None,
                    "first7_std": float(np.std(p[:7])), "last7_std": float(np.std(p[-7:])),
                    "actual_zero_days": int(np.sum(a == 0)), "prediction_zero_days": int(np.sum(p == 0)),
                    "prediction_min": float(p.min()), "prediction_max": float(p.max())})
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
