from pyspark.sql import SparkSession

# ==========================================
# 1. KHOI TAO SPARK
# ==========================================

spark = SparkSession.builder \
    .appName("M5-Sales-Analysis") \
    .master("local[*]") \
    .getOrCreate()

print("=" * 60)
print("SPARK VERSION:", spark.version)
print("=" * 60)


# ==========================================
# 2. DUONG DAN DATA
# ==========================================

sales_path = r"D:\BigData\DoAn\data\sales_train_validation.csv"


# ==========================================
# 3. DOC SALES BANG SPARK
# ==========================================

print("\nReading sales_train_validation.csv...")

sales = spark.read.csv(
    sales_path,
    header=True,
    inferSchema=True
)


# ==========================================
# 4. THONG TIN DATA
# ==========================================

print("\n" + "=" * 60)
print("DATA INFORMATION")
print("=" * 60)

print("Number of rows:", sales.count())
print("Number of columns:", len(sales.columns))


# ==========================================
# 5. SCHEMA
# ==========================================

print("\n" + "=" * 60)
print("SCHEMA")
print("=" * 60)

sales.printSchema()


# ==========================================
# 6. HIEN THI 5 DONG DAU
# ==========================================

print("\n" + "=" * 60)
print("FIRST 5 ROWS")
print("=" * 60)

sales.show(5, truncate=False)


# ==========================================
# 7. KET THUC
# ==========================================

spark.stop()

print("\n" + "=" * 60)
print("SPARK READ DATA SUCCESSFULLY!")
print("=" * 60)