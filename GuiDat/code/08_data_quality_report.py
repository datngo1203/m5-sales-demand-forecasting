from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    count,
    when,
    min,
    max,
    avg,
    countDistinct,
    sum as spark_sum
)
import os


# ============================================================
# 1. CREATE SPARK SESSION
# ============================================================

spark = SparkSession.builder \
    .appName("M5_Data_Quality_Report") \
    .master("local[*]") \
    .config("spark.driver.memory", "8g") \
    .config("spark.sql.shuffle.partitions", "32") \
    .config("spark.sql.adaptive.enabled", "true") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")


# ============================================================
# 2. HDFS INPUT
# ============================================================

INPUT_PATH = "hdfs://localhost:9000/m5/processed_m5"

print("=" * 70)
print("DATA QUALITY REPORT - M5 SALES DATA")
print("=" * 70)

print("\nReading data from HDFS...")
print(INPUT_PATH)

df = spark.read.parquet(INPUT_PATH)


# ============================================================
# 3. BASIC INFORMATION
# ============================================================

print("\n" + "=" * 70)
print("1. BASIC INFORMATION")
print("=" * 70)

num_rows = df.count()
num_columns = len(df.columns)

print(f"So dong: {num_rows:,}")
print(f"So cot: {num_columns}")

print("\nCac cot:")
for i, column in enumerate(df.columns, 1):
    print(f"{i}. {column}")


# ============================================================
# 4. DATA TYPES
# ============================================================

print("\n" + "=" * 70)
print("2. DATA TYPES")
print("=" * 70)

df.printSchema()


# ============================================================
# 5. MISSING VALUES
# ============================================================

print("\n" + "=" * 70)
print("3. MISSING VALUES")
print("=" * 70)

missing_expr = []

for column in df.columns:
    missing_expr.append(
        spark_sum(
            when(
                col(column).isNull() |
                (col(column) == ""),
                1
            ).otherwise(0)
        ).alias(column)
    )

missing_row = df.select(missing_expr).collect()[0]

missing_results = []

for column in df.columns:
    missing_count = missing_row[column]

    if missing_count is None:
        missing_count = 0

    missing_results.append(
        (
            column,
            int(missing_count),
            round((missing_count / num_rows) * 100, 4)
        )
    )

print(f"{'Column':<20} {'Missing':>15} {'Percent':>12}")
print("-" * 50)

for column, missing_count, percentage in missing_results:
    print(
        f"{column:<20} "
        f"{missing_count:>15,} "
        f"{percentage:>11.4f}%"
    )


# ============================================================
# 6. BUSINESS KEY DUPLICATE CHECK
# ============================================================

print("\n" + "=" * 70)
print("4. BUSINESS KEY DUPLICATE CHECK")
print("=" * 70)

# M5 business key:
# id + d
#
# Không kiểm tra duplicate toàn bộ 22 cột vì dataset có
# hơn 58 triệu dòng và phép dropDuplicates() rất tốn RAM.

key_columns = ["id", "d"]

print("Khoa kiem tra:", key_columns)

key_stats = df.agg(
    countDistinct(
        col("id"),
        col("d")
    ).alias("distinct_keys")
).collect()[0]

distinct_keys = key_stats["distinct_keys"]

key_duplicate = num_rows - distinct_keys

print(f"So record:       {num_rows:,}")
print(f"So key duy nhat: {distinct_keys:,}")
print(f"So key trung:    {key_duplicate:,}")

if key_duplicate == 0:
    print("=> Khong phat hien duplicate theo business key.")
else:
    print("=> CANH BAO: Co duplicate theo business key.")


# ============================================================
# 7. DEMAND QUALITY
# ============================================================

print("\n" + "=" * 70)
print("5. DEMAND QUALITY")
print("=" * 70)

demand_stats = df.agg(
    count("demand").alias("count"),
    min("demand").alias("min"),
    max("demand").alias("max"),
    avg("demand").alias("avg"),
    spark_sum(
        when(col("demand") < 0, 1).otherwise(0)
    ).alias("negative_count"),
    spark_sum(
        when(col("demand").isNull(), 1).otherwise(0)
    ).alias("null_count")
).collect()[0]

print(f"Count:          {demand_stats['count']:,}")
print(f"Minimum:        {demand_stats['min']}")
print(f"Maximum:        {demand_stats['max']}")
print(f"Average:        {demand_stats['avg']:.4f}")
print(f"Negative:       {demand_stats['negative_count']:,}")
print(f"Null:           {demand_stats['null_count']:,}")


# ============================================================
# 8. SELL PRICE QUALITY
# ============================================================

print("\n" + "=" * 70)
print("6. SELL PRICE QUALITY")
print("=" * 70)

price_stats = df.agg(
    count("sell_price").alias("count"),
    min("sell_price").alias("min"),
    max("sell_price").alias("max"),
    avg("sell_price").alias("avg"),
    spark_sum(
        when(col("sell_price") < 0, 1).otherwise(0)
    ).alias("negative_count"),
    spark_sum(
        when(col("sell_price").isNull(), 1).otherwise(0)
    ).alias("null_count")
).collect()[0]

