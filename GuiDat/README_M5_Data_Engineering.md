# M5 Forecasting - Data Processing & Feature Engineering

## 1. Giới thiệu

Đây là phần Data Engineering của đồ án M5 Forecasting.

Mục tiêu của phần này là:
- Khảo sát và phân tích dữ liệu M5.
- Làm sạch và tiền xử lý dữ liệu bằng Apache Spark.
- Lưu trữ dữ liệu dạng Parquet.
- Đưa dữ liệu lên HDFS.
- Kiểm tra chất lượng dữ liệu.
- Thực hiện phân tích EDA nâng cao về nhu cầu bán hàng.
- Chuẩn bị bộ dữ liệu và các đặc trưng phục vụ cho bước Forecasting/Modeling.

Phần Modeling/Forecasting sẽ được thực hiện ở bước tiếp theo dựa trên dữ liệu đã được chuẩn bị.

---

## 2. Công nghệ sử dụng

- Python
- PySpark
- Apache Spark 3.5.9
- Hadoop 3.3.6
- HDFS
- Parquet
- Snappy Compression

---

## 3. Cấu trúc thư mục

```text
GuiDat/
├── README.md
├── code/
│   ├── 01_khao_sat.py
│   ├── 02_phan_tich_sales.py
│   ├── 03_spark_read.py
│   ├── 04_spark_preprocessing.py
│   ├── 05_check_processed.py
│   ├── 06_spark_analysis.py
│   ├── 07_spark_hdfs_analysis.py
│   ├── 08_data_quality_report.py
│   ├── 09_advanced_eda.py
│   ├── 10_forecasting_features.py
│   └── reports/
│       ├── data_quality_summary.txt
│       └── advanced_eda_summary.txt
└── data/
    └── processed_m5/
        ├── part-00000-....parquet
        ├── part-00001-....parquet
        ├── ...
        └── _SUCCESS
```

---

## 4. Quy trình xử lý dữ liệu

```text
Raw M5 Dataset
      ↓
01. Khảo sát dữ liệu
      ↓
02. Phân tích dữ liệu ban đầu
      ↓
03. Đọc dữ liệu bằng Spark
      ↓
04. Làm sạch & tiền xử lý
      ↓
05. Kiểm tra dữ liệu sau xử lý
      ↓
06. Phân tích bằng Spark
      ↓
07. Đưa dữ liệu lên HDFS
      ↓
08. Data Quality Report
      ↓
09. Advanced EDA
      ↓
10. Forecasting Feature Engineering
      ↓
Forecasting / Modeling
```

---

## 5. Các file code

### 5.1. 01_khao_sat.py

Khảo sát dataset ban đầu:
- Kiểm tra cấu trúc dữ liệu.
- Kiểm tra số lượng dòng/cột.
- Kiểm tra kiểu dữ liệu.
- Kiểm tra các trường quan trọng.
- Xác định các vấn đề cần xử lý.

### 5.2. 02_phan_tich_sales.py

Phân tích dữ liệu sales ban đầu:
- Phân tích demand.
- Kiểm tra phân bố dữ liệu.
- Phân tích theo sản phẩm, cửa hàng và thời gian.
- Xác định các đặc điểm chính của dữ liệu.

### 5.3. 03_spark_read.py

Đọc dữ liệu bằng Apache Spark:
- Kiểm tra khả năng đọc dataset bằng Spark.
- Kiểm tra schema.
- Kiểm tra số lượng records.
- Chuẩn bị dữ liệu cho các bước xử lý tiếp theo.

### 5.4. 04_spark_preprocessing.py

Làm sạch và tiền xử lý dữ liệu:
- Chuẩn hóa kiểu dữ liệu.
- Xử lý dữ liệu thiếu.
- Chuẩn hóa các trường ngày tháng.
- Chuẩn hóa các thuộc tính categorical.
- Chuẩn bị dữ liệu để lưu dưới dạng Parquet.

Output:

```text
data/processed_m5/
```

Dữ liệu được lưu dưới dạng Parquet + Snappy Compression.

### 5.5. 05_check_processed.py

Kiểm tra dữ liệu sau preprocessing và xác nhận dữ liệu đã được tạo đúng.

### 5.6. 06_spark_analysis.py

Thực hiện các phân tích dữ liệu bằng Spark trên dataset đã xử lý.

