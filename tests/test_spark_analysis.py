import importlib.util
from datetime import date
from pathlib import Path
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

spec = importlib.util.spec_from_file_location(
    "spark_analysis", Path(__file__).resolve().parents[1] / "code/12_spark_analysis.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SparkAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = module.create_spark()
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def fixture(self, folder, demand=None):
        table = pa.table({
            "item_id": ["a", "b", "c", "d", "e", "f"],
            "date": [date(2020, 1, 1)] * 3 + [date(2020, 1, 2)] * 3,
            "cat_id": ["A"] * 3 + ["B"] * 3,
            "store_id": ["S1"] * 3 + ["S2"] * 3,
            "demand": demand if demand is not None else [2, 3, 0, 4, 1, 2],
            "sell_price": [2.5, None, 0., float("nan"), float("inf"), -1.]})
        path = Path(folder) / "input.parquet"
        pq.write_table(table, path)
        return path

    def test_real_spark_export_and_price_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            self.fixture(folder)
            report = module.run(self.spark, folder, Path(folder) / "out")
            totals = report["totals"]
            self.assertEqual(totals["rows"], 6)
            self.assertEqual(totals["units"], 12)
            self.assertEqual(totals["revenue_known"], 5.)
            self.assertAlmostEqual(totals["price_row_coverage"], 2 / 6)
            self.assertAlmostEqual(totals["price_unit_coverage"], 2 / 12)
            self.assertEqual(report["output_rows"]["daily_category_store"], 2)
            import csv
            with (Path(folder) / "out/category_sales.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[1]["revenue_known"], "")
            self.assertTrue((Path(folder) / "out/analysis_report.json").is_file())

    def test_rejects_invalid_demand_and_empty_input(self):
        with tempfile.TemporaryDirectory() as folder:
            df = module.prepare(self.spark.read.parquet(
                self.fixture(folder, [2, -3, 0, 4, 1, 2]).as_uri()))
            with self.assertRaisesRegex(ValueError, "Invalid date/key/demand"):
                module.validate(df)
            with self.assertRaisesRegex(ValueError, "no rows"):
                module.validate(df.limit(0))
            with self.assertRaisesRegex(ValueError, "Missing columns"):
                module.prepare(df.drop("store_id"))
            bad_key = df.withColumn("item_id", module.F.lit(None))
            with self.assertRaisesRegex(ValueError, "Invalid date/key/demand"):
                module.validate(module.prepare(bad_key))

    def test_zero_units_coverage_and_uri(self):
        with tempfile.TemporaryDirectory() as folder:
            df = module.prepare(self.spark.read.parquet(
                self.fixture(folder, [0] * 6).as_uri()))
            totals = module.with_coverage(module.rollup(module.aggregate_detail(df), [])).first()
            self.assertIsNone(totals.price_unit_coverage)
            self.assertEqual(totals.revenue_known, 0.)
        uri = "hdfs://localhost:9000/m5/processed_m5"
        self.assertEqual(module.input_uri(uri), uri)
        self.assertTrue(module.input_uri("GuiDat/data/processed_m5").startswith("file:///"))


if __name__ == "__main__":
    unittest.main()
