import importlib.util
import hashlib
from pathlib import Path
from unittest.mock import patch
import sys
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
            self.assertEqual(result["status"], "success")
            self.assertEqual([row["name"] for row in result["files"]],
                             ["part-0.parquet", "part-1.parquet"])
            for row in result["files"]:
                data = (folder / row["name"]).read_bytes()
                self.assertEqual(row["bytes"], len(data))
                self.assertEqual(row["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(module.inspect_input(folder)["files"], result["files"])
            pq.write_table(pa.table({name: [3] for name in module.REQUIRED}), folder / "part-1.parquet")
            self.assertNotEqual(module.inspect_input(folder)["files"][1]["sha256"],
                                result["files"][1]["sha256"])
            pq.write_table(pa.table({"demand": [1]}), folder / "part-2.parquet")
            with self.assertRaisesRegex(ValueError, "missing columns"):
                module.inspect_input(folder)

    def test_failed_rerun_removes_old_success_and_records_versions(self):
        self.assertEqual(module.package_versions()["pyarrow"], pa.__version__)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inventory.json"
            output.write_text('{"status":"success"}', encoding="utf-8")
            with patch.object(sys, "argv", ["inspect", "--input", directory, "--output", str(output)]):
                with self.assertRaisesRegex(ValueError, "No Parquet"):
                    module.main()
            self.assertFalse(output.exists())

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
