import importlib.util
import hashlib
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
                for model in ("seasonal_naive", "random_forest", "selected_forecast"):
                    predictions.append({"date": "2020-01-02", "origin_date": "2020-01-01",
                                        "store_id": "A", "item_id": item, "split": split,
                                        "model": model, "prediction": 3, "actual": 2})
                    metrics.append({"store_id": "A", "item_id": item, "split": split,
                                    "model": model, "observations": 1, "mae": 1, "rmse": 1,
                                    "actual_units": 2, "predicted_units": 3, "bias_units": 1, "bias_pct": 50})
        pd.DataFrame(predictions).to_csv(folder / "forecast/predictions.csv", index=False)
        pd.DataFrame(metrics).to_csv(folder / "forecast/metrics.csv", index=False)

    def open_app(self, folder):
        return AppTest.from_file(str(APP), default_timeout=25).run()

    def test_forecast_default_scope_hidden_actual_and_weekly_export(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"M5_OUTPUT_DIR": folder}):
            self.fixture(folder)
            app = self.open_app(folder)
            self.assertFalse(app.exception)
            self.assertEqual(app.sidebar.radio[0].value, "Dự báo sản phẩm")
            self.assertEqual(app.selectbox[0].options, ["A"])
            self.assertFalse(app.date_input)
            self.assertFalse(app.checkbox[0].value)
            spec = json.loads(app.get("arrow_vega_lite_chart")[0].proto.spec)
            self.assertEqual(spec["layer"][1]["encoding"]["color"]["scale"]["domain"], ["Lịch sử", "Dự báo cuối"])
            self.assertEqual(app.metric[0].value, "3,0")
            self.assertEqual(app.metric[2].value, "Chưa đủ dữ liệu")
            self.assertIn("Mô phỏng dự báo trong quá khứ", app.info[0].value)
            self.assertEqual(app.dataframe[0].value["Dự báo cuối"].sum(), 3)
            self.assertEqual(len(app.get("download_button")), 1)
            app.checkbox[0].check().run()
            spec = json.loads(app.get("arrow_vega_lite_chart")[0].proto.spec)
            self.assertIn("Thực tế", spec["layer"][1]["encoding"]["color"]["scale"]["domain"])
            app.selectbox[2].select("item2").run()
            app.selectbox[1].select("validation").run()
            self.assertFalse(app.exception)
            self.assertIn("đã tham gia lựa chọn", " ".join(x.value for x in app.caption))

    def test_comparison_checkboxes_control_series_and_handle_empty_selection(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"M5_OUTPUT_DIR": folder}):
            self.fixture(folder)
            app = self.open_app(folder)
            self.assertTrue(app.checkbox(key="compare_selected_forecast").value)
            self.assertFalse(app.checkbox(key="compare_random_forest").value)
            self.assertNotIn("compare_weekday_mean4", [c.key for c in app.checkbox])
            app.checkbox(key="compare_selected_forecast").uncheck().run()
            self.assertFalse(app.exception)
            self.assertIn("Tích ít nhất", " ".join(x.value for x in app.info))
            self.assertEqual(len(app.get("arrow_vega_lite_chart")), 2)
            chart = json.loads(app.get("arrow_vega_lite_chart")[0].proto.spec)
            self.assertEqual(chart["layer"][1]["encoding"]["color"]["scale"]["domain"], ["Lịch sử"])
            self.assertNotIn("So sánh với các cách dự báo khác", [x.label for x in app.expander])
            app.checkbox(key="compare_random_forest").check().run()
            self.assertFalse(app.exception)
            chart = json.loads(app.get("arrow_vega_lite_chart")[0].proto.spec)
            self.assertEqual(chart["layer"][1]["encoding"]["color"]["scale"]["domain"], ["Lịch sử", "Random Forest (RF)"])
            self.assertEqual(app.metric[0].value, "3,0")
            self.assertEqual(app.dataframe[0].value["Dự báo cuối"].sum(), 3)
            app.checkbox[0].check().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get("arrow_vega_lite_chart")), 2)
            chart = json.loads(app.get("arrow_vega_lite_chart")[0].proto.spec)
            self.assertEqual(chart["layer"][1]["encoding"]["color"]["scale"]["domain"], ["Lịch sử", "Random Forest (RF)", "Thực tế"])
            app.checkbox(key="compare_random_forest").uncheck().run()
            chart = json.loads(app.get("arrow_vega_lite_chart")[0].proto.spec)
            self.assertEqual(chart["layer"][1]["encoding"]["color"]["scale"]["domain"], ["Lịch sử", "Thực tế"])

    def test_sales_filters_do_not_change_fixed_forecast(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"M5_OUTPUT_DIR": folder}):
            self.fixture(folder)
            path = Path(folder) / "analysis/daily_category_store.csv"
            daily = pd.read_csv(path)
            later = daily.copy()
            later["date"], later["units"] = "2020-01-02", 7
            pd.concat([daily, later]).to_csv(path, index=False)
            app = self.open_app(folder)
            forecast = app.dataframe[0].value.copy()
            app.sidebar.radio[0].set_value("Tổng quan bán hàng").run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, "9")
            self.assertEqual(app.metric[1].value, "Chưa biết")
            app.date_input[0].set_value((date(2020, 1, 2), date(2020, 1, 2))).run()
            self.assertEqual(app.metric[0].value, "7")
            self.assertIn("5 đơn vị", app.metric[0].delta)
            app.selectbox[0].select("B").run()
            self.assertFalse(app.exception)
            app.selectbox[1].select("FOODS").run()
            app.date_input[0].set_value((date(2020, 1, 1),)).run()
            self.assertIn("Chọn đủ ngày", app.info[0].value)
            app.sidebar.radio[0].set_value("Dự báo sản phẩm").run()
            self.assertEqual(app.selectbox[0].options, ["A"])
            pd.testing.assert_frame_equal(app.dataframe[0].value, forecast)

    def test_missing_results_display_actionable_error(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"M5_OUTPUT_DIR": folder}):
            app = self.open_app(folder)
            self.assertFalse(app.exception)
            self.assertIn("Không đọc được kết quả", app.error[0].value)

    def test_v2_blend_explanation_and_v1_are_compatible(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"M5_OUTPUT_DIR": folder}):
            self.fixture(folder)
            path = Path(folder) / "forecast/forecast_report.json"
            report = json.loads(path.read_text())
            report.update(pipeline_version="v2", selected_candidate="blend", published_seed=42)
            path.write_text(json.dumps(report), encoding="utf-8")
            target = Path(folder) / "forecast/predictions.csv"
            data = pd.read_csv(target)
            extra = data[data.model == "seasonal_naive"].copy()
            extra["model"] = "weekday_mean4"
            pd.concat([data, extra]).to_csv(target, index=False)
            app = self.open_app(folder)
            self.assertFalse(app.exception)
            self.assertIn("RF đoán 14", " ".join(x.value for x in app.markdown))
            self.assertFalse(app.checkbox(key="compare_weekday_mean4").value)
            app.checkbox(key="compare_weekday_mean4").check().run()
            chart = json.loads(app.get("arrow_vega_lite_chart")[0].proto.spec)
            self.assertIn("Trung bình 4 tuần cùng thứ", chart["layer"][1]["encoding"]["color"]["scale"]["domain"])
            self.assertFalse(app.json)
            app.sidebar.radio[0].set_value("Kiểm tra độ tin cậy").run()
            self.assertFalse(app.exception)
            self.assertIn("Trung bình 4 tuần cùng thứ", app.dataframe[0].value["Cách dự báo"].tolist())

    def test_reliability_units_bias_and_optional_research(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"M5_OUTPUT_DIR": folder}):
            self.fixture(folder)
            app = self.open_app(folder)
            app.sidebar.radio[0].set_value("Kiểm tra độ tin cậy").run()
            self.assertFalse(app.exception)
            self.assertFalse(app.date_input)
            self.assertEqual(app.metric[0].value, "1,00")
            self.assertEqual(app.metric[1].value, "2,0")
            self.assertEqual(app.dataframe[1].value["Sản phẩm"].tolist(), ["item1", "item2"])
            self.assertIn("Không có sản phẩm dự báo thiếu", " ".join(x.value for x in app.info))
            with patch.object(dashboard, "ROOT", Path(folder)):
                # Reruns import the module afresh; exercise the optional reader directly instead.
                with patch.object(dashboard.st, "info") as info:
                    dashboard.research_results()
                    self.assertIn("Chưa đọc được", info.call_args.args[0])
                research_dir = Path(folder) / "resources"
                research_dir.mkdir(parents=True)
                # Synthetic fixture: tests must not require exported research results.
                research = pd.DataFrame([
                    {"store": store, "panel": panel, "model": model,
                     "mae": 1., "rmse": 2., "bias_pct": -3., "normalized_rmse": .5}
                    for store in ("CA_3", "TX_1", "WI_1") for panel in ("recent", "legacy")
                    for model in ("blend", "random_forest", "weekday_mean4", "seasonal_naive")])
                research.to_csv(research_dir / "v3_test_metrics.csv", index=False)
                with patch.object(dashboard.st, "dataframe") as display:
                    dashboard.research_results()
                    table = display.call_args.args[0]
                    self.assertEqual(set(table["Cửa hàng"]), {"CA_3", "TX_1", "WI_1"})
                    self.assertEqual(len(table), 24)

    def test_previous_period_requires_complete_equal_calendar_windows(self):
        summary = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=6), "units": [0, 2, 3, 4, 5, 6]})
        before = dashboard.previous_period(summary, pd.Timestamp("2020-01-04"), pd.Timestamp("2020-01-06"))
        self.assertEqual(before.units.sum(), 5)
        self.assertIsNone(dashboard.previous_period(summary.iloc[1:], pd.Timestamp("2020-01-04"), pd.Timestamp("2020-01-06")))
        self.assertIsNone(dashboard.previous_period(summary, pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-03")))

    def test_planning_gap_handles_sufficient_stock_and_rejects_invalid_inputs(self):
        self.assertEqual(dashboard.supply_gap(100.5, 30, 20), 50.5)
        self.assertEqual(dashboard.supply_gap(100, 110, 20), 0)
        for value in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                dashboard.supply_gap(100, value, 0)

    def test_planning_scenario_uses_forecast_only_and_handles_incomplete_period(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"M5_OUTPUT_DIR": folder}):
            self.fixture(folder)
            app = self.open_app(folder)
            self.assertIn("Chưa đủ 28 ngày", " ".join(x.value for x in app.info))
            target = Path(folder) / "forecast/predictions.csv"
            data = pd.read_csv(target)
            full = pd.concat([data.assign(date=str(day.date())) for day in pd.date_range("2020-01-02", periods=28)])
            full.to_csv(target, index=False)
            app = self.open_app(folder)
            app.checkbox(key="planning_enabled").check().run()
            app.number_input(key="planning_stock").set_value(20.).run()
            app.number_input(key="planning_incoming").set_value(10.).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[-1].value, "54,0")
            full["actual"] = 1e9
            full.to_csv(target, index=False)
            app.run()
            self.assertEqual(app.metric[-1].value, "54,0")
            app.selectbox[2].select("item2").run()
            self.assertFalse(app.checkbox(key="planning_enabled").value)
            app.checkbox(key="planning_enabled").check().run()
            self.assertEqual(app.number_input(key="planning_stock").value, 0)
            self.assertEqual(app.number_input(key="planning_incoming").value, 0)

    def test_hdfs_badge_requires_matching_verified_report(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(dashboard.hdfs_verification(folder))
            path = Path(folder) / "analysis_hdfs"
            path.mkdir()
            report = path / "analysis_report.json"
            report.write_text(json.dumps({"status": "success", "input_mode": "hdfs"}), encoding="utf-8")
            proof = {"status": "verified", "quality": {"rows": 42},
                     "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest()}
            (path / "verification.json").write_text(json.dumps(proof), encoding="utf-8")
            self.assertEqual(dashboard.hdfs_verification(folder)["quality"]["rows"], 42)
            report.write_text('{"status":"success","input_mode":"local"}', encoding="utf-8")
            self.assertIsNone(dashboard.hdfs_verification(folder))

    def test_forecast_weeks_are_relative_to_origin_and_do_not_round_totals(self):
        data = pd.DataFrame({"date": pd.date_range("2020-01-02", periods=28), "model": "selected_forecast",
                             "prediction": 1.25, "actual": 1})
        comparison, weekly = dashboard.forecast_tables(data)
        self.assertEqual(weekly["Dự báo cuối"].tolist(), [8.75] * 4)
        self.assertEqual(weekly["Dự báo cuối"].sum(), comparison.selected_forecast.sum())

    def test_evaluation_positive_negative_bias_and_zero_actual(self):
        data = pd.DataFrame({"item_id": ["a", "b", "c"], "model": "selected_forecast",
                             "prediction": [4, 0, 2], "actual": [2, 3, 0]})
        summary, items = dashboard.evaluation_tables(data)
        self.assertAlmostEqual(summary.mae.iloc[0], 7 / 3)
        self.assertEqual(summary.bias.iloc[0], 1)
        self.assertEqual(items.loc["b", "bias"], -3)
        data["actual"] = 0
        summary, _ = dashboard.evaluation_tables(data)
        self.assertTrue(pd.isna(summary.bias_pct.iloc[0]))

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
