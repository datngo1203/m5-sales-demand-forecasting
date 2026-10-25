import csv
from datetime import date, timedelta
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

spec = importlib.util.spec_from_file_location(
    "forecast", Path(__file__).resolve().parents[1] / "code/13_forecasting.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ForecastLogicTests(unittest.TestCase):
    def test_split_features_and_no_future_targets(self):
        dates = [date(2020, 1, 1) + timedelta(days=i) for i in range(120)]
        values = np.arange(240, dtype=float).reshape(2, 120)
        val_start, test_start = module.split_dates(dates[0], dates[-1])
        self.assertEqual(dates.index(val_start), 64)
        self.assertEqual(dates.index(test_start), 92)
        x, y = module.training_data(values, dates, 64)
        changed = values.copy()
        changed[:, 64:] = 1e9
        changed_x, changed_y = module.training_data(changed, dates, 64)
        np.testing.assert_array_equal(x, changed_x)
        np.testing.assert_array_equal(y, changed_y)
        self.assertEqual(x[0, :4].tolist(), [27, 21, 14, 0])
        self.assertEqual(y[0], 28)
        with self.assertRaises(ValueError):
            module.split_dates(dates[0], dates[80])

    def test_recursive_forests_and_weekly_baseline(self):
        class LastPlusOne:
            def predict(self, x):
                return np.asarray(x)[:, 0] + 1

        dates = [date(2020, 2, 1) + timedelta(days=i) for i in range(28)]
        known = np.arange(28, dtype=float).reshape(1, 28)
        result = module.recursive_predict(LastPlusOne(), known, dates, date(2020, 1, 4))
        np.testing.assert_array_equal(result[0], np.arange(28, 56))
        baseline = module.recursive_predict(None, known, dates, date(2020, 1, 4))
        np.testing.assert_array_equal(baseline[0], np.tile(np.arange(21, 28), 4))
        self.assertEqual(module.scores([0, 2], [0, 0]), {"mae": 1., "rmse": 2 ** .5})
        np.testing.assert_array_equal(known[0], np.arange(28))


class ForecastSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = module.analysis.create_spark()
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def fixture(self, folder, duplicate=False, missing=False):
        rows = []
        for i in range(21):
            for t in range(110):
                if missing and i == 1 and t == 50:
                    continue
                # Item 00 wins only in the future and must not be selected.
                units = (10000 if t >= 54 else 0) if i == 0 else i
                rows.append({"date": date(2020, 1, 1) + timedelta(days=t),
                             "item_id": f"item{i:02}", "cat_id": "FOODS", "store_id": "S",
                             "demand": units, "sell_price": 1.})
        if duplicate:
            rows.append(rows[-1])
        path = Path(folder) / "input.parquet"
        pq.write_table(pa.Table.from_pylist(rows), path)
        return path

    def test_end_to_end_training_only_selection_exports_and_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            source = self.fixture(folder)
            output = Path(folder) / "out"
            report = module.run(self.spark, str(source), output, "S")
            self.assertEqual(report["status"], "success")
            selected = list(csv.DictReader(io.StringIO((output / "selected_series.csv").read_text())))
            self.assertEqual(len(selected), 20)
            self.assertEqual(selected[0]["item_id"], "item20")
            self.assertNotIn("item00", [row["item_id"] for row in selected])
            predictions = list(csv.DictReader(io.StringIO((output / "predictions.csv").read_text())))
            self.assertEqual(len(predictions), 2240)
            for split in ("validation", "test"):
                for model in ("seasonal_naive", "random_forest"):
                    subset = [r for r in predictions if r["split"] == split and r["model"] == model]
                    self.assertEqual(len(subset), 560)
                    self.assertEqual(len({r["origin_date"] for r in subset}), 1)
                    self.assertTrue(all(r["date"] > r["origin_date"] for r in subset))
                    metric = next(r for r in report["metrics"] if r["split"] == split and r["model"] == model)
                    computed = module.scores([float(r["actual"]) for r in subset],
                                             [float(r["prediction"]) for r in subset])
                    self.assertAlmostEqual(metric["mae"], computed["mae"])
                    self.assertAlmostEqual(metric["rmse"], computed["rmse"])
            self.assertTrue((output / "random_forest.joblib").is_file())
            self.assertEqual(json.loads((output / "forecast_report.json").read_text())["status"], "success")
            # A failed rerun must not retain a stale success report.
            with self.assertRaisesRegex(ValueError, "at least 20"):
                module.run(self.spark, str(source), output, "ABSENT")
            self.assertFalse((output / "forecast_report.json").exists())

    def test_reject_duplicate_and_missing_selected_dates(self):
        for options in ({"duplicate": True}, {"missing": True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                source = self.fixture(folder, **options)
                with self.assertRaisesRegex(ValueError, "duplicate or missing"):
                    module.load_panel(self.spark, str(source), "S")


if __name__ == "__main__":
    unittest.main()
