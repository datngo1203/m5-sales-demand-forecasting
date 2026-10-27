import importlib.util
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch
from datetime import date,timedelta

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"code"),str(ROOT/"scripts")]
import forecast_v3 as v3
import run_forecast_v3 as runner


class V3Tests(unittest.TestCase):
    def test_k_candidates_and_tie_order(self):
        actual=np.ones((13,2,28))
        rf=np.ones((13,3,2,28))*2
        ks=v3.estimate_k(actual,rf)
        self.assertEqual(ks,[.5]*3)
        pred=v3.candidates(rf,np.ones_like(rf),ks)
        np.testing.assert_array_equal(pred["blend"],1.5)
        np.testing.assert_array_equal(pred["rf_calibrated"],1)
        with self.assertRaises(ValueError): v3.estimate_k(actual,np.zeros_like(rf))
        fake={m:{"score":1.,"metrics":{"bias_pct":0.}} for m in v3.CANDIDATES}
        self.assertEqual(v3.select([fake]*4)["choice"],"weekday_mean4")
        bad={m:{"score":1.,"metrics":{"bias_pct":0.}} for m in v3.CANDIDATES}
        bad["weekday_mean4"]={"score":.1,"metrics":{"bias_pct":-100.}}
        self.assertEqual(v3.select([bad]*4)["choice"],"blend")

    def test_validation_only_and_group_scores(self):
        data={"actual":np.ones((13,2,28)),"known":np.ones((13,2,28)),
            "random_forest":np.ones((13,3,2,28))*2,"weekday_mean4":np.ones((13,3,2,28)),
            "seasonal_naive":np.ones((13,3,2,28))*3}
        ks,forecasts,rows,summary=v3.validation(data)
        self.assertEqual(summary["rf_calibrated"]["score"],0)
        # Unused external test labels are never an argument to calibration or selection.
        data["test_actual"]=np.ones((2,28))*1e9
        self.assertEqual(v3.validation(data)[0],ks)
        self.assertEqual(v3.validation(data)[3],summary)
        self.assertEqual(len(rows),13*3*5)

    def test_fresh_forecasts_ignore_future(self):
        dates=[date(2015,1,1)+timedelta(days=i) for i in range(450)]
        values=np.array([np.arange(450)%7,np.arange(450)%9],dtype=float)
        origin=dates[350]
        changed=values.copy(); changed[:,351:]=1e9
        rf=runner.rf_fit(values,dates,origin,42)
        # Keep exact causality checks independent of parallel tree-sum roundoff.
        rf.set_params(n_jobs=1)
        for name,pred in runner.predict(rf,values,dates,origin).items():
            np.testing.assert_array_equal(pred,runner.predict(rf,changed,dates,origin)[name])

    def test_gate_requires_both_panels_and_absolute_bias(self):
        rows=[]
        for store in ("A","B","C"):
            for panel in ("recent","legacy"):
                rows.extend([{"store":store,"panel":panel,"model":"random_forest","mae":10.,"bias_pct":5.},
                             {"store":store,"panel":panel,"model":"blend","mae":9.,"bias_pct":-4.}])
        self.assertTrue(v3.integration_gate(rows,"blend",["A","B","C"])["integrate"])
        for row in rows:
            if row["model"]=="blend" and row["store"] in ("A","B") and row["panel"]=="legacy":
                row["bias_pct"]=-6
        self.assertFalse(v3.integration_gate(rows,"blend",["A","B","C"])["integrate"])

    def test_fresh_test_guard_rejects_second_run_before_source_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            (path/"test_started.json").write_text("consumed")
            with patch.object(runner,"OUTPUT",path), patch.object(runner,"verify",return_value={"stores":[],"panels":[]}), patch.object(runner,"spark_session") as spark:
                with self.assertRaises(FileExistsError): runner.test()
            spark.assert_not_called()


if __name__=="__main__": unittest.main()
