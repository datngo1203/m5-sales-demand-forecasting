from pyspark.sql import SparkSession
from pyspark.sql.functions import broadcast


# ============================================================
# 1. KHOI TAO SPARK
# ============================================================

spark = SparkSession.builder \
    .appName("M5-Preprocessing") \
    .master("local[*]") \
    .config("spark.driver.memory", "4g") \
    .config("spark.sql.shuffle.partitions", "32") \
    .config("spark.sql.autoBroadcastJoinThreshold", "50MB") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")


print("=" * 60)
print("M5 DATA PREPROCESSING")
print("=" * 60)


# ============================================================
# 2. DUONG DAN
# ============================================================

DATA_DIR = r"D:\BigData\DoAn\data"

sales_path = DATA_DIR + r"\sales_train_validation.csv"
calendar_path = DATA_DIR + r"\calendar.csv"
prices_path = DATA_DIR + r"\sell_prices.csv"

output_path = DATA_DIR + r"\processed_m5"


# ============================================================
# 3. DOC SALES
# ============================================================

print("\n[1] Reading sales...")

sales = spark.read.csv(
    sales_path,
    header=True,
    inferSchema=True
)

print("Sales columns:", len(sales.columns))


# ============================================================
# 4. WIDE -> LONG
# ============================================================

print("\n[2] Converting sales WIDE -> LONG...")

id_columns = [
    "id",
    "item_id",
    "dept_id",
    "cat_id",
    "store_id",
    "state_id"
]

day_columns = [
    c for c in sales.columns
    if c.startswith("d_")
]

stack_expression = ", ".join(
    [f"'{c}', `{c}`" for c in day_columns]
)

sales_long = sales.selectExpr(
    *id_columns,
    f"stack({len(day_columns)}, {stack_expression}) as (d, demand)"
)

print("WIDE -> LONG completed.")


# ============================================================
# 5. DOC CALENDAR
# ============================================================

print("\n[3] Reading calendar...")

calendar = spark.read.csv(
    calendar_path,
    header=True,
    inferSchema=True
)

calendar_selected = calendar.select(
    "d",
    "date",
    "wm_yr_wk",
    "weekday",
    "wday",
    "month",
    "year",
    "event_name_1",
    "event_type_1",
    "event_name_2",
    "event_type_2",
    "snap_CA",
    "snap_TX",
    "snap_WI"
)


# ============================================================
# 6. JOIN CALENDAR
# ============================================================

print("\n[4] Joining calendar...")

sales_calendar = sales_long.join(
    broadcast(calendar_selected),
    on="d",
    how="left"
)

print("Calendar join completed.")


# ============================================================
# 7. DOC SELL PRICES
# ============================================================

print("\n[5] Reading sell prices...")

prices = spark.read.csv(
    prices_path,
    header=True,
    inferSchema=True
)

prices = prices.select(
    "store_id",
    "item_id",
    "wm_yr_wk",
    "sell_price"
)

print("Price columns selected.")


# ============================================================
# 8. JOIN SELL PRICES
# ============================================================

print("\n[6] Joining sell prices...")

sales_final = sales_calendar.join(
    prices,
    on=["store_id", "item_id", "wm_yr_wk"],
    how="left"
)

print("Price join completed.")


# ============================================================
# 9. CHON COT
# ============================================================

print("\n[7] Selecting final columns...")

final_data = sales_final.select(
    "id",
    "item_id",
    "dept_id",
    "cat_id",
    "store_id",
    "state_id",
    "d",
    "date",
    "wm_yr_wk",
    "demand",
    "sell_price",
    "weekday",
    "wday",
    "month",
    "year",
    "event_name_1",
    "event_type_1",
    "event_name_2",
    "event_type_2",
    "snap_CA",
    "snap_TX",
    "snap_WI"
)


# ============================================================
# 10. LUU PARQUET
# ============================================================

print("\n[8] Saving processed data...")

final_data.write \
    .mode("overwrite") \
    .parquet(output_path)

print("\n" + "=" * 60)
print("PREPROCESSING COMPLETED!")
print("=" * 60)

print("Saved to:")
print(output_path)


# ============================================================
# 11. STOP
# ============================================================

spark.stop()