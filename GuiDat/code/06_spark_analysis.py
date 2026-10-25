from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    sum,
    avg,
    max,
    min,
    count,
    month,
    year,
    dayofweek
)

# ============================================================
# 1. KHỞI TẠO SPARK
# ============================================================

spark = SparkSession.builder \
    .appName("M5-Spark-Analysis") \
    .config("spark.sql.shuffle.partitions", "10") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

print("=" * 60)
print("M5 SALES ANALYSIS - SPARK")
print("=" * 60)

# ============================================================
# 2. ĐỌC DỮ LIỆU ĐÃ XỬ LÝ
# ============================================================

data_path = r"D:\BigData\DoAn\data\processed_m5"

df = spark.read.parquet(data_path)

print("\nSo dong:", df.count())
print("So cot:", len(df.columns))

# ============================================================
# 3. TỔNG DOANH SỐ THEO CATEGORY
# ============================================================

print("\n" + "=" * 60)
print("1. DOANH SO THEO CATEGORY")
print("=" * 60)

category_sales = df.groupBy("cat_id") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy("total_demand", ascending=False)

category_sales.show()

# ============================================================
# 4. DOANH SỐ THEO STORE
# ============================================================

print("\n" + "=" * 60)
print("2. DOANH SO THEO STORE")
print("=" * 60)

store_sales = df.groupBy("store_id") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy("total_demand", ascending=False)

store_sales.show()

# ============================================================
# 5. DOANH SỐ THEO STATE
# ============================================================

print("\n" + "=" * 60)
print("3. DOANH SO THEO STATE")
print("=" * 60)

state_sales = df.groupBy("state_id") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy("total_demand", ascending=False)

state_sales.show()

# ============================================================
# 6. TOP 20 SẢN PHẨM
# ============================================================

print("\n" + "=" * 60)
print("4. TOP 20 SAN PHAM BAN CHAY")
print("=" * 60)

top_products = df.groupBy("item_id", "cat_id") \
    .agg(
        sum("demand").alias("total_demand")
    ) \
    .orderBy("total_demand", ascending=False) \
    .limit(20)

top_products.show(20, truncate=False)

# ============================================================
# 7. DOANH SỐ THEO NĂM
# ============================================================

print("\n" + "=" * 60)
print("5. DOANH SO THEO NAM")
print("=" * 60)

year_sales = df.groupBy("year") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy("year")

year_sales.show()

# ============================================================
# 8. DOANH SỐ THEO THÁNG
# ============================================================

print("\n" + "=" * 60)
print("6. DOANH SO THEO THANG")
print("=" * 60)

month_sales = df.groupBy("month") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy("month")

month_sales.show()

# ============================================================
# 9. DOANH SỐ THEO NGÀY TRONG TUẦN
# ============================================================

print("\n" + "=" * 60)
print("7. DOANH SO THEO THU TRONG TUAN")
print("=" * 60)

weekday_sales = df.groupBy("weekday") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy("total_demand", ascending=False)

weekday_sales.show()

# ============================================================
# 10. THỐNG KÊ DEMAND
# ============================================================

print("\n" + "=" * 60)
print("8. THONG KE DEMAND")
print("=" * 60)

df.select(
    sum("demand").alias("total"),
    avg("demand").alias("average"),
    max("demand").alias("maximum"),
    min("demand").alias("minimum")
).show()

# ============================================================
# KẾT THÚC
# ============================================================

print("\n" + "=" * 60)
print("SPARK ANALYSIS COMPLETED!")
print("=" * 60)

spark.stop()