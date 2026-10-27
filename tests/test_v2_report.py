import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("v2_report", ROOT / "scripts/report_forecast_v2.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    def test_seed_aggregation_groups_and_all_horizons(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            folder = Path(temp)
            actual = np.ones((13, 20, 28))
            known = np.ones((13, 20, 28)) * 2
            forecast = np.ones((13, 3, 20, 28)) * 3
            for store in ("CA_1", "CA_2"):
                for panel in report.PANELS:
                    path = folder / store / panel
                    path.mkdir(parents=True)
                    report.dump(path / "panel.json", {"store": store, "panel": panel,
                        "selected": [{"item_id": f"item{i:02}"} for i in range(20)]})
                    np.savez(path / "validation_predictions.npz", actual=actual, known=known,
                             flags=np.zeros(13,dtype=bool), **{name:forecast for name in report.MODELS})
                    np.savez(path / "test_predictions.npz", actual=actual[0], known=known[0],
                             **{name:forecast[0] for name in (*report.MODELS,"v2_frozen")})
            frozen={"step2_permitted":False,"gates":{p:{"wins":8,"rf_score":2.,"direct_score":2.,
                    "mae_ratio":1.,"passed":False} for p in report.PANELS},
                    "panels":{p:{"choice":"random_forest"} for p in report.PANELS}}
            (folder/"test_complete.json").write_text("{}")
            args=["report_forecast_v2.py","--output",str(folder),"--docs",str(folder/"docs")]
            with patch.object(sys,"argv",args), patch.object(report,"verify_frozen",return_value=frozen):
                report.main()
            with (folder/"docs/V2_METRICS.csv").open() as stream:
                metrics=list(csv.DictReader(stream))
            self.assertEqual(len(metrics),120)
            self.assertTrue(all(float(r["mae"])==2 for r in metrics))
            self.assertTrue(all(float(r["normalized_rmse"])==1 for r in metrics))
            with (folder/"docs/V2_BIAS_BY_H.csv").open() as stream:
                bias=list(csv.DictReader(stream))
            subset=[r for r in bias if r["store"]=="CA_1" and r["panel"]=="recent" and
                    r["split"]=="validation" and r["group"]=="all" and
                    r["seed"]=="42" and r["model"]=="random_forest"]
            self.assertEqual({int(r["horizon"]) for r in subset},set(range(1,29)))
            self.assertEqual(sum(float(r["bias_units"]) for r in subset),13*20*28*2)
            text=(folder/"docs/V2_RESULTS.md").read_text(encoding="utf-8")
            self.assertIn("Cổng không đạt",text)
            self.assertIn("13 origin không độc lập",text)
            self.assertIn("CA_2",text)


if __name__ == "__main__":
    unittest.main()
