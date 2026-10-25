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
FOLDS = 4
FEATURES = ([f"lag_{lag}" for lag in (1, 7, 14, 28)]
            + ["mean_7", "mean_28", "weekday", "month", "day_of_year", "trend_days"])
RECENT_FEATURES = ["zero_fraction_7", "zero_fraction_28", "zero_streak_28", "mean_7_minus_28"]
CANDIDATES = [{"window_days": window, "max_depth": depth, "min_samples_leaf": leaf}
              for window in (None, 365, 180) for depth, leaf in ((12, 5), (None, 2))]


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


def rolling_starts(days):
    starts = list(range(days - HORIZON * (FOLDS + 1), days - HORIZON, HORIZON))
    if starts[0] < LOOKBACK + HORIZON:
        raise ValueError("Need at least 196 daily observations for four validation windows and direct training")
    return starts


def load_panel(spark, source, store):
    df = analysis.prepare(spark.read.parquet(*analysis.parquet_paths(analysis.input_uri(source))))
    quality = analysis.validate(df)
    first, last = quality["date_min"], quality["date_max"]
    val_start, test_start = split_dates(first, last)
    selection_end = first + timedelta(days=rolling_starts((last - first).days + 1)[0])
    store_df = df.filter(F.col("store_id") == store)
    ranked = (store_df.filter(F.col("date") < F.lit(selection_end)).groupBy("item_id")
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


def features(history, day, first, series_index, count, recent=True):
    if len(history) < LOOKBACK:
        raise ValueError("Features require 28 known previous observations")
    result = ([history[-lag] for lag in (1, 7, 14, 28)]
            + [float(np.mean(history[-7:])), float(np.mean(history[-28:])),
               day.weekday(), day.month, day.timetuple().tm_yday, (day - first).days])
    if recent:
        last = np.asarray(history[-LOOKBACK:])
        nonzero = np.flatnonzero(last > 0)
        result += [float(np.mean(last[-7:] == 0)), float(np.mean(last == 0)),
                   float(LOOKBACK - 1 - nonzero[-1]) if len(nonzero) else float(LOOKBACK),
                   float(np.mean(last[-7:]) - np.mean(last))]
    return result + [float(i == series_index) for i in range(count)]


def training_data(values, dates, end, window_days=None, recent=True, horizon=1):
    x, y = [], []
    for series in range(len(values)):
        for t in range(max(LOOKBACK, end - window_days) if window_days else LOOKBACK, end - horizon + 1):
            x.append(features(values[series, :t], dates[t], dates[0], series, len(values), recent))
            y.append(values[series, t] if horizon == 1 else values[series, t:t + horizon])
    return np.asarray(x), np.asarray(y)


def recursive_predict(model, known, dates, first, recent=True):
    histories = [list(row) for row in known]
    result = []
    for day in dates:
        if model is None:
            predicted = np.array([history[-7] for history in histories])
        else:
            x = [features(history, day, first, i, len(histories), recent)
                 for i, history in enumerate(histories)]
            predicted = np.maximum(0, model.predict(x))
        result.append(predicted)
        for history, prediction in zip(histories, predicted):
            history.append(float(prediction))
    return np.asarray(result).T


def scores(actual, predicted):
    error = np.asarray(actual) - np.asarray(predicted)
    total = float(np.sum(actual))
    bias = float(np.sum(predicted) - total)
    return {"mae": float(np.mean(np.abs(error))), "rmse": float(np.sqrt(np.mean(error ** 2))),
            "actual_units": total, "predicted_units": float(np.sum(predicted)),
            "bias_units": bias, "bias_pct": 100 * bias / total if total else None}


def direct_predict(model, known, dates, first):
    x = [features(history, dates[0], first, i, len(known)) for i, history in enumerate(known)]
    return np.maximum(0, model.predict(x))


def fit_model(x, y, params):
    return RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=2,
                                 **{k: v for k, v in params.items() if k not in ("window_days", "strategy")}).fit(x, y)


def select_forecasters(actual, baseline, forest):
    # Fold axes stay separate until selection; test observations never enter here.
    return ["random_forest" if scores(a, rf)["mae"] < scores(a, sn)["mae"] else "seasonal_naive"
            for a, sn, rf in zip(actual.transpose(1, 0, 2), baseline.transpose(1, 0, 2),
                                 forest.transpose(1, 0, 2))]


