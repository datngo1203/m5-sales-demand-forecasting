"""Select 20 training-only M5 series with Spark and evaluate recursive forecasts."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import platform
import time

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestRegressor
from pyspark.sql import functions as F

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("analysis", Path(__file__).with_name("12_spark_analysis.py"))
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
HORIZON = 28
LOOKBACK = 28
FEATURES = ([f"lag_{lag}" for lag in (1, 7, 14, 28)]
            + ["mean_7", "mean_28", "weekday", "month", "day_of_year", "trend_days"])
CANDIDATES = [{"max_depth": 12, "min_samples_leaf": 5},
              {"max_depth": None, "min_samples_leaf": 2}]


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def split_dates(first, last):
    test_start = last - timedelta(days=HORIZON - 1)
    val_start = test_start - timedelta(days=HORIZON)
    if (val_start - first).days <= LOOKBACK:
        raise ValueError("Need more than 84 consecutive daily observations")
    return val_start, test_start


def load_panel(spark, source, store):
    df = analysis.prepare(spark.read.parquet(*analysis.parquet_paths(analysis.input_uri(source))))
    quality = analysis.validate(df)
    first, last = quality["date_min"], quality["date_max"]
    val_start, test_start = split_dates(first, last)
    store_df = df.filter(F.col("store_id") == store)
    ranked = (store_df.filter(F.col("date") < F.lit(val_start)).groupBy("item_id")
              .agg(F.sum("demand").alias("train_units"))
              .orderBy(F.desc("train_units"), F.asc("item_id")).limit(20).collect())
    if len(ranked) != 20:
        raise ValueError(f"Store {store!r} needs at least 20 training series")
    selected = [{"rank": i + 1, "item_id": row.item_id, "store_id": store,
                 "train_units": row.train_units} for i, row in enumerate(ranked)]
    items = [row["item_id"] for row in selected]
    daily = (store_df.filter(F.col("item_id").isin(items)).groupBy("item_id", "date")
             .agg(F.count("*").alias("source_rows"), F.sum("demand").alias("units")))
    dates = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    # Collect only the bounded 20-series daily panel, never all raw input rows.
    rows = daily.collect()
    lookup = {(row.item_id, row.date): row for row in rows}
    if len(rows) != len(items) * len(dates) or any(row.source_rows != 1 for row in rows):
        raise ValueError("Selected series have duplicate or missing daily observations; no zero fill applied")
    values = np.array([[lookup[item, day].units for day in dates] for item in items], dtype=float)
    return dates, values, selected, quality, val_start, test_start


def features(history, day, first, series_index, count):
    if len(history) < LOOKBACK:
        raise ValueError("Features require 28 known previous observations")
    return ([history[-lag] for lag in (1, 7, 14, 28)]
            + [float(np.mean(history[-7:])), float(np.mean(history[-28:])),
               day.weekday(), day.month, day.timetuple().tm_yday, (day - first).days]
            + [float(i == series_index) for i in range(count)])


def training_data(values, dates, end):
    x, y = [], []
    for series in range(len(values)):
        for t in range(LOOKBACK, end):
            x.append(features(values[series, :t], dates[t], dates[0], series, len(values)))
            y.append(values[series, t])
    return np.asarray(x), np.asarray(y)


def recursive_predict(model, known, dates, first):
    histories = [list(row) for row in known]
    result = []
    for day in dates:
        if model is None:
            predicted = np.array([history[-7] for history in histories])
        else:
            x = [features(history, day, first, i, len(histories))
                 for i, history in enumerate(histories)]
            predicted = np.maximum(0, model.predict(x))
        result.append(predicted)
        for history, prediction in zip(histories, predicted):
            history.append(float(prediction))
    return np.asarray(result).T


def scores(actual, predicted):
    error = np.asarray(actual) - np.asarray(predicted)
    return {"mae": float(np.mean(np.abs(error))), "rmse": float(np.sqrt(np.mean(error ** 2)))}


def fit_model(x, y, params):
    return RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=2,
                                 **params).fit(x, y)


def evaluate_panel(dates, values, selected, output):
    val_start, test_start = split_dates(dates[0], dates[-1])
    val_index, test_index = dates.index(val_start), dates.index(test_start)
    x, y = training_data(values, dates, val_index)
    trials = []
    best = None
    for params in CANDIDATES:
        model = fit_model(x, y, params)
        predicted = recursive_predict(model, values[:, :val_index], dates[val_index:test_index], dates[0])
        score = scores(values[:, val_index:test_index], predicted)
        trials.append({"params": params, **score})
        if best is None or score["mae"] < best[0]:
            best = (score["mae"], params, predicted)
    x, y = training_data(values, dates, test_index)
    model = fit_model(x, y, best[1])
    predictions, metrics = [], []
    for split, start, end in (("validation", val_index, test_index), ("test", test_index, len(dates))):
        actual = values[:, start:end]
        baseline = recursive_predict(None, values[:, :start], dates[start:end], dates[0])
        forest = (best[2] if split == "validation" else
                  recursive_predict(model, values[:, :start], dates[start:end], dates[0]))
        for name, predicted in (("seasonal_naive", baseline), ("random_forest", forest)):
            metrics.append({"split": split, "model": name, "item_id": "ALL", "store_id": selected[0]["store_id"],
                            "observations": actual.size, **scores(actual, predicted)})
            for i, item in enumerate(selected):
                metrics.append({"split": split, "model": name, "item_id": item["item_id"],
                                "store_id": item["store_id"], "observations": end - start,
                                **scores(actual[i], predicted[i])})
                for t, day in enumerate(dates[start:end]):
                    predictions.append({"split": split, "model": name, "item_id": item["item_id"],
                                        "store_id": item["store_id"], "origin_date": dates[start - 1],
                                        "date": day, "horizon": t + 1, "actual": actual[i, t],
                                        "prediction": predicted[i, t]})
    write_csv(output / "predictions.csv", predictions)
    write_csv(output / "metrics.csv", metrics)
    joblib.dump(model, output / "random_forest.joblib")
    return {"validation_candidates": trials, "selected_params": best[1],
            "train": {"start": dates[0], "end": dates[val_index - 1]},
            "validation": {"start": val_start, "end": dates[test_index - 1]},
            "test": {"start": test_start, "end": dates[-1]},
            "train_examples": len(selected) * (val_index - LOOKBACK),
            "refit_examples": len(y), "metrics": [row for row in metrics if row["item_id"] == "ALL"],
            "output_rows": {"predictions": len(predictions), "metrics": len(metrics)}}


def run(spark, source, output, store="CA_1"):
    started = time.perf_counter()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "forecast_report.json"
    report_path.unlink(missing_ok=True)
    dates, values, selected, quality, _, _ = load_panel(spark, source, store)
    write_csv(output / "selected_series.csv", selected)
    write_csv(output / "history.csv", ({"date": day, "item_id": item["item_id"],
              "store_id": store, "units": values[i, t]}
              for i, item in enumerate(selected) for t, day in enumerate(dates)))
    result = evaluate_panel(dates, values, selected, output)
    report = {"status": "success", "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "input": analysis.input_uri(source), "input_quality": quality,
              "store_id": store, "series_count": len(selected), "days": len(dates),
              "selection": "Top 20 by total training units in the requested store; item_id breaks ties",
              "features": FEATURES + [f"item_{row['item_id']}" for row in selected],
              "forest": {"n_estimators": 100, "random_state": 42, "n_jobs": 2},
              "protocol": ["Last 28 days test, preceding 28 validation; earlier days training",
                           "Select RF parameters by validation MAE; refit on train+validation before test",
                           "Each 28-day window has one fixed origin; recursive predictions replace unknown demand",
                           "Seasonal naive repeats the last known week recursively",
                           "No actual future demand, prices, or source forecasting features enter predictors",
                           "Metrics are per daily item/store observation; ALL pools equal-length series",
                           "Forecasts estimate observed sales, not latent demand during stockouts",
                           "Duplicate/missing dates rejected for selected series; HDFS requires a separate service test"],
              **result, "seconds": round(time.perf_counter() - started, 2),
              "environment": {"python": platform.python_version(), "spark": spark.version,
                              "numpy": np.__version__, "scikit_learn": sklearn.__version__,
                              "java": spark.sparkContext._jvm.java.lang.System.getProperty("java.version"),
                              "master": spark.sparkContext.master}}
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(ROOT / "GuiDat/data/processed_m5"))
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/forecast")
    parser.add_argument("--store", default="CA_1")
    parser.add_argument("--master", default="local[2]")
    parser.add_argument("--driver-memory", default="2g")
    args = parser.parse_args()
    spark = analysis.create_spark(args.master, args.driver_memory)
    spark.sparkContext.setLogLevel("WARN")
    try:
        print(json.dumps(run(spark, args.input, args.output, args.store), indent=2, default=str))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