### 5.7. 07_spark_hdfs_analysis.py

Thực hiện phân tích và làm việc với dữ liệu được lưu trên HDFS.

---

## 6. Dữ liệu đã xử lý

Dữ liệu sau preprocessing được lưu tại:

```text
data/processed_m5/
```

Đây là dữ liệu local dạng Parquet.

Dữ liệu tương ứng cũng được đưa lên HDFS để sử dụng trong pipeline Big Data.

HDFS path:

```text
/m5/processed_m5
```

---

## 7. Làm sạch và tiền xử lý dữ liệu

Dữ liệu sau preprocessing có các đặc điểm:
- Được xử lý bằng Apache Spark.
- Được chuẩn hóa schema.
- Các trường ngày tháng được chuẩn hóa để phục vụ phân tích theo thời gian.
- Các trường categorical được giữ ở dạng phù hợp cho phân tích.
- Dữ liệu được lưu dưới dạng Parquet để tối ưu việc đọc/ghi trên hệ thống Big Data.
- Dữ liệu được nén bằng Snappy.
- Dữ liệu sau xử lý được kiểm tra lại trước khi đưa vào HDFS.

Kết quả kiểm tra chất lượng được lưu tại:

```text
code/reports/data_quality_summary.txt
```

Kết quả hiện tại:

```text
Overall status: PASS
```

---

## 8. Data Quality Report

File thực hiện:

```text
08_data_quality_report.py
```

Mục đích là đánh giá chất lượng dữ liệu trước khi chuyển sang các bước phân tích và forecasting.

Các nội dung kiểm tra:
- Số lượng records.
- Số lượng columns.
- Missing values.
- Duplicate records.
- Giá trị demand bất thường.
- Kiểu dữ liệu.
- Một số thống kê cơ bản.
- Trạng thái tổng thể của dataset.

Kết quả:

```text
code/reports/data_quality_summary.txt
```

Overall status hiện tại:

```text
PASS
```

---

## 9. Advanced EDA

File thực hiện:

```text
09_advanced_eda.py
```

Mục đích là phân tích sâu hơn về đặc điểm của demand trước khi xây dựng mô hình forecasting.

Dataset được phân tích có:

```text
58,327,370 records
```

### Demand

Average demand:

```text
1.1263
```

Maximum demand:

```text
763
```

Zero-demand rows:

```text
39,777,094
```

Zero-demand percentage:

```text
68.20%
```

Điều này cho thấy dữ liệu có tỷ lệ zero-demand khá lớn và đây là đặc điểm quan trọng cần lưu ý khi xây dựng mô hình forecasting.

### Theo category

Category có demand cao nhất:

```text
FOODS
```

### Theo store

Store có average demand cao nhất:

```text
CA_3
```

Average demand:

```text
1.9182
```

### Theo state

State có demand cao nhất:

```text
CA
```

### Theo weekday

Ngày có average demand cao nhất:

```text
Saturday
```

Kết quả đầy đủ được lưu tại:

```text
code/reports/advanced_eda_summary.txt
```

---

## 10. Forecasting Feature Engineering

File thực hiện:

```text
10_forecasting_features.py
```

Mục đích là chuẩn bị dataset đầu vào cho người thực hiện Forecasting/Modeling.

Thay vì để người làm Modeling phải tự xử lý lại dữ liệu từ đầu, file này đã chuẩn bị các đặc trưng cần thiết cho bài toán dự báo nhu cầu.

Các nhóm feature bao gồm:

### Temporal features

Các đặc trưng thời gian được tạo từ ngày:
- year
- month
- week
- day
- weekday
- weekend

Các feature này giúp mô hình học được xu hướng theo thời gian và seasonality.

### Demand-related features

Các feature liên quan đến demand được chuẩn bị để phục vụ bài toán forecasting và có thể được phát triển tiếp thành:
- lag features
- rolling statistics
- historical demand features

### Store / Product / Category features

Dữ liệu giữ các thông tin:
- item/product
- store
- state
- category

Những thông tin này giúp mô hình phân biệt hành vi demand giữa các sản phẩm và cửa hàng.

### Price / Event / SNAP features

Các yếu tố bên ngoài demand được giữ lại:
- price
- event
- SNAP
- SNAP theo state

