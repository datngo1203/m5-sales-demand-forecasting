# Phân tích dữ liệu bán hàng và dự báo nhu cầu sản phẩm

Đồ án môn Nhập môn Big Data, đề tài 12; sử dụng bộ dữ liệu M5 và Apache Spark. Tên repository: `m5-sales-demand-forecasting`.

Phần bàn giao nằm trong `GuiDat/`. Phạm vi bổ sung xem `SPEC.md`.

Repository chứa source, tài liệu và kiểm tra. Sau khi clone, chép bộ dữ liệu bàn giao vào `GuiDat/data/processed_m5/` (32 file `*.parquet` và `_SUCCESS`) trước khi chạy. Dữ liệu, `.venv/`, `.runtime/` và `outputs/` không được đưa lên GitHub; kết quả được tạo lại bằng các lệnh bên dưới.

## Cấu trúc và các bước

```text
GuiDat/                    Mã và dữ liệu của thành viên còn lại
SPEC.md                    Spec v1 và các giả định
code/11_inspect_input.py    Kiểm tra đầu vào, đã bổ sung
code/12_spark_analysis.py   Tổng hợp bán hàng bằng Spark
tests/test_inspect_input.py Kiểm tra script đầu vào
tests/test_spark_analysis.py Kiểm tra tổng hợp và giá thiếu
outputs/                   Kết quả tạo khi chạy
```

Đã bổ sung script bước 2. Các bước tiếp theo dự kiến: `13_forecasting.py` cho huấn luyện/đánh giá, `14_dashboard.py` cho demo; hai file này chưa được triển khai.

| Bước | Thời lượng dự kiến | Kết quả kiểm chứng được |
|---|---|---|
| 1. Mở bàn giao và kiểm tra đầu vào | 1–2 giờ tối đa | Môi trường Python riêng, kiểm tra số dòng/schema, JSON đầu vào, xác định phụ thuộc thiếu |
| 2. Chuẩn bị Spark và tổng hợp | 45–60 phút | Chạy Spark đọc dữ liệu thật, xuất thống kê nhỏ và mức bao phủ giá |
| 3. Dự báo và đánh giá | 60–90 phút | Baseline + hồi quy, tách ngày đúng, CSV dự báo và MAE/RMSE |
| 4. Demo và chạy lại quy trình | 30–45 phút | Biểu đồ, hướng dẫn chạy và kiểm tra cuối |

Các khoảng trên là ước lượng. Bước 1 và bước 2 có lệnh chạy bên dưới; HDFS cần được kiểm thử riêng khi có dịch vụ.

## Chạy bước 1 bằng PowerShell

Từ thư mục gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-preflight.txt
.\.venv\Scripts\python.exe code\11_inspect_input.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_inspect_input.py -v
```

Kết quả nằm ở `outputs/input_inventory.json`. Script đọc footer của **tất cả** part files và 5 dòng mẫu của part đầu, không nạp 58 triệu dòng vào RAM. Script kiểm tra schema, số dòng, dấu hoàn tất Parquet và các phụ thuộc tìm thấy; đây chưa phải kiểm tra toàn bộ null/trùng lặp/chất lượng hay chạy thử Spark/HDFS.

## Chạy bước 2 bằng PowerShell

Môi trường: Python 3.11, PySpark 3.5.3, JDK 17. Spark chạy local trên CPU; không cần Docker. Cài phụ thuộc vào `.venv` của dự án:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-spark.txt
```

Nếu chưa có JDK 17, tải bản portable Temurin vào thư mục riêng của dự án (chỉ cần chạy một lần):

```powershell
New-Item -ItemType Directory -Force .runtime | Out-Null
Invoke-WebRequest 'https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse' -OutFile .runtime\jdk17.zip
Expand-Archive .runtime\jdk17.zip -DestinationPath .runtime
```

Thiết lập cho phiên PowerShell hiện tại và chạy:

```powershell
$env:JAVA_HOME = (Get-ChildItem .runtime -Directory -Filter 'jdk-17*' | Select-Object -First 1).FullName
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
$env:SPARK_LOCAL_IP = '127.0.0.1'
$env:PYSPARK_PYTHON = (Resolve-Path .venv\Scripts\python.exe).Path
.\.venv\Scripts\python.exe code\12_spark_analysis.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Nếu dùng JDK 17 đã cài sẵn, thay dòng gán `JAVA_HOME` bằng đường dẫn JDK đó. Mặc định `local[2]`, driver `2g`, 16 shuffle partitions; có thể đổi bằng `--master` và `--driver-memory`. Spark đọc Parquet và thực hiện tổng hợp bằng JVM; Python chỉ liệt kê tên file local và nhận kết quả tổng hợp để ghi CSV, không nạp toàn bộ dữ liệu thô. Đầu vào local là file hoặc thư mục Parquet có schema thống nhất, không dùng cột partition suy ra từ tên thư mục. Cảnh báo thiếu native Hadoop trên Windows có thể xuất hiện; việc liệt kê file bằng Python tránh lỗi native khi Hadoop duyệt thư mục local, không cần tải winutils từ nguồn bên ngoài cho luồng này.

Đầu vào tùy chọn là đường dẫn local, `file:///...` hoặc URI HDFS:

