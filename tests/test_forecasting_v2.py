from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
import forecast_v2 as v2

spec = importlib.util.spec_from_file_location("v2_runner", ROOT / "scripts/run_forecast_v2.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class CausalForecastTests(unittest.TestCase):
    def fixture(self):
        dates = [date(2015, 1, 1) + timedelta(days=i) for i in range(420)]
        values = np.array([np.arange(420) % 7, (np.arange(420) % 9) * 2.], dtype=float)
        return dates, values, dates[350]

    def test_features_training_and_predictions_ignore_post_origin_demand(self):
        dates, values, origin = self.fixture()
        future = [origin + timedelta(days=h) for h in range(1, 29)]
        changed = values.copy()
        changed[:, 351:] = 1e9
        x, scales = v2.historical_features(values, dates, origin, future)
        xx, other_scales = v2.historical_features(changed, dates, origin, future)
        np.testing.assert_array_equal(x, xx)
        np.testing.assert_array_equal(scales, other_scales)
        train_x, train_y = v2.direct_training(values, dates, origin)
        changed_x, changed_y = v2.direct_training(changed, dates, origin)
        np.testing.assert_array_equal(train_x, changed_x)
        np.testing.assert_array_equal(train_y, changed_y)
        self.assertEqual(x.shape, (56, 7))
        self.assertEqual(train_x.shape[1], 7)
        # No future target can enter fitting, even if future demand is arbitrarily large.
        self.assertLess(float(train_y.max()), 20)
        models = v2.fit_forecasters(values, dates, origin, 42)
        predictions = v2.forecast(models, values, dates, origin)
        altered = v2.forecast(models, changed, dates, origin)
        for name in runner.MODELS:
            np.testing.assert_array_equal(predictions[name], altered[name])
            self.assertEqual(predictions[name].shape, (2, 28))
            self.assertTrue(np.isfinite(predictions[name]).all())
        # Fits must also ignore the altered future, not just inference.
        changed_models = v2.fit_forecasters(changed, dates, origin, 42)
        for name, pred in v2.forecast(changed_models, changed, dates, origin).items():
            np.testing.assert_array_equal(predictions[name], pred)
        for i in range(2):
            for h, target in enumerate(future):
                expected = np.mean([values[i, t] for t in range(323, 351)
                                    if dates[t].weekday() == target.weekday()])
                self.assertEqual(predictions["weekday_mean4"][i, h], expected)

    def test_direct_labels_and_origin_groups(self):
        dates, values, origin = self.fixture()
        x, y = v2.direct_training(values, dates, origin)
        end = dates.index(origin) + 1
        anchors = list(range(max(27, end - v2.WINDOW), end - 28, 7))
        rows = 2 * 28
        for j, anchor in enumerate(anchors):
            scale = np.maximum(values[:, anchor-27:anchor+1].mean(axis=1), 1)
            np.testing.assert_allclose(y[j*rows:(j+1)*rows],
                (values[:, anchor+1:anchor+29] / scale[:, None]).ravel())
            self.assertLessEqual(anchor + 28, dates.index(origin))
        origins = v2.origins()
        self.assertEqual((origins[0], origins[-1]), (date(2015, 12, 6), date(2016, 2, 28)))
        self.assertEqual(len(origins), 13)
        self.assertEqual(origins[-1] + timedelta(days=28), v2.TEST_ORIGIN)
        for group in range(4):
            phase = origins[group::4]
            for left, right in zip(phase, phase[1:]):
                self.assertEqual((right-left).days, 28)

    def test_sparse_scale_and_sensitivity_are_fixed_rules(self):
        known = np.array([[0.] * 28, [1.] * 28])
        raw, baseline = np.ones((2, 28)), np.zeros((2, 28))
        adjusted = v2.direct_variant(raw, baseline, known, k=2, fallback=True)
        np.testing.assert_array_equal(adjusted[0], 0)
        np.testing.assert_array_equal(adjusted[1], 2)
        actual = np.array([[0.] * 14 + [1.] * 14, [1.] * 28])
        self.assertTrue(v2.zero_run_flag(actual, [0]))
        self.assertFalse(v2.zero_run_flag(actual, [1]))
        self.assertFalse(v2.zero_run_flag(np.ones((2, 28)), [0, 1]))
        metric = v2.metrics(np.zeros((2, 28)), raw, known, baseline)
        self.assertIsNone(metric["bias_pct"])
        self.assertEqual(metric["normalized_rmse"], 1.)
        self.assertEqual(metric["bias_units"], metric["B_SN"] + metric["delta_bias"])

    def test_gate_uses_median_phases_and_nine_origins(self):
        rows = []
        for fold in range(13):
            for seed in v2.SEEDS:
                for model, mae, delta in (("random_forest", 10., 5.), ("direct_poisson", 10.3, 4.)):
                    rows.append({"fold": fold, "group": fold % 4, "seed": seed,
                                 "model": model, "mae": mae, "delta_bias": delta})
        self.assertTrue(v2.gate(rows)["passed"])
        for row in rows:
            if row["model"] == "direct_poisson" and row["fold"] >= 8:
                row["delta_bias"] = 6
        self.assertEqual(v2.gate(rows)["wins"], 8)
        self.assertFalse(v2.gate(rows)["passed"])
        # Very bad origin 0 should not turn the score into the pooled mean.
        for row in rows:
            if row["model"] == "random_forest" and row["fold"] == 0:
                row["mae"] = 1000
        self.assertEqual(v2.group_score(rows, "random_forest")[0], 10.)

    def test_freeze_uses_both_panels_and_blocks_unfrozen_or_repeated_test(self):
        from argparse import Namespace
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as folder:
            folder = Path(folder)
            args = Namespace(output=folder)
            with self.assertRaises(FileNotFoundError):
                runner.test(args)
            runner.dump(folder / "prepared.json", {"config": v2.CONFIG, "code_hashes": runner.code_hashes()})
            for panel in runner.PANELS:
                path = folder / "CA_1" / panel
                runner.dump(path / "validation_gate.json", {"passed": panel == "recent"})
                (path / "validation_metrics.csv").write_text("fixture")
                np.savez(path / "validation_predictions.npz", actual=np.array([0.]))
            runner.freeze(args)
            frozen = runner.verify_frozen(folder)
            self.assertFalse(frozen["step2_permitted"])
            self.assertTrue(all(x["choice"] == "random_forest" for x in frozen["panels"].values()))
            with self.assertRaises(ValueError):
                runner.freeze(args)
            for panel in runner.PANELS:
                path = folder / "CA_2" / panel
                path.mkdir(parents=True)
                np.savez(path / "validation_predictions.npz", actual=np.array([0.]))
            (folder / "test_started.json").write_text("already consumed")
            with self.assertRaises(FileExistsError), patch.object(runner, "spark_session") as spark:
                runner.test(args)
            spark.assert_not_called()

    def test_v1_reference_and_default_dashboard_contract_unchanged(self):
        self.assertEqual((ROOT / "code/13_forecasting.py").read_bytes(),
                         (ROOT / "code/13_forecasting_v1.py").read_bytes())
        self.assertNotIn("forecast_v2", (ROOT / "code/14_dashboard.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
