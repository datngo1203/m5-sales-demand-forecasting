import pandas as pd
import os

# Đường dẫn dataset
DATA_DIR = r"D:\BigData\DoAn\m5-forecasting-accuracy"

sales_file = os.path.join(DATA_DIR, "sales_train_validation.csv")
calendar_file = os.path.join(DATA_DIR, "calendar.csv")
prices_file = os.path.join(DATA_DIR, "sell_prices.csv")


print("=" * 60)
print("1. KIỂM TRA SALES")
print("=" * 60)

sales = pd.read_csv(sales_file)

print("Kích thước:", sales.shape)
print("\nCác cột:")
print(sales.columns.tolist())

print("\n5 dòng đầu:")
print(sales.head())


print("\n" + "=" * 60)
print("2. KIỂM TRA CALENDAR")
print("=" * 60)

calendar = pd.read_csv(calendar_file)

print("Kích thước:", calendar.shape)
print("\nCác cột:")
print(calendar.columns.tolist())

print("\n5 dòng đầu:")
print(calendar.head())


print("\n" + "=" * 60)
print("3. KIỂM TRA SELL PRICES")
print("=" * 60)

prices = pd.read_csv(prices_file)

print("Kích thước:", prices.shape)
print("\nCác cột:")
print(prices.columns.tolist())

print("\n5 dòng đầu:")
print(prices.head())


print("\n" + "=" * 60)
print("4. THỐNG KÊ SALES")
print("=" * 60)

print("Số sản phẩm:", sales["item_id"].nunique())
print("Số cửa hàng:", sales["store_id"].nunique())
print("Số bang:", sales["state_id"].nunique())

print("\nCác bang:")
print(sales["state_id"].unique())

print("\nCác cửa hàng:")
print(sales["store_id"].unique())

print("\nCác category:")
print(sales["cat_id"].unique())

print("\nCác department:")
print(sales["dept_id"].unique())


print("\n" + "=" * 60)
print("5. KIỂM TRA GIÁ TRỊ THIẾU")
print("=" * 60)

print("\nSales:")
print(sales.isnull().sum().sort_values(ascending=False).head(20))

print("\nCalendar:")
print(calendar.isnull().sum().sort_values(ascending=False).head(20))

print("\nPrices:")
print(prices.isnull().sum().sort_values(ascending=False).head(20))


print("\n" + "=" * 60)
print("HOÀN THÀNH")
print("=" * 60)