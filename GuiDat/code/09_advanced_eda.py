from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    sum,
    avg,
    max,
    min,
    count,
    stddev,
    desc
)
import os

# ============================================================
# 1. SPARK SESSION
# ============================================================

spark = (
    SparkSession.builder
    .appName("M5_Advanced_EDA")
    .config("spark.driver.memory", "4g")
    .config("spark.executor.memory", "4g")
    .config("spark.sql.shuffle.partitions", "50")
    .config("spark.sql.adaptive.enabled", "true")
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")


# ============================================================
# 2. INPUT / OUTPUT
# ============================================================

INPUT_PATH = "hdfs://localhost:9000/m5/processed_m5"

OUTPUT_DIR = "reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

REPORT_FILE = os.path.join(
    OUTPUT_DIR,
    "advanced_eda_summary.txt"
)


# ============================================================
# 3. READ DATA
# ============================================================

print("=" * 70)
print("ADVANCED EDA - M5 SALES DATA")
print("=" * 70)

print("\nLoading data from HDFS...")

df = spark.read.parquet(INPUT_PATH)

# Chỉ giữ các cột cần thiết
df = df.select(
    "item_id",
    "cat_id",
    "store_id",
    "state_id",
    "date",
    "demand",
    "sell_price",
    "weekday",
    "month",
    "year",
    "event_name_1",
    "event_type_1",
    "snap_CA",
    "snap_TX",
    "snap_WI"
)

print("Data loaded successfully!")


# ============================================================
# 4. BASIC INFORMATION
# ============================================================

print("\nCalculating basic information...")

row_count = df.count()

print("Rows:", row_count)
print("Columns:", len(df.columns))


# ============================================================
# REPORT INITIALIZATION
# ============================================================

report = []

report.append("=" * 70)
report.append("ADVANCED EDA - M5 SALES DATA")
report.append("=" * 70)

report.append("")
report.append("1. BASIC INFORMATION")
report.append("-" * 70)
report.append(f"Total rows: {row_count}")
report.append(f"Total columns: {len(df.columns)}")


# ============================================================
# 5. DEMAND DISTRIBUTION
# ============================================================

print("\n" + "=" * 70)
print("1. DEMAND DISTRIBUTION")
print("=" * 70)

demand_stats = (
    df.select(
        count("demand").alias("count"),
        avg("demand").alias("mean"),
        stddev("demand").alias("stddev"),
        min("demand").alias("min"),
        max("demand").alias("max")
    )
    .collect()[0]
)

print("Average demand:", demand_stats["mean"])
print("Std deviation:", demand_stats["stddev"])
print("Minimum:", demand_stats["min"])
print("Maximum:", demand_stats["max"])

report.append("")
report.append("2. DEMAND DISTRIBUTION")
report.append("-" * 70)
report.append(f"Average demand: {demand_stats['mean']}")
report.append(f"Standard deviation: {demand_stats['stddev']}")
report.append(f"Minimum demand: {demand_stats['min']}")
report.append(f"Maximum demand: {demand_stats['max']}")


# ============================================================
# 6. ZERO-DEMAND ANALYSIS
# ============================================================

print("\n" + "=" * 70)
print("2. ZERO-DEMAND ANALYSIS")
print("=" * 70)

zero_count = (
    df.filter(col("demand") == 0)
    .count()
)

zero_percent = (
    zero_count / row_count * 100
    if row_count > 0
    else 0
)

print("Zero-demand rows:", zero_count)
print(f"Zero-demand percentage: {zero_percent:.2f}%")

report.append("")
report.append("3. ZERO-DEMAND ANALYSIS")
report.append("-" * 70)
report.append(f"Zero-demand rows: {zero_count}")
report.append(f"Zero-demand percentage: {zero_percent:.2f}%")


# ============================================================
# 7. DEMAND BY CATEGORY
# ============================================================

print("\n" + "=" * 70)
print("3. DEMAND BY CATEGORY")
print("=" * 70)

category = (
    df.groupBy("cat_id")
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand"),
        stddev("demand").alias("std_demand")
    )
    .orderBy(desc("total_demand"))
)

category.show(truncate=False)

report.append("")
report.append("4. DEMAND BY CATEGORY")
report.append("-" * 70)

for row in category.collect():
    report.append(
        f"{row['cat_id']}: "
        f"total={row['total_demand']}, "
        f"average={row['avg_demand']:.4f}, "
        f"std={row['std_demand']:.4f}"
    )


