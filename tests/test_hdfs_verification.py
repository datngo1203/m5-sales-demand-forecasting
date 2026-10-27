import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_hdfs", ROOT / "scripts/verify_hdfs.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HDFSVerificationTests(unittest.TestCase):
    def test_checks_all_tables_and_rejects_changed_values_or_local_only_run(self):
        with tempfile.TemporaryDirectory() as folder:
            old, new = Path(folder) / "old", Path(folder) / "new"
            old.mkdir(); new.mkdir()
            for path, mode in ((old, "local"), (new, "hdfs")):
                report = {"status": "success", "input_mode": mode, "input": mode,
                          "quality": {"rows": 2}, "output_rows": {}, "totals": {}, "environment": {}}
                (path / "analysis_report.json").write_text(json.dumps(report))
                for name, keys in module.TABLES.items():
                    pd.DataFrame([{**{key: "A" for key in keys}, "units": 3.5}]).to_csv(path / f"{name}.csv", index=False)
            self.assertEqual(len(module.verify(old, new)["tables_checked"]), 4)
            target = new / "store_sales.csv"
            data = pd.read_csv(target); data["units"] = 4
            data.to_csv(target, index=False)
            with self.assertRaises(AssertionError):
                module.verify(old, new)
            report["input_mode"] = "local"
            (new / "analysis_report.json").write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                module.verify(old, new)
