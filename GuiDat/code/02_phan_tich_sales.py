import pandas as pd
import os

DATA_DIR = r"D:\BigData\DoAn\m5-forecasting-accuracy"

sales_file = os.path.join(DATA_DIR, "sales_train_validation.csv")

print("=" * 60)
print("ĐỌC SALES DATA")
print("=" * 60)

sales = pd.read_csv(sales_file)

# Các cột thông tin
id_cols = [
    "id",
    "item_id",
    "dept_id",
    "cat_id",
    "store_id",
    "state_id"
]

# Các cột doanh số
d_cols = [c for c in sales.columns if c.startswith("d_")]

print("Số sản phẩm-cửa hàng:", len(sales))
print("Số ngày:", len(d_cols))

# Tổng số lượng bán
sales["total_sales"] = sales[d_cols].sum(axis=1)

print("\n" + "=" * 60)
print("THỐNG KÊ DOANH SỐ")
print("=" * 60)

print("Tổng số sản phẩm-cửa hàng:", len(sales))
print("Có doanh số > 0:",
      (sales["total_sales"] > 0).sum())

print("Không có doanh số:",
      (sales["total_sales"] == 0).sum())

print("\nTổng sản phẩm bán ra:",
      sales["total_sales"].sum())

print("\nDoanh số trung bình:",
      sales["total_sales"].mean())

print("\nDoanh số lớn nhất:",
      sales["total_sales"].max())

print("\nDoanh số nhỏ nhất:",
      sales["total_sales"].min())


print("\n" + "=" * 60)
print("DOANH SỐ THEO CATEGORY")
print("=" * 60)

category_sales = (
    sales.groupby("cat_id")["total_sales"]
    .sum()
    .sort_values(ascending=False)
)

print(category_sales)


print("\n" + "=" * 60)
print("DOANH SỐ THEO STORE")
print("=" * 60)

store_sales = (
    sales.groupby("store_id")["total_sales"]
    .sum()
    .sort_values(ascending=False)
)

print(store_sales)


print("\n" + "=" * 60)
print("TOP 20 SẢN PHẨM")
print("=" * 60)

top_products = (
    sales[["item_id", "cat_id", "total_sales"]]
    .groupby(["item_id", "cat_id"])["total_sales"]
    .sum()
    .sort_values(ascending=False)
    .head(20)
)

print(top_products)


print("\n" + "=" * 60)
print("HOÀN THÀNH")
print("=" * 60)