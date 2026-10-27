"""Staged, opt-in V2 backtest. Never writes the default dashboard artifacts."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import date, timedelta, datetime, timezone

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
import numpy as np
import forecast_v2 as v2
import v2_panel

MODELS = ("seasonal_naive", "weekday_mean4", "random_forest", "direct_poisson")
PANELS = ("recent", "legacy")
VARIANTS = ("direct_poisson", "direct_calibrated", "direct_sparse", "direct_calibrated_sparse")


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(paths):
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def code_hashes():
    return fingerprint([ROOT / p for p in ("code/forecast_v2.py", "code/v2_panel.py",
        "code/13_forecasting_v1.py", "scripts/run_forecast_v2.py", "config/forecast.json")])


def spark_session():
    if not os.environ.get("JAVA_HOME"):
        jdks = sorted((ROOT / ".runtime").glob("jdk-17*"))
        if not jdks:
            raise ValueError("Set JAVA_HOME to JDK 17")
        os.environ["JAVA_HOME"] = str(jdks[0])
    os.environ["PATH"] = str(Path(os.environ["JAVA_HOME"]) / "bin") + os.pathsep + os.environ["PATH"]
    os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"
    os.environ["PYSPARK_PYTHON"] = sys.executable
    spark = v2.v1.analysis.create_spark()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def load_prepared(folder, store, panel):
    path = folder / store / panel
    meta = read(path / "panel.json")
    with np.load(path / "history_validation.npz", allow_pickle=False) as data:
        values = data["values"]
        dates = [date.fromisoformat(d) for d in data["dates"].tolist()]
    assert dates[-1] == v2.TEST_ORIGIN
    return path, meta, dates, values


def prepare(args):
    if (args.output / "prepared.json").exists():
        raise ValueError("Preparation already exists; use a new output directory")
    spark = spark_session()
    try:
        metadata = {"source": str(args.input.resolve()), "config": v2.CONFIG, "stores": ["CA_1", "CA_2"],
                    "code_hashes": code_hashes(),
                    "source_sha256": fingerprint(sorted(args.input.glob("*.parquet")))}
        if not metadata["source_sha256"]:
            raise ValueError("No source Parquet files")
        for store in metadata["stores"]:
            panels = v2_panel.load_panels(spark, str(args.input), store)
            for panel, selected in panels.items():
                path = args.output / store / panel
                path.mkdir(parents=True, exist_ok=True)
                dates, values = v2_panel.load_values(spark, str(args.input), store, selected, v2.TEST_ORIGIN)
                dump(path / "panel.json", {"store": store, "panel": panel, "selected": selected,
                    "selection_date": str(v2.SELECTION_DATE), "history_end": str(dates[-1])})
                np.savez_compressed(path / "history_validation.npz", values=values,
                                    dates=np.array([str(d) for d in dates]))
                print(f"prepared {store}/{panel}: {len(selected)} items, {len(dates)} days", flush=True)
        dump(args.output / "prepared.json", metadata)
    finally:
        spark.stop()


def origin_metrics(actual, forecasts, known, fold, seed, flagged):
    rows, bias = [], []
    for model, predicted in forecasts.items():
        rows.append({"fold": fold, "group": fold % 4, "origin_date": str(v2.origins()[fold]),
                     "seed": seed, "model": model, "zero_run_flag": bool(flagged),
                     **v2.metrics(actual, predicted, known, forecasts["seasonal_naive"])})
        for h in range(28):
            b_sn = float(np.sum(forecasts["seasonal_naive"][:, h] - actual[:, h]))
            b = float(np.sum(predicted[:, h] - actual[:, h]))
            bias.append({"fold": fold, "group": fold % 4, "origin_date": str(v2.origins()[fold]),
                         "seed": seed, "model": model, "horizon": h + 1,
                         "bias_units": b, "B_SN": b_sn, "delta_bias": b - b_sn})
    return rows, bias


def validate(args):
    meta = read(args.output / "prepared.json")
    assert meta["config"] == v2.CONFIG and meta["code_hashes"] == code_hashes(), "Code/config drift after prepare"
    if args.store == "CA_2" and not (args.output / "frozen.json").is_file():
        raise ValueError("Freeze CA_1 decisions before CA_2 validation")
    for panel in PANELS:
        path, panel_meta, dates, values = load_prepared(args.output, args.store, panel)
        if (path / "validation_predictions.npz").exists():
            raise ValueError("Validation exists; do not silently replace frozen evidence")
        selected = panel_meta["selected"]
        high = sorted(range(len(selected)), key=lambda i: (-selected[i]["recent_units"], selected[i]["item_id"]))[:10]
        predictions = {name: [] for name in MODELS}
        actuals, knowns, flags, rows, bias_rows = [], [], [], [], []
        for fold, origin in enumerate(v2.origins()):
            end = dates.index(origin) + 1
            known = values[:, :end]
            actual = values[:, end:end + 28]
            assert actual.shape == (20, 28)
            flag = v2.zero_run_flag(actual, high)
            fold_predictions = {name: [] for name in MODELS}
            for seed in v2.SEEDS:
                models = v2.fit_forecasters(known, dates[:end], origin, seed)
                forecasts = v2.forecast(models, known, dates[:end], origin)
                for name in MODELS:
                    fold_predictions[name].append(forecasts[name])
                r, b = origin_metrics(actual, forecasts, known, fold, seed, flag)
                rows.extend(r)
                bias_rows.extend(b)
            for name in MODELS:
                predictions[name].append(fold_predictions[name])
            actuals.append(actual)
            knowns.append(known[:, -28:])
            flags.append(flag)
            print(f"validation {args.store}/{panel} {fold+1}/13 {origin}", flush=True)
        np.savez_compressed(path / "validation_predictions.npz", actual=actuals, known=knowns, flags=flags,
                            **{k: np.asarray(v) for k, v in predictions.items()})
        v2.v1.write_csv(path / "validation_metrics.csv", rows)
        v2.v1.write_csv(path / "validation_bias_by_h.csv", bias_rows)
        dump(path / "validation_gate.json", v2.gate(rows))


def apply_variant(data, name, ks):
    raw = data["direct_poisson"]
    return np.asarray([[v2.direct_variant(raw[f, s], data["weekday_mean4"][f, s], data["known"][f],
        k=ks[s] if "calibrated" in name else 1., fallback="sparse" in name)
        for s in range(3)] for f in range(len(raw))])


def variant_metrics(data, predictions, name):
    rows = []
    for fold in range(13):
        for s, seed in enumerate(v2.SEEDS):
            rows.append({"fold": fold, "group": fold % 4, "seed": seed, "model": name,
                "zero_run_flag": bool(data["flags"][fold]),
                **v2.metrics(data["actual"][fold], predictions[fold, s], data["known"][fold],
                             data["seasonal_naive"][fold, s])})
    return rows


def freeze(args):
    if (args.output / "frozen.json").exists():
        raise ValueError("Decision already frozen")
    prepared = read(args.output / "prepared.json")
    assert prepared["config"] == v2.CONFIG and prepared["code_hashes"] == code_hashes()
    gates = {panel: read(args.output / "CA_1" / panel / "validation_gate.json") for panel in PANELS}
    passed = all(g["passed"] for g in gates.values())
    frozen = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "config": v2.CONFIG,
              "code_hashes": code_hashes(), "gates": gates, "step2_permitted": passed,
              "panels": {}, "prepared_sha256": fingerprint([args.output / "prepared.json"])}
    for panel in PANELS:
        path = args.output / "CA_1" / panel
        ks = [1., 1., 1.]
        choice = "random_forest"
        candidate_scores = {}
        if passed:
            with np.load(path / "validation_predictions.npz", allow_pickle=False) as data:
                total_actual = float(data["actual"].sum())
                ks = [total_actual / float(data["direct_poisson"][:, s].sum()) for s in range(3)]
                all_rows = []
                for name in VARIANTS:
                    rows = variant_metrics(data, apply_variant(data, name, ks), name)
                    score, groups = v2.group_score(rows, name)
                    candidate_scores[name] = {"score": score, "groups": groups}
                    all_rows.extend(rows)
                choice = min(VARIANTS, key=lambda n: (candidate_scores[n]["score"], VARIANTS.index(n)))
                v2.v1.write_csv(path / "step2_validation_metrics.csv", all_rows)
        frozen["panels"][panel] = {"choice": choice, "k_by_seed": ks, "candidate_scores": candidate_scores}
    frozen["validation_hashes"] = fingerprint([args.output / "CA_1" / p / f for p in PANELS
        for f in ("validation_predictions.npz", "validation_metrics.csv", "validation_gate.json")])
    dump(args.output / "frozen.json", frozen)
    print(json.dumps({"gates": gates, "step2_permitted": passed, "panels": frozen["panels"]}, indent=2), flush=True)


def verify_frozen(folder):
    frozen = read(folder / "frozen.json")
    assert frozen["config"] == v2.CONFIG and frozen["code_hashes"] == code_hashes(), "Frozen code/config changed"
    for key in ("validation_hashes", "prepared_sha256"):
        assert fingerprint([ROOT / p for p in frozen[key]]) == frozen[key], "Frozen evidence changed"
    return frozen


def test(args):
    frozen = verify_frozen(args.output)
    for store in ("CA_1", "CA_2"):
        for panel in PANELS:
            if not (args.output / store / panel / "validation_predictions.npz").is_file():
                raise ValueError("Complete both stores' validation before the single test pass")
    marker = args.output / "test_started.json"
    with marker.open("x", encoding="utf-8") as stream:
        json.dump({"started_at_utc": datetime.now(timezone.utc).isoformat(),
                   "frozen_sha256": fingerprint([args.output / "frozen.json"])}, stream, indent=2)
    # Fit/predict all frozen models from history before reading any test labels.
    pending = []
    for store in ("CA_1", "CA_2"):
        for panel in PANELS:
            path, meta, dates, values = load_prepared(args.output, store, panel)
            forecasts = {name: [] for name in MODELS}
            for s, seed in enumerate(v2.SEEDS):
                models = v2.fit_forecasters(values, dates, v2.TEST_ORIGIN, seed)
                predicted = v2.forecast(models, values, dates, v2.TEST_ORIGIN)
                if frozen["step2_permitted"]:
                    for name in VARIANTS:
                        predicted[name] = v2.direct_variant(predicted["direct_poisson"], predicted["weekday_mean4"],
                            values, frozen["panels"][panel]["k_by_seed"][s] if "calibrated" in name else 1.,
                            "sparse" in name)
                predicted["v2_frozen"] = predicted[frozen["panels"][panel]["choice"]]
                for name, pred in predicted.items():
                    forecasts.setdefault(name, []).append(pred)
            pending.append((store, panel, path, meta, values, forecasts))
            print(f"test forecasts ready {store}/{panel}; labels still unopened", flush=True)
    prepared = read(args.output / "prepared.json")
    source = Path(prepared["source"])
    assert fingerprint(sorted(source.glob("*.parquet"))) == prepared["source_sha256"], "Source drift"
    spark = spark_session()
    try:
        for store, panel, path, meta, known, forecasts in pending:
            dates, full = v2_panel.load_values(spark, str(source), store, meta["selected"],
                                              v2.TEST_ORIGIN + timedelta(days=28))
            assert np.array_equal(full[:, :-28], known)
            actual = full[:, -28:]
            rows, bias = [], []
            for s, seed in enumerate(v2.SEEDS):
                for name, predictions in forecasts.items():
                    pred = predictions[s]
                    rows.append({"seed": seed, "model": name,
                                 **v2.metrics(actual, pred, known, forecasts["seasonal_naive"][s])})
                    for h in range(28):
                        sn = float(np.sum(forecasts["seasonal_naive"][s][:, h] - actual[:, h]))
                        b = float(np.sum(pred[:, h] - actual[:, h]))
                        bias.append({"seed": seed, "model": name, "horizon": h+1,
                                     "bias_units": b, "B_SN": sn, "delta_bias": b-sn})
            np.savez_compressed(path / "test_predictions.npz", actual=actual, known=known[:, -28:],
                                **{name: np.asarray(pred) for name, pred in forecasts.items()})
            v2.v1.write_csv(path / "test_metrics.csv", rows)
            v2.v1.write_csv(path / "test_bias_by_h.csv", bias)
    finally:
        spark.stop()
    dump(args.output / "test_complete.json", {"completed_at_utc": datetime.now(timezone.utc).isoformat(),
         "frozen_sha256": fingerprint([args.output / "frozen.json"]), "stores": ["CA_1", "CA_2"]})


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "validate", "freeze", "test"))
    parser.add_argument("--input", type=Path, default=ROOT / "GuiDat/data/processed_m5")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/forecast_v2")
    parser.add_argument("--store", choices=("CA_1", "CA_2"), default="CA_1")
    args = parser.parse_args()
    {"prepare": prepare, "validate": validate, "freeze": freeze, "test": test}[args.stage](args)


if __name__ == "__main__":
    main()