# ============================================================
# 8. DEMAND BY STORE
# ============================================================

print("\n" + "=" * 70)
print("4. DEMAND BY STORE")
print("=" * 70)

store = (
    df.groupBy("store_id")
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand"),
        stddev("demand").alias("std_demand")
    )
    .orderBy(desc("total_demand"))
)

store.show(truncate=False)

report.append("")
report.append("5. DEMAND BY STORE")
report.append("-" * 70)

for row in store.collect():
    report.append(
        f"{row['store_id']}: "
        f"total={row['total_demand']}, "
        f"average={row['avg_demand']:.4f}, "
        f"std={row['std_demand']:.4f}"
    )


# ============================================================
# 9. DEMAND BY STATE
# ============================================================

print("\n" + "=" * 70)
print("5. DEMAND BY STATE")
print("=" * 70)

state = (
    df.groupBy("state_id")
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    )
    .orderBy(desc("total_demand"))
)

state.show(truncate=False)

report.append("")
report.append("6. DEMAND BY STATE")
report.append("-" * 70)

for row in state.collect():
    report.append(
        f"{row['state_id']}: "
        f"total={row['total_demand']}, "
        f"average={row['avg_demand']:.4f}"
    )


# ============================================================
# 10. DEMAND BY WEEKDAY
# ============================================================

print("\n" + "=" * 70)
print("6. DEMAND BY WEEKDAY")
print("=" * 70)

weekday = (
    df.groupBy("weekday")
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    )
    .orderBy(desc("avg_demand"))
)

weekday.show(truncate=False)

report.append("")
report.append("7. DEMAND BY WEEKDAY")
report.append("-" * 70)

for row in weekday.collect():
    report.append(
        f"{row['weekday']}: "
        f"total={row['total_demand']}, "
        f"average={row['avg_demand']:.4f}"
    )


# ============================================================
# 11. DEMAND BY MONTH
# ============================================================

print("\n" + "=" * 70)
print("7. DEMAND BY MONTH")
print("=" * 70)

monthly = (
    df.groupBy("month")
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    )
    .orderBy("month")
)

monthly.show(truncate=False)

report.append("")
report.append("8. DEMAND BY MONTH")
report.append("-" * 70)

for row in monthly.collect():
    report.append(
        f"Month {row['month']}: "
        f"total={row['total_demand']}, "
        f"average={row['avg_demand']:.4f}"
    )


# ============================================================
# 12. DEMAND BY YEAR
# ============================================================

print("\n" + "=" * 70)
print("8. DEMAND BY YEAR")
print("=" * 70)

yearly = (
    df.groupBy("year")
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    )
    .orderBy("year")
)

yearly.show(truncate=False)

report.append("")
report.append("9. DEMAND BY YEAR")
report.append("-" * 70)

for row in yearly.collect():
    report.append(
        f"Year {row['year']}: "
        f"total={row['total_demand']}, "
        f"average={row['avg_demand']:.4f}"
    )


# ============================================================
# 13. TOP 20 PRODUCTS
# ============================================================

print("\n" + "=" * 70)
print("9. TOP 20 PRODUCTS")
print("=" * 70)

top_products = (
    df.groupBy(
        "item_id",
        "cat_id"
    )
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    )
    .orderBy(desc("total_demand"))
    .limit(20)
)

top_products.show(truncate=False)

report.append("")
report.append("10. TOP 20 PRODUCTS")
report.append("-" * 70)

for row in top_products.collect():
    report.append(
        f"{row['item_id']} | "
        f"{row['cat_id']} | "
        f"total={row['total_demand']} | "
        f"average={row['avg_demand']:.4f}"
    )


# ============================================================
# 14. TOP STORES
# ============================================================

print("\n" + "=" * 70)
print("10. TOP STORES BY AVERAGE DEMAND")
print("=" * 70)

top_stores = (
    df.groupBy("store_id")
    .agg(
        avg("demand").alias("avg_demand")
    )
    .orderBy(desc("avg_demand"))
)

top_stores.show(truncate=False)

report.append("")
report.append("11. TOP STORES BY AVERAGE DEMAND")
report.append("-" * 70)

for row in top_stores.collect():
    report.append(
        f"{row['store_id']}: "
        f"average={row['avg_demand']:.4f}"
    )


# ============================================================
# 15. EVENT IMPACT
# ============================================================

