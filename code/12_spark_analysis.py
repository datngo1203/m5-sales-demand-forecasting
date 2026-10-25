"""Aggregate all handed-over Parquet rows with Spark; export small local CSVs."""

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import time
from urllib.parse import urlsplit
from urllib.request import url2pathname

from pyspark.sql import SparkSession, functions as F, types as T

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["date", "cat_id", "store_id"]
METRICS = ["rows", "units", "priced_rows", "priced_units", "revenue_known"]
REQUIRED = {"item_id", *KEYS, "demand", "sell_price"}


def input_uri(value):
    if value.startswith(("hdfs://", "file://")):
        return value
    return Path(value).resolve().as_uri()


def create_spark(master="local[2]", memory="2g"):
    return (SparkSession.builder.appName("M5-step2-sales-analysis")
            .master(master).config("spark.driver.memory", memory)
            .config("spark.sql.shuffle.partitions", "16")
            .config("spark.ui.enabled", "false")
            .getOrCreate())


def parquet_paths(uri):
    if uri.startswith("hdfs://"):
        return [uri]
    parsed = urlsplit(uri)
    local = Path(url2pathname((f"//{parsed.netloc}" if parsed.netloc else "") + parsed.path))
    # Windows Hadoop directory listing needs native DLLs; enumerate local files in Python.
    files = sorted(local.rglob("*.parquet")) if local.is_dir() else [local]
    if not files or any(not path.is_file() for path in files):
        raise ValueError(f"No Parquet files found: {local}")
    return [path.resolve().as_uri() for path in files]


def prepare(df):
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    schema = {field.name: field.dataType for field in df.schema}
    if not isinstance(schema["date"], T.DateType):
        raise ValueError("date must have Parquet DATE type")
    for name in ("demand", "sell_price"):
        if not isinstance(schema[name], T.NumericType):
            raise ValueError(f"{name} must be numeric")
    invalid = F.col("date").isNull()
    for name in ("item_id", "cat_id", "store_id"):
        invalid = invalid | F.col(name).isNull() | (F.trim(F.col(name)) == "")
    demand = F.col("demand").cast("double")
    invalid = (invalid | demand.isNull() | F.isnan(demand)
               | (F.abs(demand) == float("inf")) | (demand < 0)
               | (demand != F.floor(demand)))
    price = F.col("sell_price")
    priced = (price.isNotNull() & ~F.isnan(price)
              & (F.abs(price) != float("inf")) & (price >= 0))
    return df.select("item_id", *KEYS, "demand", "sell_price").withColumn(
        "_invalid", invalid).withColumn("_priced", priced)


def validate(df):
    quality = df.agg(F.count("*").alias("rows"),
                     F.sum(F.col("_invalid").cast("long")).alias("invalid_rows"),
                     F.sum((~F.col("_priced")).cast("long")).alias("unpriced_rows"),
                     F.min("date").alias("date_min"),
                     F.max("date").alias("date_max")).first().asDict()
    if not quality["rows"]:
        raise ValueError("Dataset contains no rows")
    if quality["invalid_rows"]:
        raise ValueError(f"Invalid date/key/demand: {quality['invalid_rows']} rows")
    return quality


def aggregate_detail(df):
    return df.groupBy(*KEYS).agg(
        F.count("*").alias("rows"),
        F.sum("demand").alias("units"),
        F.sum(F.col("_priced").cast("long")).alias("priced_rows"),
        F.sum(F.when(F.col("_priced"), F.col("demand")).otherwise(0)).alias("priced_units"),
        F.sum(F.when(F.col("_priced"), F.col("demand") * F.col("sell_price"))).alias("revenue_known"))


def rollup(detail, keys):
    return detail.groupBy(*keys).agg(*(F.sum(name).alias(name) for name in METRICS))


def with_coverage(df):
    return (df.withColumn("price_row_coverage", F.col("priced_rows") / F.col("rows"))
            .withColumn("price_unit_coverage", F.when(F.col("units") > 0,
                        F.col("priced_units") / F.col("units"))))


def write_csv(df, path, keys):
    df = with_coverage(df).orderBy(*keys)
    count = 0
    # Only aggregated rows cross to Python; no raw-data collect or Python UDF.
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(df.columns)
        for row in df.toLocalIterator():
            writer.writerow(row)
            count += 1
    return count


def run(spark, source, output):
    started = time.perf_counter()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Remove the old success report before attempting a rerun.
    (output / "analysis_report.json").unlink(missing_ok=True)
    uri = input_uri(source)
    df = prepare(spark.read.parquet(*parquet_paths(uri)))
    quality = validate(df)
    detail = aggregate_detail(df).cache()
    try:
        tables = {"daily_category_store": (detail, KEYS),
                  "daily_sales": (rollup(detail, ["date"]), ["date"]),
                  "category_sales": (rollup(detail, ["cat_id"]), ["cat_id"]),
                  "store_sales": (rollup(detail, ["store_id"]), ["store_id"])}
        counts = {name: write_csv(table, output / f"{name}.csv", keys)
                  for name, (table, keys) in tables.items()}
        totals = with_coverage(rollup(detail, [])).first().asDict()
        if totals["rows"] != quality["rows"]:
            raise AssertionError("Aggregated row count does not match input")
        report = {
            "status": "success", "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "input": uri, "input_mode": "hdfs" if uri.startswith("hdfs://") else "local",
            "quality": quality, "totals": totals, "output_rows": counts,
            "seconds": round(time.perf_counter() - started, 2),
            "environment": {"python": platform.python_version(), "spark": spark.version,
                            "java": spark.sparkContext._jvm.java.lang.System.getProperty("java.version"),
                            "master": spark.sparkContext.master},
            "notes": ["revenue_known = sum(demand * sell_price) for finite nonnegative prices only",
                      "Missing/invalid prices remain unknown; no zero fill or future price imputation",
                      "Coverage denominators: all rows and all sold units; zero units gives null unit coverage",
                      "Input rows are preserved; duplicate item/store/date keys are not checked or removed",
                      "HDFS is verified only if input_mode is hdfs; output files are local"]}
        (output / "analysis_report.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8")
        return report
    finally:
        detail.unpersist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(ROOT / "GuiDat/data/processed_m5"))
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/analysis")
    parser.add_argument("--master", default="local[2]")
    parser.add_argument("--driver-memory", default="2g")
    args = parser.parse_args()
    spark = create_spark(args.master, args.driver_memory)
    spark.sparkContext.setLogLevel("WARN")
    try:
        print(json.dumps(run(spark, args.input, args.output), indent=2, default=str))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
