from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("M5-Test") \
    .master("local[*]") \
    .getOrCreate()

print("================================")
print("Spark version:", spark.version)
print("Spark da chay thanh cong!")
print("================================")

spark.stop()