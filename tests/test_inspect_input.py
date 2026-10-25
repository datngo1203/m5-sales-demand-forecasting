import importlib.util
from pathlib import Path
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq


spec = importlib.util.spec_from_file_location("inspect_input", Path(__file__).resolve().parents[1] / "code/11_inspect_input.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InspectInputTests(unittest.TestCase):
    def test_counts_all_parts_and_rejects_missing_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            table = pa.table({name: [1, 2] for name in module.REQUIRED})
            pq.write_table(table, folder / "part-0.parquet")
            pq.write_table(table, folder / "part-1.parquet")
            result = module.inspect_input(folder)
            self.assertEqual(result["rows_from_all_footers"], 4)
            self.assertEqual(result["part_files"], 2)
            self.assertFalse(result["success_marker"])
            pq.write_table(pa.table({"demand": [1]}), folder / "part-2.parquet")
            with self.assertRaisesRegex(ValueError, "missing columns"):
                module.inspect_input(folder)

    def test_empty_folder_and_inconsistent_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with self.assertRaisesRegex(ValueError, "No Parquet"):
                module.inspect_input(folder)
            pq.write_table(pa.table({name: [1] for name in module.REQUIRED}), folder / "part-0.parquet")
            pq.write_table(pa.table({name: ["x"] for name in module.REQUIRED}), folder / "part-1.parquet")
            with self.assertRaisesRegex(ValueError, "inconsistent schema"):
                module.inspect_input(folder)


if __name__ == "__main__":
    unittest.main()
