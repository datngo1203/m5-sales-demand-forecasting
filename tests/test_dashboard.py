import importlib.util
from datetime import date
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "code/14_dashboard.py"
spec = importlib.util.spec_from_file_location("dashboard", APP)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    def fixture(self, folder):
        folder = Path(folder)
        (folder / "analysis").mkdir()
        (folder / "forecast").mkdir()
        report = {"status": "success", "input": "fixture", "store_id": "A", "series_count": 2,
                  "train": {}, "validation": {}, "test": {}, "selected_params": {}}
        for name in ("analysis/analysis_report.json", "forecast/forecast_report.json"):
            (folder / name).write_text(json.dumps(report), encoding="utf-8")
        daily = pd.DataFrame([{"date": "2020-01-01", "cat_id": "FOODS", "store_id": store,
                               "units": 2, "rows": 4, "priced_rows": 0, "priced_units": 0,
                               "revenue_known": None} for store in ("A", "B")])
        daily.to_csv(folder / "analysis/daily_category_store.csv", index=False)
        pd.DataFrame([{"date": "2020-01-01", "store_id": "A", "item_id": item, "units": 2}
                      for item in ("item1", "item2")]).to_csv(folder / "forecast/history.csv", index=False)
        predictions, metrics = [], []
        for split in ("test", "validation"):
            for item in ("item1", "item2"):
                for model in ("seasonal_naive", "random_forest"):
                    predictions.append({"date": "2020-01-02", "origin_date": "2020-01-01",
                                        "store_id": "A", "item_id": item, "split": split,
                                        "model": model, "prediction": 3, "actual": 2})
                    metrics.append({"store_id": "A", "item_id": item, "split": split,
                                    "model": model, "observations": 1, "mae": 1, "rmse": 1})
        pd.DataFrame(predictions).to_csv(folder / "forecast/predictions.csv", index=False)
        pd.DataFrame(metrics).to_csv(folder / "forecast/metrics.csv", index=False)

    def test_filters_charts_and_unavailable_store(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"M5_OUTPUT_DIR": folder}):
            self.fixture(folder)
            app = AppTest.from_file(str(APP), default_timeout=20).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get("arrow_vega_lite_chart")), 4)
            self.assertEqual(app.metric[2].value, "Chưa biết")
            app.sidebar.selectbox[2].select("item2")
            app.sidebar.selectbox[3].select("validation").run()
            self.assertFalse(app.exception)
            self.assertTrue((app.dataframe[0].value.item_id == "item2").all())
            app.sidebar.selectbox[1].select("FOODS").run()
            self.assertFalse(app.exception)
            app.sidebar.selectbox[0].select("B").run()
            self.assertFalse(app.exception)
            self.assertIn("Chưa có dự báo", app.info[0].value)
            self.assertEqual(len(app.get("arrow_vega_lite_chart")), 2)

    def test_missing_results_display_actionable_error(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"M5_OUTPUT_DIR": folder}):
            app = AppTest.from_file(str(APP)).run()
            self.assertFalse(app.exception)
            self.assertIn("Không đọc được kết quả", app.error[0].value)

    def test_date_filter_updates_sales_without_changing_evaluation(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"M5_OUTPUT_DIR": folder}):
            self.fixture(folder)
            path = Path(folder) / "analysis/daily_category_store.csv"
            daily = pd.read_csv(path)
            later = daily.copy()
            later["date"] = "2020-01-02"
            later["units"] = 7
            pd.concat([daily, later]).to_csv(path, index=False)
            app = AppTest.from_file(str(APP), default_timeout=20).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, "9")
            original_comparison = app.dataframe[1].value.copy()
            app.sidebar.date_input[0].set_value((date(2020, 1, 2), date(2020, 1, 2))).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, "7")
            self.assertIn("không có lịch sử", app.info[0].value)
            pd.testing.assert_frame_equal(app.dataframe[1].value, original_comparison)
            app.sidebar.date_input[0].set_value((date(2020, 1, 1),)).run()
            self.assertFalse(app.exception)
            self.assertIn("Chọn đủ ngày", app.info[0].value)

    def test_reject_incomplete_or_different_sources_and_preserve_unknown_revenue(self):
        with tempfile.TemporaryDirectory() as folder:
            self.fixture(folder)
            daily, *_ = dashboard.load_data(folder)
            self.assertTrue(pd.isna(dashboard.sales_summary(daily, "A", "Tất cả").revenue_known.iloc[0]))
            path = Path(folder) / "forecast/forecast_report.json"
            for report in ({"status": "failed"}, {"status": "success", "input": "other"}):
                path.write_text(json.dumps(report))
                with self.assertRaises(ValueError):
                    dashboard.load_data(folder)


if __name__ == "__main__":
    unittest.main()