def evaluate_panel(dates, values, selected, output):
    val_start, test_start = split_dates(dates[0], dates[-1])
    val_index, test_index = dates.index(val_start), dates.index(test_start)
    starts = rolling_starts(len(dates))
    actual_folds = np.array([values[:, start:start + HORIZON] for start in starts])
    baseline_folds = np.array([recursive_predict(None, values[:, :start],
                               dates[start:start + HORIZON], dates[0]) for start in starts])
    trials, fold_metrics, candidate_predictions = [], [], []
    # Reuse the training matrix for the two depth settings in each history window.
    for window in (None, 365, 180):
        matrices = [training_data(values, dates, start, window) for start in starts]
        for params in (p for p in CANDIDATES if p["window_days"] == window):
            candidate_id = f"rf_{window or 'all'}_depth_{params['max_depth'] or 'none'}"
            forecasts = []
            for fold, (start, (x, y)) in enumerate(zip(starts, matrices), 1):
                model = fit_model(x, y, params)
                predicted = recursive_predict(model, values[:, :start], dates[start:start + HORIZON], dates[0])
                forecasts.append(predicted)
                for i, item in enumerate(selected):
                    fold_metrics.append({"fold": fold, "candidate": candidate_id,
                                         "origin_date": dates[start - 1], "item_id": item["item_id"],
                                         "store_id": item["store_id"], **scores(values[i, start:start + HORIZON], predicted[i])})
            forecasts = np.array(forecasts)
            candidate_predictions.append(forecasts)
            trials.append({"candidate": candidate_id, "params": params, **scores(actual_folds, forecasts)})
            print(json.dumps({"candidate": candidate_id, "validation_mae": trials[-1]["mae"]}), flush=True)
    # Reuse the best recursive configuration for one native multi-output RF trial.
    direct_params = {**min(trials, key=lambda row: (row["mae"], row["rmse"]))["params"], "strategy": "direct"}
    forecasts = []
    for fold, start in enumerate(starts, 1):
        x, y = training_data(values, dates, start, direct_params["window_days"], horizon=HORIZON)
        direct = fit_model(x, y, direct_params)
        predicted = direct_predict(direct, values[:, :start], dates[start:start + HORIZON], dates[0])
        forecasts.append(predicted)
        for i, item in enumerate(selected):
            fold_metrics.append({"fold": fold, "candidate": "rf_direct", "origin_date": dates[start - 1],
                                 "item_id": item["item_id"], "store_id": item["store_id"],
                                 **scores(values[i, start:start + HORIZON], predicted[i])})
    forecasts = np.array(forecasts)
    candidate_predictions.append(forecasts)
    trials.append({"candidate": "rf_direct", "params": direct_params, **scores(actual_folds, forecasts)})
    print(json.dumps({"candidate": "rf_direct", "validation_mae": trials[-1]["mae"]}), flush=True)
    best_index = min(range(len(trials)), key=lambda i: (trials[i]["mae"], trials[i]["rmse"]))
    best_params = trials[best_index]["params"]
    forest_folds = candidate_predictions[best_index]
    chosen = select_forecasters(actual_folds, baseline_folds, forest_folds)
    write_csv(output / "model_selection.csv", [
        {"item_id": item["item_id"], "store_id": item["store_id"], "model": choice,
         "baseline_mae": scores(actual_folds[:, i], baseline_folds[:, i])["mae"],
         "rf_mae": scores(actual_folds[:, i], forest_folds[:, i])["mae"]}
        for i, (item, choice) in enumerate(zip(selected, chosen))])
    for fold, start in enumerate(starts, 1):
        for i, item in enumerate(selected):
            fold_metrics.append({"fold": fold, "candidate": "seasonal_naive", "origin_date": dates[start - 1],
                                 "item_id": item["item_id"], "store_id": item["store_id"],
                                 **scores(actual_folds[fold - 1, i], baseline_folds[fold - 1, i])})
    write_csv(output / "rolling_metrics.csv", fold_metrics)
    is_direct = best_params.get("strategy") == "direct"
    x, y = training_data(values, dates, test_index, best_params["window_days"], horizon=HORIZON if is_direct else 1)
    model = fit_model(x, y, best_params)
    # Recompute the original RF on this exact panel for a comparable before/after.
    reference_x, reference_y = training_data(values, dates, test_index, recent=False)
    reference = fit_model(reference_x, reference_y, {"max_depth": 12, "min_samples_leaf": 5})
    reference_test = recursive_predict(reference, values[:, :test_index], dates[test_index:], dates[0], recent=False)
    predictions, metrics = [], []
    for split, start, end in (("validation", val_index, test_index), ("test", test_index, len(dates))):
        actual = values[:, start:end]
        baseline = recursive_predict(None, values[:, :start], dates[start:end], dates[0])
        forest = (forest_folds[-1] if split == "validation" else
                  (direct_predict if is_direct else recursive_predict)(
                      model, values[:, :start], dates[start:end], dates[0]))
        combined = np.array([rf if choice == "random_forest" else sn
                             for choice, rf, sn in zip(chosen, forest, baseline)])
        for name, predicted in (("seasonal_naive", baseline), ("random_forest", forest),
                                ("selected_forecast", combined)):
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
    initial_start = max(LOOKBACK, starts[0] - best_params["window_days"]) if best_params["window_days"] else LOOKBACK
    return {"validation_candidates": trials, "selected_params": best_params,
            "train": {"start": dates[0], "end": dates[starts[0] - 1]},
            "selection_cutoff": dates[starts[0] - 1],
            "validation": {"start": dates[starts[0]], "end": dates[test_index - 1], "windows": FOLDS},
            "validation_display": {"start": val_start, "end": dates[test_index - 1]},
            "test": {"start": test_start, "end": dates[-1]},
            "train_examples": len(selected) * (starts[0] - initial_start - (HORIZON - 1 if is_direct else 0)),
            "reference_test": scores(values[:, test_index:], reference_test),
            "selected_models": {item["item_id"]: choice for item, choice in zip(selected, chosen)},
            "rolling_baseline": scores(actual_folds, baseline_folds),
            "validation_note": "Development results used for selection; displayed validation is the last window, not an independent holdout",
            "test_note": "Previously inspected historical test; improvements are retrospective, not a fresh unseen test",
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
              "selection": "Top 20 by units strictly before the earliest validation origin; item_id breaks ties",
              "features": FEATURES + RECENT_FEATURES + [f"item_{row['item_id']}" for row in selected],
              "forest": {"n_estimators": 100, "random_state": 42, "n_jobs": 2},
              "protocol": ["Last 28 days test; four earlier nonoverlapping 28-day validation windows",
                           "Freeze the panel before the earliest validation window",
                           "Select RF window/depth by pooled rolling validation MAE, then RMSE to break ties",
                           "Also compare one direct 28-output RF with the best recursive window/depth",
                           "Choose RF or baseline per item using pooled validation MAE; ties use baseline",
                           "Refit selected RF configuration on data before test; selection never uses test targets",
                           "Each 28-day window has one fixed origin; direct RF predicts all 28 days at once",
                           "Recursive candidates replace unknown demand with predictions; direct targets end before each origin",
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