print("\n" + "=" * 70)
print("11. EVENT IMPACT")
print("=" * 70)

event_stats = (
    df.withColumn(
        "has_event",
        col("event_name_1").isNotNull()
    )
    .groupBy("has_event")
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand"),
        count("*").alias("rows")
    )
    .orderBy("has_event")
)

event_stats.show(truncate=False)

report.append("")
report.append("12. EVENT IMPACT")
report.append("-" * 70)

for row in event_stats.collect():
    event_label = (
        "Event"
        if row["has_event"]
        else "No Event"
    )

    report.append(
        f"{event_label}: "
        f"rows={row['rows']}, "
        f"total={row['total_demand']}, "
        f"average={row['avg_demand']:.4f}"
    )


# ============================================================
# 16. PRICE INFORMATION
# ============================================================

print("\n" + "=" * 70)
print("12. PRICE INFORMATION")
print("=" * 70)

price_stats = (
    df.select(
        avg("sell_price").alias("avg_price"),
        min("sell_price").alias("min_price"),
        max("sell_price").alias("max_price")
    )
    .collect()[0]
)

print("Average price:", price_stats["avg_price"])
print("Minimum price:", price_stats["min_price"])
print("Maximum price:", price_stats["max_price"])

report.append("")
report.append("13. PRICE INFORMATION")
report.append("-" * 70)
report.append(
    f"Average price: {price_stats['avg_price']}"
)
report.append(
    f"Minimum price: {price_stats['min_price']}"
)
report.append(
    f"Maximum price: {price_stats['max_price']}"
)


# ============================================================
# 17. SNAP ANALYSIS
# ============================================================

print("\n" + "=" * 70)
print("13. SNAP PROGRAM ANALYSIS")
print("=" * 70)

for snap_col in [
    "snap_CA",
    "snap_TX",
    "snap_WI"
]:

    snap = (
        df.groupBy(snap_col)
        .agg(
            avg("demand").alias("avg_demand"),
            sum("demand").alias("total_demand"),
            count("*").alias("rows")
        )
        .orderBy(snap_col)
    )

    print(f"\n{snap_col}")
    snap.show(truncate=False)

    report.append("")
    report.append(f"{snap_col}")
    report.append("-" * 50)

    for row in snap.collect():

        report.append(
            f"{snap_col}={row[snap_col]}: "
            f"rows={row['rows']}, "
            f"average={row['avg_demand']:.4f}, "
            f"total={row['total_demand']}"
        )


# ============================================================
# 18. KEY FINDINGS
# ============================================================

print("\n" + "=" * 70)
print("14. KEY FINDINGS")
print("=" * 70)

best_category = category.first()
best_store = store.first()
best_state = state.first()
best_weekday = weekday.first()

print(
    f"Highest demand category: "
    f"{best_category['cat_id']}"
)

print(
    f"Highest demand store: "
    f"{best_store['store_id']}"
)

print(
    f"Highest demand state: "
    f"{best_state['state_id']}"
)

print(
    f"Highest average demand weekday: "
    f"{best_weekday['weekday']}"
)

report.append("")
report.append("14. KEY FINDINGS")
report.append("-" * 70)

report.append(
    f"Highest demand category: "
    f"{best_category['cat_id']}"
)

report.append(
    f"Highest demand store: "
    f"{best_store['store_id']}"
)

report.append(
    f"Highest demand state: "
    f"{best_state['state_id']}"
)

report.append(
    f"Highest average demand weekday: "
    f"{best_weekday['weekday']}"
)


# ============================================================
# 19. DATASET CHARACTERISTICS
# ============================================================

report.append("")
report.append("15. DATASET CHARACTERISTICS")
report.append("-" * 70)

report.append(
    "The dataset contains daily product-level demand "
    "observations across multiple stores, states and categories."
)

report.append(
    "The dataset includes temporal, product, store, price, "
    "event and SNAP-related attributes."
)

report.append(
    "The processed data is stored in Parquet format "
    "and distributed across HDFS."
)


# ============================================================
# 20. SAVE REPORT
# ============================================================

with open(
    REPORT_FILE,
    "w",
    encoding="utf-8"
) as f:

    f.write(
        "\n".join(report)
    )


print("\n" + "=" * 70)
print("ADVANCED EDA COMPLETED!")
print("=" * 70)

print(
    f"Report saved to: {REPORT_FILE}"
)


# ============================================================
# 21. STOP SPARK
# ============================================================

spark.stop()