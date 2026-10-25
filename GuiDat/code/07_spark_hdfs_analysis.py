from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, avg, max, min

spark = SparkSession.builder \
    .appName("M5 HDFS Analysis") \
    .master("local[*]") \
    .config("spark.driver.memory", "6g") \
    .getOrCreate()

print("=" * 60)
print("M5 SPARK ANALYSIS FROM HDFS")
print("=" * 60)

# Đọc dữ liệu trực tiếp từ HDFS
hdfs_path = "hdfs://localhost:9000/m5/processed_m5"

df = spark.read.parquet(hdfs_path)

print("\nSo dong:", df.count())
print("So cot:", len(df.columns))

print("\nCac cot:")
print(df.columns)

print("\nSchema:")
df.printSchema()

print("\n5 dong dau:")
df.show(5, truncate=False)

# ============================================================
# 1. DOANH SO THEO CATEGORY
# ============================================================

print("\n" + "=" * 60)
print("1. DOANH SO THEO CATEGORY")
print("=" * 60)

df.groupBy("cat_id") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy(col("total_demand").desc()) \
    .show()

# ============================================================
# 2. DOANH SO THEO STORE
# ============================================================

print("\n" + "=" * 60)
print("2. DOANH SO THEO STORE")
print("=" * 60)

df.groupBy("store_id") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy(col("total_demand").desc()) \
    .show()

# ============================================================
# 3. DOANH SO THEO STATE
# ============================================================

print("\n" + "=" * 60)
print("3. DOANH SO THEO STATE")
print("=" * 60)

df.groupBy("state_id") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy(col("total_demand").desc()) \
    .show()

# ============================================================
# 4. TOP 20 SAN PHAM
# ============================================================

print("\n" + "=" * 60)
print("4. TOP 20 SAN PHAM BAN CHAY")
print("=" * 60)

df.groupBy("item_id", "cat_id") \
    .agg(
        sum("demand").alias("total_demand")
    ) \
    .orderBy(col("total_demand").desc()) \
    .show(20)

# ============================================================
# 5. THEO NAM
# ============================================================

print("\n" + "=" * 60)
print("5. DOANH SO THEO NAM")
print("=" * 60)

df.groupBy("year") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy("year") \
    .show()

# ============================================================
# 6. THEO THANG
# ============================================================

print("\n" + "=" * 60)
print("6. DOANH SO THEO THANG")
print("=" * 60)

df.groupBy("month") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy("month") \
    .show()

# ============================================================
# 7. THEO THU
# ============================================================

print("\n" + "=" * 60)
print("7. DOANH SO THEO THU TRONG TUAN")
print("=" * 60)

df.groupBy("weekday") \
    .agg(
        sum("demand").alias("total_demand"),
        avg("demand").alias("avg_demand")
    ) \
    .orderBy(col("total_demand").desc()) \
    .show()

# ============================================================
# 8. THONG KE DEMAND
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

print("\n" + "=" * 60)
print("SPARK HDFS ANALYSIS COMPLETED!")
print("=" * 60)

spark.stop()