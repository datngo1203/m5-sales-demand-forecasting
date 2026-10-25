from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window


# ============================================================
# 1. CONFIGURATION
# ============================================================

INPUT_PATH = "hdfs://localhost:9000/m5/processed_m5"
OUTPUT_PATH = "hdfs://localhost:9000/m5/forecasting_features"


# ============================================================
# 2. CREATE SPARK SESSION
# ============================================================

spark = (
    SparkSession.builder
    .appName("M5_Forecasting_Features")
    .config("spark.driver.memory", "4g")
    .config("spark.executor.memory", "4g")
    .config("spark.sql.shuffle.partitions", "32")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

print("=" * 70)
print("M5 FORECASTING FEATURE ENGINEERING")
print("=" * 70)


# ============================================================
# 3. READ PROCESSED DATA FROM HDFS
# ============================================================

print("\n[1] Reading processed data from HDFS...")

df = spark.read.parquet(INPUT_PATH)

print("Input rows:", df.count())
print("Input columns:", len(df.columns))

print("\nInput schema:")
df.printSchema()


# ============================================================
# 4. CHECK REQUIRED COLUMNS
# ============================================================

required_columns = [
    "item_id",
    "store_id",
    "cat_id",
    "state_id",
    "date",
    "demand"
]

missing_columns = [
    c for c in required_columns
    if c not in df.columns
]

if missing_columns:
    print("\nERROR: Missing columns:")
    print(missing_columns)
    spark.stop()
    raise Exception("Required columns are missing.")


# ============================================================
# 5. PREPARE DATE
# ============================================================

print("\n[2] Preparing date features...")

df = df.withColumn(
    "date",
    F.to_date("date")
)

df = (
    df
    .withColumn("year", F.year("date"))
    .withColumn("month", F.month("date"))
    .withColumn("day", F.dayofmonth("date"))
    .withColumn("weekofyear", F.weekofyear("date"))
    .withColumn("weekday", F.dayofweek("date"))
)


# ============================================================
# 6. CREATE SNAP FEATURE
# ============================================================

# M5 has SNAP variables by state.
# Convert them into a single SNAP feature according to the store state.

if "snap_CA" in df.columns:
    df = df.withColumn(
        "snap",
        F.when(F.col("state_id") == "CA", F.col("snap_CA"))
         .when(F.col("state_id") == "TX", F.col("snap_TX"))
         .when(F.col("state_id") == "WI", F.col("snap_WI"))
         .otherwise(F.lit(0))
    )
else:
    df = df.withColumn("snap", F.lit(0))


# ============================================================
# 7. DEFINE TIME WINDOW
# ============================================================

print("\n[3] Creating time-series features...")

# Each item-store pair is treated as an individual time series.
window_spec = (
    Window
    .partitionBy("item_id", "store_id")
    .orderBy("date")
)


# ============================================================
# 8. LAG FEATURES
# ============================================================

print("Creating lag features...")

df = (
    df
    .withColumn("lag_1", F.lag("demand", 1).over(window_spec))
    .withColumn("lag_7", F.lag("demand", 7).over(window_spec))
    .withColumn("lag_14", F.lag("demand", 14).over(window_spec))
    .withColumn("lag_28", F.lag("demand", 28).over(window_spec))
)


# ============================================================
# 9. ROLLING FEATURES
# ============================================================

print("Creating rolling mean features...")

window_7 = (
    Window
    .partitionBy("item_id", "store_id")
    .orderBy("date")
    .rowsBetween(-7, -1)
)

window_14 = (
    Window
    .partitionBy("item_id", "store_id")
    .orderBy("date")
    .rowsBetween(-14, -1)
)

window_28 = (
    Window
    .partitionBy("item_id", "store_id")
    .orderBy("date")
    .rowsBetween(-28, -1)
)

df = (
    df
    .withColumn(
        "rolling_mean_7",
        F.avg("demand").over(window_7)
    )
    .withColumn(
        "rolling_mean_14",
        F.avg("demand").over(window_14)
    )
    .withColumn(
        "rolling_mean_28",
        F.avg("demand").over(window_28)
    )
)


# ============================================================
# 10. PRICE FEATURE
# ============================================================

if "sell_price" in df.columns:
    df = df.withColumn(
        "price",
        F.col("sell_price").cast("double")
    )
elif "price" in df.columns:
    df = df.withColumn(
        "price",
        F.col("price").cast("double")
    )
else:
    df = df.withColumn(
        "price",
        F.lit(None).cast("double")
    )


# ============================================================
# 11. EVENT FEATURE
# ============================================================

if "event_name" in df.columns:
    df = df.withColumn(
        "has_event",
        F.when(
            F.col("event_name").isNotNull(),
            1
        ).otherwise(0)
    )
else:
    df = df.withColumn(
        "has_event",
        F.lit(0)
    )


# ============================================================
# 12. SELECT FINAL FEATURES
# ============================================================

print("\n[4] Selecting forecasting features...")

final_columns = [
    "item_id",
    "store_id",
    "cat_id",
    "state_id",

    "date",
    "year",
    "month",
    "day",
    "weekofyear",
    "weekday",

    "demand",

    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",

    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_28",

    "price",
    "snap",
    "has_event"
]

# Only keep columns that actually exist.
final_columns = [
    c for c in final_columns
    if c in df.columns
]

forecast_df = df.select(final_columns)


# ============================================================
# 13. REMOVE ROWS WITHOUT ENOUGH HISTORY
# ============================================================

print("\n[5] Removing rows without sufficient historical information...")

before_count = forecast_df.count()

forecast_df = forecast_df.dropna(
    subset=[
        "lag_1",
        "lag_7",
        "lag_14",
        "lag_28",
        "rolling_mean_7",
        "rolling_mean_14",
        "rolling_mean_28"
    ]
)

after_count = forecast_df.count()

print("Rows before removing history gaps:", before_count)
print("Rows after removing history gaps:", after_count)
print("Rows removed:", before_count - after_count)


# ============================================================
# 14. SHOW SAMPLE
# ============================================================

print("\n[6] Forecasting feature sample:")

forecast_df.show(
    10,
    truncate=False
)


# ============================================================
# 15. SHOW FINAL SCHEMA
# ============================================================

print("\n[7] Final schema:")

forecast_df.printSchema()


# ============================================================
# 16. SAVE TO HDFS
# ============================================================

print("\n[8] Saving forecasting-ready dataset to HDFS...")

(
    forecast_df
    .write
    .mode("overwrite")
    .parquet(OUTPUT_PATH)
)

print("\nSaved to:")
print(OUTPUT_PATH)


# ============================================================
# 17. VALIDATION
# ============================================================

print("\n[9] Validation...")

saved_df = spark.read.parquet(OUTPUT_PATH)

print("Final rows:", saved_df.count())
print("Final columns:", len(saved_df.columns))

print("\nFinal columns:")
for c in saved_df.columns:
    print("-", c)


# ============================================================
# 18. FINAL MESSAGE
# ============================================================

print("\n" + "=" * 70)
print("FORECASTING FEATURE ENGINEERING COMPLETED!")
print("=" * 70)

print("\nHDFS output:")
print(OUTPUT_PATH)

print("\nDataset is ready for the forecasting/modeling stage.")

spark.stop()