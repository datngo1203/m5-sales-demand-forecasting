from datetime import timedelta
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

spec = importlib.util.spec_from_file_location("v2_panel", Path(__file__).resolve().parents[1] / "code/v2_panel.py")
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


class PanelTests(unittest.TestCase):
    def test_rank_and_post_cutoff_mutation(self):
        dates = [panel.SELECTION_DATE + timedelta(days=i) for i in range(-399, 41)]
        values = np.ones((22, len(dates)))
        values[0, :150] = 100  # Historic bestseller, but inactive just before selection.
        values[0, 372:400] = 0
        values[1, 218:400] = 5
        items = [f"item{i:02}" for i in range(22)]
        stats = panel.selection_stats(values, dates, items)
        recent = panel.rank_panel(stats, "recent")
        legacy = panel.rank_panel(stats, "legacy")
        self.assertEqual(recent[0]["item_id"], "item01")
        self.assertEqual(legacy[0]["item_id"], "item00")
        self.assertNotIn("item00", [r["item_id"] for r in recent])
        changed = values.copy()
        changed[:, 400:] = 1e9
        self.assertEqual(stats, panel.selection_stats(changed, dates, items))
        for name in ("legacy", "recent"):
            self.assertEqual(panel.rank_panel(stats, name),
                             panel.rank_panel(panel.selection_stats(changed, dates, items), name))
        with self.assertRaises(ValueError):
            panel.rank_panel(stats[:10], "recent")

    def test_spark_panel_matches_pure_aggregate_and_ignores_future(self):
        analysis_spec = importlib.util.spec_from_file_location(
            "analysis", Path(__file__).resolve().parents[1] / "code/12_spark_analysis.py")
        analysis = importlib.util.module_from_spec(analysis_spec)
        analysis_spec.loader.exec_module(analysis)
        spark = analysis.create_spark()
        spark.sparkContext.setLogLevel("ERROR")
        try:
            dates = [panel.SELECTION_DATE + timedelta(days=i) for i in range(-189, 6)]
            items = [f"i{i:02}" for i in range(21)]
            values = np.asarray([[i + 1 for _ in dates] for i in range(21)], dtype=float)
            values[20, 162:190] = 0
            expected = panel.selection_stats(values, dates, items)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "data.parquet"
                for mutation in (False, True):
                    rows = [{"date": day, "item_id": item, "cat_id": "FOODS", "store_id": "S",
                             "sell_price": 1., "demand": 10**9 if mutation and day > panel.SELECTION_DATE
                             else int(values[i, t])}
                            for i, item in enumerate(items) for t, day in enumerate(dates)]
                    pq.write_table(pa.Table.from_pylist(rows), path)
                    actual = panel.load_panels(spark, str(path), "S")
                    for name in ("recent", "legacy"):
                        self.assertEqual(actual[name], panel.rank_panel(expected, name))
        finally:
            spark.stop()


if __name__ == "__main__":
    unittest.main()
