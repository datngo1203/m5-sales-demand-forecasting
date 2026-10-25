from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("M5-Check-Processed") \
    .getOrCreate()

path = r"D:\BigData\DoAn\data\processed_m5"

print("=" * 60)
print("KIEM TRA DU LIEU DA XU LY")
print("=" * 60)

df = spark.read.parquet(path)

print("\nSo dong:", df.count())

print("\nSo cot:", len(df.columns))

print("\nCac cot:")
print(df.columns)

print("\n5 dong dau:")
df.show(5, truncate=False)

print("\nSchema:")
df.printSchema()

spark.stop()