"""Inspect metadata and hash handed-over Parquet without loading it all into RAM."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"item_id", "store_id", "cat_id", "state_id", "date", "demand", "sell_price"}


def inspect_input(directory):
    directory = Path(directory)
    files = sorted(directory.glob("*.parquet"))
    if not files:
        raise ValueError(f"No Parquet files found: {directory}")
    rows = 0
    first_schema = None
    sample = []
    manifest = []
    for path in files:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        manifest.append({"name": path.name, "bytes": path.stat().st_size, "sha256": digest})
        with pq.ParquetFile(path) as part:
            schema = part.schema_arrow
            missing = REQUIRED - set(schema.names)
            if missing:
                raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
            if first_schema is None:
                first_schema = schema
                sample = next(part.iter_batches(batch_size=5), None)
                sample = sample.to_pylist() if sample is not None else []
            elif not schema.equals(first_schema, check_metadata=False):
                raise ValueError(f"{path.name}: inconsistent schema")
            rows += part.metadata.num_rows
    if rows == 0:
        raise ValueError("Dataset contains no rows")
    return {
        "input": str(directory.resolve()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "files": manifest,
        "part_files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "rows_from_all_footers": rows,
        "columns": [{"name": field.name, "type": str(field.type)} for field in first_schema],
        "success_marker": (directory / "_SUCCESS").is_file(),
        "first_part_sample": sample,
        "forecasting_features_in_archive": (directory.parent / "forecasting_features").is_dir(),
        "check_scope": "SHA-256 of all file bytes, all footers and 5 sample rows; not a full quality scan",
    }


def package_versions():
    result = {}
    for name in ("pyarrow", "pyspark", "numpy", "scikit-learn", "pandas", "streamlit"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "GuiDat/data/processed_m5")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/input_inventory.json")
    args = parser.parse_args()
    args.output.unlink(missing_ok=True)
    result = inspect_input(args.input)
    result["environment"] = {
        "python": sys.version,
        "platform": sys.platform,
        "packages": package_versions(),
        "pyspark_installed": importlib.util.find_spec("pyspark") is not None,
        "java_on_path": shutil.which("java"),
        "java_home": os.environ.get("JAVA_HOME"),
        "hadoop_on_path": shutil.which("hadoop"),
        "hdfs_service": "not tested",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"PASS input metadata: {result['part_files']} files, {result['rows_from_all_footers']:,} rows")
    print(f"Schema: {len(result['columns'])} columns; _SUCCESS: {result['success_marker']}")
    print(f"Environment: {result['environment']}")
    print(f"Report: {args.output.resolve()}")


if __name__ == "__main__":
    main()
