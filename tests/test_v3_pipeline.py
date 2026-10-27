import csv
from datetime import date,timedelta
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v3_pipeline",ROOT/"code/15_forecasting_v3.py")
pipeline=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class PipelineTests(unittest.TestCase):
    def fixture(self):
        end=pipeline.v3.v2.TEST_ORIGIN
        dates=[date(2011,1,29)+timedelta(days=i) for i in range((end-date(2011,1,29)).days+1)]
        return {"dates":dates,"history":np.ones((2,len(dates))),"actual":np.ones((2,28))*3,
            "selected":[{"item_id":f"i{i}","train_units":100} for i in range(2)],"reused":True,
            "validation":{"actual":np.ones((13,2,28)),"known":np.ones((13,2,28)),
                "random_forest":np.ones((13,3,2,28))*4,"weekday_mean4":np.ones((13,3,2,28))*2,
                "seasonal_naive":np.ones((13,3,2,28))*2},
            "test":{"random_forest":np.ones((3,2,28))*4,"weekday_mean4":np.ones((3,2,28))*2,
                    "seasonal_naive":np.ones((3,2,28))*2}}

    def test_cached_run_never_fits_and_preserves_dashboard_columns(self):
        bundle=self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(pipeline,"cached_bundle",return_value=bundle), patch.object(pipeline,"rf_fit",side_effect=AssertionError("must reuse")):
                existing=pipeline.obtain_bundle(Path(folder),"S","recent",Path(folder)/"cache")
                report=pipeline.export(existing,folder,folder,"S","blend")
            self.assertTrue(report["reused_predictions"])
            self.assertEqual(report["k_seed42"],.25)
            self.assertEqual(report["selected_candidate"],"blend")
            with (Path(folder)/"predictions.csv").open() as stream:
                reader=csv.DictReader(stream); rows=list(reader)
                self.assertEqual(reader.fieldnames,["split","model","item_id","store_id","origin_date","date","horizon","actual","prediction"])
            self.assertEqual(len(rows),448)
            self.assertTrue(all(float(r["prediction"])==3 for r in rows if r["model"]=="selected_forecast"))
            with (Path(folder)/"metrics.csv").open() as stream:
                reader=csv.DictReader(stream); metrics=list(reader)
                self.assertEqual(reader.fieldnames,["split","model","item_id","store_id","observations","mae","rmse","actual_units","predicted_units","bias_units","bias_pct"])
            selected=next(r for r in metrics if r["split"]=="test" and r["model"]=="selected_forecast" and r["item_id"]=="ALL")
            self.assertEqual(float(selected["mae"]),0)
            # Modifying test targets changes exported metrics, never k or predictions.
            bundle["actual"][:]=1e9
            again=pipeline.export(bundle,folder,folder,"S","blend")
            self.assertEqual(again["k_seed42"],.25)
            self.assertEqual(again["selected_models"],report["selected_models"])

    def test_pipeline_default_and_v1_escape_hatch(self):
        text=(ROOT/"run_pipeline.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$V1",text)
        self.assertIn("if ($V1) { '13_forecasting_v1.py' } else { '15_forecasting_v3.py' }",text)
        self.assertEqual((ROOT/"code/13_forecasting.py").read_bytes(),(ROOT/"code/13_forecasting_v1.py").read_bytes())

    def test_cli_uses_runtime_config_without_research_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            (folder/"config").mkdir()
            (folder/"config/forecast.json").write_text(json.dumps({"enabled":True,"selected_candidate":"blend"}))
            with patch.object(pipeline,"ROOT",folder), patch.object(sys,"argv",["forecast"]), \
                 patch.object(pipeline,"obtain_bundle",return_value=self.fixture()) as obtain, \
                 patch.object(pipeline,"export",return_value={"reused_predictions":True}) as export:
                pipeline.main()
                obtain.assert_called_once()
                self.assertEqual(export.call_args.args[-1],"blend")
            self.assertFalse((folder/"docs/review").exists())

    def test_cli_rejects_disabled_or_unknown_config_before_training(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            (folder/"config").mkdir()
            with patch.object(pipeline,"ROOT",folder), patch.object(sys,"argv",["forecast"]), \
                 patch.object(pipeline,"obtain_bundle") as obtain:
                for settings in ({"enabled":False}, {"enabled":"true","selected_candidate":"blend"},
                                 {"enabled":True,"selected_candidate":"unknown"}, []):
                    (folder/"config/forecast.json").write_text(json.dumps(settings))
                    with self.assertRaises(ValueError):
                        pipeline.main()
                obtain.assert_not_called()

    def test_new_store_without_v2_outputs_fits_once_then_reuses_own_cache(self):
        bundle=self.fixture()
        dates=bundle["dates"]; history=bundle["history"]
        days=dates+[dates[-1]+timedelta(days=h) for h in range(1,29)]
        full=np.concatenate([history,bundle["actual"]],axis=1)
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder); source=folder/"data"; source.mkdir()
            predictions={"random_forest":np.ones((2,28))*4,"weekday_mean4":np.ones((2,28))*2,
                         "seasonal_naive":np.ones((2,28))*2}
            with patch.object(pipeline,"ROOT",folder),patch.object(pipeline,"spark_session") as spark, \
                 patch.object(pipeline.v2_panel,"load_panels",return_value={"recent":bundle["selected"]}), \
                 patch.object(pipeline.v2_panel,"load_values",side_effect=[(dates,history),(days,full)]), \
                 patch.object(pipeline,"rf_fit",return_value=object()) as fit, \
                 patch.object(pipeline,"predict",return_value=predictions):
                first=pipeline.obtain_bundle(source,"NEW","recent",folder/"cache")
                self.assertEqual(fit.call_count,42)
                self.assertFalse(first["reused"])
                with patch.object(pipeline,"rf_fit",side_effect=AssertionError("repeat fit")):
                    second=pipeline.obtain_bundle(source,"NEW","recent",folder/"cache")
                self.assertTrue(second["reused"])
                np.testing.assert_array_equal(first["test"]["random_forest"],second["test"]["random_forest"])
                self.assertEqual(pipeline.v3.estimate_k(second["validation"]["actual"],second["validation"]["random_forest"]),[.25]*3)


if __name__=="__main__": unittest.main()