print(f"Count:          {price_stats['count']:,}")
print(f"Minimum:        {price_stats['min']}")
print(f"Maximum:        {price_stats['max']}")
print(f"Average:        {price_stats['avg']:.4f}")
print(f"Negative:       {price_stats['negative_count']:,}")
print(f"Null:           {price_stats['null_count']:,}")


# ============================================================
# 9. DATE RANGE
# ============================================================

print("\n" + "=" * 70)
print("7. DATE RANGE")
print("=" * 70)

date_stats = df.agg(
    min("date").alias("min_date"),
    max("date").alias("max_date")
).collect()[0]

print(f"Tu ngay:        {date_stats['min_date']}")
print(f"Den ngay:       {date_stats['max_date']}")


# ============================================================
# 10. CARDINALITY
# ============================================================

print("\n" + "=" * 70)
print("8. CARDINALITY")
print("=" * 70)

cardinality_columns = [
    "item_id",
    "dept_id",
    "cat_id",
    "store_id",
    "state_id"
]

for column in cardinality_columns:

    value = df.select(
        countDistinct(column).alias("distinct_count")
    ).collect()[0]["distinct_count"]

    print(f"{column:<15}: {value:,}")


# ============================================================
# 11. CATEGORY DISTRIBUTION
# ============================================================

print("\n" + "=" * 70)
print("9. CATEGORY DISTRIBUTION")
print("=" * 70)

df.groupBy("cat_id") \
    .count() \
    .orderBy(col("count").desc()) \
    .show(truncate=False)


# ============================================================
# 12. STORE DISTRIBUTION
# ============================================================

print("\n" + "=" * 70)
print("10. STORE DISTRIBUTION")
print("=" * 70)

df.groupBy("store_id") \
    .count() \
    .orderBy(col("count").desc()) \
    .show(20, truncate=False)


# ============================================================
# 13. STATE DISTRIBUTION
# ============================================================

print("\n" + "=" * 70)
print("11. STATE DISTRIBUTION")
print("=" * 70)

df.groupBy("state_id") \
    .count() \
    .orderBy(col("count").desc()) \
    .show(truncate=False)


# ============================================================
# 14. DATA QUALITY SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("12. DATA QUALITY SUMMARY")
print("=" * 70)

quality_status = "PASS"

if key_duplicate > 0:
    quality_status = "WARNING"

if demand_stats["negative_count"] > 0:
    quality_status = "WARNING"

if price_stats["negative_count"] > 0:
    quality_status = "WARNING"

print(f"Overall status: {quality_status}")


# ============================================================
# 15. SAVE REPORT
# ============================================================

REPORT_DIR = "reports"

if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)

report_file = os.path.join(
    REPORT_DIR,
    "data_quality_summary.txt"
)

with open(report_file, "w", encoding="utf-8") as f:

    f.write("M5 DATA QUALITY REPORT\n")
    f.write("=" * 60 + "\n\n")

    f.write("BASIC INFORMATION\n")
    f.write("-" * 60 + "\n")
    f.write(f"So dong: {num_rows:,}\n")
    f.write(f"So cot: {num_columns}\n\n")

    f.write("MISSING VALUES\n")
    f.write("-" * 60 + "\n")

    for column, missing_count, percentage in missing_results:
        f.write(
            f"{column}: "
            f"{missing_count:,} "
            f"({percentage:.4f}%)\n"
        )

    f.write("\n")

    f.write("BUSINESS KEY DUPLICATE\n")
    f.write("-" * 60 + "\n")
    f.write(f"Key columns: {key_columns}\n")
    f.write(f"Total records: {num_rows:,}\n")
    f.write(f"Distinct keys: {distinct_keys:,}\n")
    f.write(f"Duplicate keys: {key_duplicate:,}\n")

    f.write("\n")

    f.write("DEMAND\n")
    f.write("-" * 60 + "\n")
    f.write(f"Minimum: {demand_stats['min']}\n")
    f.write(f"Maximum: {demand_stats['max']}\n")
    f.write(f"Average: {demand_stats['avg']:.4f}\n")
    f.write(f"Negative: {demand_stats['negative_count']:,}\n")
    f.write(f"Null: {demand_stats['null_count']:,}\n")

    f.write("\n")

    f.write("SELL PRICE\n")
    f.write("-" * 60 + "\n")
    f.write(f"Minimum: {price_stats['min']}\n")
    f.write(f"Maximum: {price_stats['max']}\n")
    f.write(f"Average: {price_stats['avg']:.4f}\n")
    f.write(f"Negative: {price_stats['negative_count']:,}\n")
    f.write(f"Null: {price_stats['null_count']:,}\n")

    f.write("\n")

    f.write("DATE RANGE\n")
    f.write("-" * 60 + "\n")
    f.write(f"From: {date_stats['min_date']}\n")
    f.write(f"To: {date_stats['max_date']}\n")

    f.write("\n")

    f.write("OVERALL STATUS\n")
    f.write("-" * 60 + "\n")
    f.write(quality_status + "\n")


# ============================================================
# 16. STOP SPARK
# ============================================================

spark.stop()

print("\n" + "=" * 70)
print("DATA QUALITY REPORT COMPLETED!")
print("=" * 70)

print(f"Report saved to: {report_file}")