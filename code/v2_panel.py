"""Select both V2 panels strictly at the fixed, pre-validation cutoff."""

from datetime import date, timedelta
import importlib.util
from pathlib import Path

import numpy as np
from pyspark.sql import functions as F

SELECTION_DATE = date(2015, 12, 6)
RECENT_DAYS = 26 * 7
LAST_DAYS = 28


def rank_panel(stats, panel, count=20):
    if panel not in ("legacy", "recent"):
        raise ValueError("panel must be legacy or recent")
    eligible = [r for r in stats if panel == "legacy" or r["last28_units"] > 0]
    field = "train_units" if panel == "legacy" else "recent_units"
    ranked = sorted(eligible, key=lambda r: (-r[field], r["item_id"]))[:count]
    if len(ranked) != count:
        raise ValueError(f"Need at least {count} eligible products")
    return [{**r, "rank": i + 1} for i, r in enumerate(ranked)]


def selection_stats(values, dates, items, cutoff=SELECTION_DATE):
    end = dates.index(cutoff) + 1
    if end < RECENT_DAYS:
        raise ValueError("Need 26 weeks before selection")
    known = values[:, :end]
    return [{"item_id": item, "train_units": float(known[i].sum()),
             "recent_units": float(known[i, -RECENT_DAYS:].sum()),
             "last28_units": float(known[i, -LAST_DAYS:].sum())} for i, item in enumerate(items)]


def load_panels(spark, source, store):
    spec = importlib.util.spec_from_file_location("v2_analysis", Path(__file__).with_name("12_spark_analysis.py"))
    analysis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analysis)
    # Filter before any action: neither panel ranking nor validation sees test demand.
    frame = spark.read.parquet(*analysis.parquet_paths(analysis.input_uri(source)))
    history = analysis.prepare(frame.filter((F.col("store_id") == store) &
                                           (F.col("date") <= F.lit(SELECTION_DATE))))
    analysis.validate(history)
    stats = history.groupBy("item_id").agg(
        F.sum("demand").alias("train_units"),
        F.sum(F.when(F.col("date") >= F.lit(SELECTION_DATE - timedelta(days=181)),
                     F.col("demand")).otherwise(0)).alias("recent_units"),
        F.sum(F.when(F.col("date") >= F.lit(SELECTION_DATE - timedelta(days=27)),
                     F.col("demand")).otherwise(0)).alias("last28_units"))
    rows = [r.asDict() for r in stats.collect()]
    panels = {name: rank_panel(rows, name) for name in ("recent", "legacy")}
    return panels


def load_values(spark, source, store, selected, end):
    spec = importlib.util.spec_from_file_location("v2_analysis", Path(__file__).with_name("12_spark_analysis.py"))
    analysis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analysis)
    frame = spark.read.parquet(*analysis.parquet_paths(analysis.input_uri(source)))
    items = [r["item_id"] for r in selected]
    history = analysis.prepare(frame.filter((F.col("store_id") == store) & F.col("item_id").isin(items) &
                                           (F.col("date") <= F.lit(end))))
    quality = analysis.validate(history)
    first = quality["date_min"]
    dates = [first + timedelta(days=i) for i in range((end - first).days + 1)]
    rows = history.select("item_id", "date", "demand").collect()
    lookup = {(r.item_id, r.date): r.demand for r in rows}
    if len(lookup) != len(rows) or len(rows) != len(items) * len(dates):
        raise ValueError("Duplicate or missing selected daily observations")
    return dates, np.asarray([[lookup[item, day] for day in dates] for item in items], dtype=float)