```powershell
.\.venv\Scripts\python.exe code\12_spark_analysis.py --input 'hdfs://localhost:9000/m5/processed_m5' --output outputs\analysis_hdfs
```

HDFS cần NameNode/DataNode hoạt động và máy chạy Spark truy cập được các địa chỉ dịch vụ. **Chưa kiểm thử HDFS** trên máy này; hỗ trợ URI trong code không chứng minh đã chạy HDFS.

Kết quả tại `outputs/analysis/`:

| File | Nội dung |
|---|---|
| `daily_category_store.csv` | Theo ngày × nhóm sản phẩm (`cat_id`) × cửa hàng |
| `daily_sales.csv` | Tổng theo ngày |
| `category_sales.csv` | Tổng theo nhóm sản phẩm |
| `store_sales.csv` | Tổng theo cửa hàng |
| `analysis_report.json` | Trạng thái thành công, nguồn, thời gian, phiên bản, kiểm tra đầu vào, tổng và số dòng xuất |

Các bảng gồm `rows`, `units`, `priced_rows`, `priced_units`, `revenue_known`, `price_row_coverage`, `price_unit_coverage`. Doanh thu là tổng `demand × sell_price` chỉ với giá hữu hạn không âm; giá 0 hợp lệ. Giá null/NaN/vô cực/âm được coi là chưa biết, không điền 0 hoặc lấy giá tương lai. Nhóm hoàn toàn không có giá có doanh thu trống, không phải 0. Tỷ lệ bao phủ tính theo số dòng và số lượng bán; nếu tổng lượng bán bằng 0 thì bao phủ lượng bán để trống. Doanh thu dùng số thực theo giá nguồn nên có sai số dấu phẩy động nhỏ.

Script từ chối tập rỗng, thiếu cột, ngày sai kiểu/null, mã sản phẩm/nhóm/cửa hàng rỗng hoặc null, lượng bán null/không hữu hạn/âm/không nguyên. Dữ liệu bàn giao được giữ nguyên; chưa kiểm tra hoặc loại trùng khóa sản phẩm–cửa hàng–ngày. Chỉ coi thư mục kết quả là hoàn tất khi có `analysis_report.json` với `status=success` của lần chạy đó. Các CSV có thể chưa đầy đủ nếu lần chạy lỗi; báo cáo thành công cũ được xóa trước khi đọc dữ liệu.

### Kết quả kiểm chứng ngày 25/10/2026

Đã chạy local trên toàn bộ 32 part files, **58.327.370 dòng**, khoảng ngày **29/01/2011–24/04/2016**. Python **3.11.9**, Spark **3.5.3**, Temurin Java **17.0.20.1**, `local[2]`, driver `2g`. Thời gian xử lý trong script **22,91 giây** (không gồm khởi động JVM/cài đặt).

- Tổng lượng bán: **65.695.409**; doanh thu biết giá: **187.676.570,02** theo đơn vị giá dữ liệu nguồn.
- Giá hợp lệ: **46.027.957/58.327.370 dòng (78,91%)**; bao phủ **100% lượng bán**. Có **12.299.413** dòng chưa biết giá, đều có lượng bán 0 trong bộ dữ liệu này.
- Xuất **57.390** dòng ngày × nhóm × cửa hàng, **1.913** dòng ngày, **3** dòng nhóm và **10** dòng cửa hàng; CSV lớn nhất khoảng **4,63 MB**.
- Kiểm tra ngày/mã/lượng bán không hợp lệ: **0 dòng**. Đối chiếu độc lập bằng PyArrow đọc toàn bộ 32 file khớp các tổng; cả 4 bảng CSV bảo toàn các tổng và có khóa nhóm duy nhất. Bằng chứng lưu tại `outputs/analysis_validation.json`, nhật ký tại `outputs/step2_run.log` và `outputs/step2_tests.log`.
- Bộ kiểm tra đạt **5/5**, gồm kiểm tra đầu vào và chạy Spark với dữ liệu nhỏ để kiểm tra tổng hợp, giá thiếu/không hợp lệ, nhóm không có giá, lượng bán 0 và đầu vào lỗi.
- HDFS chưa chạy; dự báo và dashboard thuộc các bước tiếp theo.