---

## 11. Forecasting Dataset

Output của:

```text
10_forecasting_features.py
```

được lưu trên HDFS tại:

```text
/m5/forecasting_features
```

Dataset được lưu dưới dạng:
- Parquet
- Snappy Compression

Dataset hiện tại gồm:
- 32 parquet part files
- Tổng dung lượng khoảng 319 MB

Đây là dataset đầu vào được đề xuất cho bước Forecasting/Modeling.

---

## 12. Cách sử dụng Forecasting Dataset

Người thực hiện Modeling không cần chạy lại toàn bộ pipeline preprocessing.

Có thể đọc trực tiếp dataset trên HDFS:

```python
df = spark.read.parquet(
    "hdfs://localhost:9000/m5/forecasting_features"
)
```

Sau đó kiểm tra:

```python
df.printSchema()
df.show(5)
df.count()
```

Tiếp theo có thể thực hiện:
- Train / Validation / Test split theo thời gian.
- Xây dựng baseline model.
- Xây dựng forecasting model.
- Machine Learning model.
- Deep Learning model nếu cần.
- Đánh giá bằng các metric forecasting.

---

## 13. Lưu ý quan trọng cho Forecasting

Đây là bài toán time-series forecasting nên không nên chia train/test ngẫu nhiên.

Nên chia dữ liệu theo thời gian:

```text
Historical data
      ↓
    Train
      ↓
 Validation
      ↓
    Test
```

Không nên sử dụng random split vì có thể gây data leakage.

Đặc biệt cần chú ý:
- Không sử dụng thông tin của tương lai để tạo feature cho quá khứ.
- Lag features phải được tạo từ demand trong quá khứ.
- Rolling features phải đảm bảo không nhìn thấy target của ngày cần dự báo.
- Test set phải nằm sau train/validation theo timeline.

---

## 14. Báo cáo kết quả

Các report hiện tại:

```text
code/reports/data_quality_summary.txt
code/reports/advanced_eda_summary.txt
```

Hai report này dùng để:
- Kiểm chứng chất lượng dữ liệu.
- Chứng minh quá trình preprocessing.
- Giải thích đặc điểm của demand.
- Hỗ trợ lựa chọn feature/model ở bước Forecasting.

---

## 15. Phân chia công việc

### Phần đã hoàn thành

Data Engineering:
- Khảo sát dữ liệu.
- Đọc dữ liệu bằng Spark.
- Preprocessing.
- Kiểm tra dữ liệu.
- Phân tích Spark.
- Lưu dữ liệu Parquet.
- Đưa dữ liệu lên HDFS.
- Data Quality Report.
- Advanced EDA.
- Forecasting Feature Engineering.

### Phần tiếp theo

Forecasting / Modeling:

1. Đọc `/m5/forecasting_features`.
2. Kiểm tra schema và dữ liệu.
3. Xác định target.
4. Chia train/validation/test theo thời gian.
5. Xây dựng baseline.
6. Xây dựng forecasting model.
7. Đánh giá model.
8. So sánh các model.
9. Chọn model tốt nhất.
10. Xuất kết quả dự báo.

---

## 16. Pipeline tổng thể

```text
                    M5 RAW DATA
                         │
                         ▼
                Data Exploration
                         │
                         ▼
                 Spark Read / Schema
                         │
                         ▼
              Data Preprocessing
                         │
                         ▼
                 Processed Parquet
                         │
                         ▼
                       HDFS
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
       Data Quality              Advanced EDA
             │                       │
             └───────────┬───────────┘
                         ▼
              Feature Engineering
                         │
                         ▼
          /m5/forecasting_features
                         │
                         ▼
              Forecasting / Modeling
                         │
                         ▼
                  Evaluation
                         │
                         ▼
                 Final Forecast
```

---

## 17. Trạng thái hiện tại

### Data Engineering

[✓] Raw data exploration  
[✓] Spark processing  
[✓] Data preprocessing  
[✓] Parquet output  
[✓] HDFS storage  
[✓] Data quality validation  
[✓] Advanced EDA  
[✓] Forecasting feature engineering  
[✓] Forecasting-ready dataset  

### Forecasting / Modeling

[ ] Forecasting model  
[ ] Model evaluation  
[ ] Model comparison  
[ ] Final prediction
