"""Opt-in V2 experiment helpers. The default V1 pipeline is unchanged."""

from datetime import date, timedelta
import importlib.util
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from v2_panel import rank_panel, selection_stats

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forecast_v1", Path(__file__).with_name("13_forecasting_v1.py"))
v1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v1)

HORIZON = 28
SELECTION_DATE = date(2015, 12, 6)
TEST_ORIGIN = date(2016, 3, 27)
SEEDS = (42, 43, 44)
WINDOW = 180
RECENT_DAYS = 26 * 7
SPARSE_DAYS = 28  # Fixed protocol: no validation/test tuning of this fallback threshold.
ZERO_RUN = 14  # Sensitivity only, not a stockout label or a training/evaluation mask.
CONFIG = {
    "seeds": list(SEEDS), "window_days": WINDOW, "selection_date": str(SELECTION_DATE),
    "rf": {"n_estimators": 100, "max_depth": 12, "min_samples_leaf": 5, "n_jobs": 2},
    "direct": {"loss": "poisson", "learning_rate": 0.1, "max_iter": 100,
               "max_leaf_nodes": 15, "min_samples_leaf": 20,
               "l2_regularization": 1.0, "early_stopping": False},
    "gate": {"required_wins": 9, "mae_ratio_limit": 1.03},
    "sparse_days": SPARSE_DAYS, "zero_run": ZERO_RUN, "sensitivity_top_items": 10,
}


def origins():
    return [SELECTION_DATE + timedelta(weeks=i) for i in range(13)]


def historical_features(values, dates, origin, target_dates):
    """One row per item/h. Demand after origin is never accessed."""
    end = dates.index(origin) + 1
    if end < 28 or any(day <= origin for day in target_dates):
        raise ValueError("Need 28 known days and strictly future target dates")
    last = values[:, end - 28:end]
    mean28 = last.mean(axis=1)
    zero = (last == 0).mean(axis=1)
    weekdays = np.array([day.weekday() for day in dates[end - 28:end]])
    rows = []
    for i in range(len(values)):
        for day in target_dates:
            weekday_mean = float(last[i, weekdays == day.weekday()].mean())
            rows.append([weekday_mean, mean28[i], zero[i], day.weekday(), day.month,
                         (day - origin).days, i])
    return np.asarray(rows), np.maximum(mean28, 1.0)


def direct_training(values, dates, origin):
    end = dates.index(origin) + 1
    matrices, targets = [], []
    # Inclusive day index a is the historical anchor; all 28 targets must be known.
    for a in range(max(27, end - WINDOW), end - HORIZON, 7):
        x, scale = historical_features(values, dates, dates[a], dates[a + 1:a + 29])
        matrices.append(x)
        targets.append((values[:, a + 1:a + 29] / scale[:, None]).ravel())
    if not matrices:
        raise ValueError("Not enough history for direct training")
    return np.concatenate(matrices), np.concatenate(targets)


def fit_forecasters(values, dates, origin, seed):
    end = dates.index(origin) + 1
    # v1 training_data's end is exclusive, matching the inclusive origin contract.
    x, y = v1.training_data(values[:, :end], dates[:end], end, window_days=WINDOW)
    rf = RandomForestRegressor(random_state=seed, **CONFIG["rf"]).fit(x, y)
    x, y = direct_training(values[:, :end], dates[:end], origin)
    direct = HistGradientBoostingRegressor(random_state=seed, categorical_features=[6],
                                         **CONFIG["direct"]).fit(x, y)
    return rf, direct


def forecast(models, values, dates, origin):
    end = dates.index(origin) + 1
    days = [origin + timedelta(days=h) for h in range(1, HORIZON + 1)]
    x, scale = historical_features(values, dates, origin, days)
    baseline4 = x[:, 0].reshape(len(values), HORIZON)
    known = values[:, :end]
    rf, direct = models
    return {
        "seasonal_naive": v1.recursive_predict(None, known, days, dates[0]),
        "weekday_mean4": baseline4,
        "random_forest": v1.recursive_predict(rf, known, days, dates[0]),
        "direct_poisson": direct.predict(x).reshape(len(values), HORIZON) * scale[:, None],
    }


def metrics(actual, predicted, known, baseline):
    result = v1.scores(actual, predicted)
    b_sn = float(np.sum(baseline) - np.sum(actual))
    scale = np.maximum(known[:, -28:].mean(axis=1), 1.0)
    result.update(B_SN=b_sn, delta_bias=result["bias_units"] - b_sn,
                  normalized_rmse=float(np.sqrt(np.mean(((predicted - actual) / scale[:, None]) ** 2))))
    return result


def zero_run_flag(actual, high_volume_indices):
    for i in high_volume_indices:
        run = 0
        for value in actual[i]:
            run = run + 1 if value == 0 else 0
            if run >= ZERO_RUN:
                return True
    return False


def direct_variant(prediction, baseline4, known, k=1.0, fallback=False):
    result = prediction * k
    if fallback:
        result = result.copy()
        result[known[:, -SPARSE_DAYS:].sum(axis=1) == 0] = baseline4[
            known[:, -SPARSE_DAYS:].sum(axis=1) == 0]
    return result


def group_score(rows, model):
    """Median origins within phase, then median phases; seed metrics averaged first."""
    selected = [r for r in rows if r["model"] == model]
    phases = []
    for group in range(4):
        fold_ids = sorted({r["fold"] for r in selected if r["group"] == group})
        if not fold_ids:
            raise ValueError("Missing validation phase")
        phases.append(float(np.median([np.mean([r["mae"] for r in selected if r["fold"] == fold])
                                      for fold in fold_ids])))
    return float(np.median(phases)), phases


def gate(rows):
    folds = sorted({r["fold"] for r in rows})
    if len(folds) != 13:
        raise ValueError("Gate requires all 13 origins")
    wins = 0
    for fold in folds:
        means = {model: float(np.mean([r["delta_bias"] for r in rows
                                      if r["fold"] == fold and r["model"] == model]))
                 for model in ("random_forest", "direct_poisson")}
        wins += means["direct_poisson"] < means["random_forest"]
    rf, _ = group_score(rows, "random_forest")
    direct, _ = group_score(rows, "direct_poisson")
    return {"wins": int(wins), "origins": len(folds), "rf_score": rf, "direct_score": direct,
            "mae_ratio": direct / rf if rf else None,
            "passed": bool(wins >= CONFIG["gate"]["required_wins"] and
                           direct <= CONFIG["gate"]["mae_ratio_limit"] * rf)}
