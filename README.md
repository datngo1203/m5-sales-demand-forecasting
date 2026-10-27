# Phân tích dữ liệu bán hàng và dự báo lượng bán sản phẩm

Đồ án môn Nhập môn Big Data, đề tài 12. Spark tổng hợp dữ liệu M5; scikit-learn
dự báo lượng bán 28 ngày cho nhóm 20 sản phẩm; Streamlit trình bày bán hàng,
dự báo và sai lệch để tham khảo kế hoạch hàng hóa.

Đọc [giải thích dự án](docs/GIAI_THICH_DU_AN.md) để hiểu kiến trúc, nguồn dữ liệu,
phương pháp, kết quả và giới hạn. Phần mã bàn giao gốc của thành viên nằm trong
`GuiDat/` và được giữ nguyên.

## Cấu trúc

```text
code/                   Kiểm tra đầu vào, Spark, dự báo V1/V2, dashboard và CSS
config/forecast.json    Thiết lập phương án dự báo mặc định đã chốt
GuiDat/                 Phần Data Engineering bàn giao của thành viên
infra/hdfs/             Docker Compose, cấu hình và lệnh nạp HDFS
resources/              Bảng V3 24 dòng cần hiển thị trên dashboard
scripts/                Helper pipeline, quy trình đánh giá và đối chiếu HDFS
tests/                  Kiểm thử bằng dữ liệu nhỏ tự tạo
.github/workflows/      CI chạy unittest trên Python3.11/JDK17
.streamlit/config.toml  Theme mặc định
requirements-*.txt      Phiên bản thư viện
run_pipeline.ps1        Kiểm tra đầu vào, Spark, dự báo và tests
run_hdfs_demo.ps1       Nạp HDFS, chạy Spark và đối chiếu local
docs/GIAI_THICH_DU_AN.md Kiến trúc, phương pháp và giới hạn
```

Git không chứa dữ liệu Parquet, môi trường `.venv`, JDK, model đã train, cache
hoặc output chạy. Log/report bên trong GuiDat là bản bàn giao gốc được giữ để
bảo toàn công việc thành viên; không dùng chúng thay bằng chứng chạy hiện tại.

## 1. Cài môi trường

Windows, Python **3.11**, JDK **17**, PowerShell. Docker Desktop Linux containers
chỉ cần cho phần HDFS. Sau khi cài Python/JDK, chạy tại thư mục chứa README:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.txt
.\.venv\Scripts\python.exe -m pip check
New-Item -ItemType Directory -Force -Path GuiDat/data/processed_m5, outputs, .runtime
```

Đặt `JAVA_HOME` tới thư mục JDK17 thật có `bin/java.exe`. Thay giá trị dòng đầu:

```powershell
$env:JAVA_HOME = 'THAY_BANG_DUONG_DAN_JDK_17_TREN_MAY'
$env:PATH = "$env:JAVA_HOME/bin;$env:PATH"
$env:SPARK_LOCAL_IP = '127.0.0.1'
$env:PYSPARK_PYTHON = (Resolve-Path .venv/Scripts/python.exe).Path
java -version
```

Mỗi cửa sổ PowerShell mới cần thiết lập lại biến nếu chưa đặt trong Windows.

## 2. Đặt dữ liệu

Nhận bộ `processed_m5` từ thành viên Data Engineering. Chép **32 file Parquet
và `_SUCCESS`** vào `GuiDat/data/processed_m5/`, không lồng thêm thư mục GuiDat.
Bộ đã dùng có 58.327.370 dòng và 22 cột, khoảng ngày 29/01/2011–24/04/2016.
Pipeline kiểm tra schema và hash từ file thật, không dựa vào con số trong hướng dẫn.

Các cột bắt buộc gồm `item_id`, `store_id`, `cat_id`, `state_id`, `date`, `demand`,
`sell_price`; `date` phải là Parquet DATE. Đây là dữ liệu đã tiền xử lý, không cần
chạy lại `GuiDat/code/04_spark_preprocessing.py` để ghi đè dữ liệu.

## 3. Tạo kết quả và mở dashboard

```powershell
.\run_pipeline.ps1 -SkipInstall
.\.venv\Scripts\python.exe -m streamlit run code/14_dashboard.py
```

Mở http://127.0.0.1:8501. Pipeline mặc định dùng CA_1/recent và phương án
`blend`: 50% Random Forest + 50% trung bình 4 tuần cùng thứ. `config/forecast.json`
giữ thiết lập này; không chọn lại phương pháp bằng kết quả test.

Lần đầu không có cache sẽ huấn luyện theo cấu hình cố định. Lần sau tái dùng
cache nếu nguồn/cấu hình phù hợp. Không chạy pipeline khi đang trình bày ứng dụng
vì bước xuất ghi lại output. Nếu mở dashboard trước khi có output, ứng dụng sẽ
báo thiếu dữ liệu và hướng dẫn chọn nguồn kết quả.

```powershell
# Chạy bản V1:
.\run_pipeline.ps1 -SkipInstall -V1
# Đổi cửa hàng/nhóm sản phẩm, giữ phương pháp đã chốt:
.\run_pipeline.ps1 -SkipInstall -Store TX_1 -Panel legacy
```

Output chính: `outputs/analysis`, `outputs/forecast`; cache mới nằm ở
`outputs/forecast_v3_pipeline_cache`. Dashboard chỉ đọc CSV nhỏ; đổi bộ lọc
không làm mô hình học lại. Phân tích và dự báo phải dùng cùng nguồn dữ liệu.

## 4. Kiểm thử

Sau khi cài thư viện/JDK và thiết lập biến ở bước 1:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests tự tạo dữ liệu nhỏ; không cần bộ M5 đầy đủ và không train lại dữ liệu thật.
CI trên GitHub chạy cùng lệnh. Fixture kiểm tra bảng nghiên cứu là dữ liệu giả,
không phải các chỉ số được công bố trong bảng V3.

## 5. HDFS

Cần dữ liệu và kết quả local của bước 3 để đối chiếu. Bật Docker Desktop rồi chạy:

```powershell
.\run_hdfs_demo.ps1
```

Mở http://127.0.0.1:9870. Xem [hướng dẫn HDFS](infra/hdfs/README.md) để vận hành
và dừng mà vẫn giữ volume. HDFS gồm một NameNode/một DataNode trên cùng máy;
Spark local[2] đọc HDFS. Chưa kiểm chứng cụm nhiều máy.

## 6. Demo ba trang

1. **Tổng quan bán hàng:** lọc cửa hàng/nhóm/ngày; đọc lượng bán, doanh thu biết
   giá và bao phủ giá; xem biểu đồ tuần, so kỳ trước khi đủ dữ liệu.
2. **Dự báo sản phẩm:** đọc ngày lập và khoảng mô phỏng 28 ngày; xem tổng và bốn
   tuần. Tích phương pháp ngay trên biểu đồ lịch sử để hiện/ẩn đường, bật thực
   tế khi cần đối chiếu. Có tải CSV và phần tính thử hàng hóa từ số giả định.
3. **Kiểm tra độ tin cậy:** đọc MAE/RMSE/dư-thiếu theo sản phẩm; bảng V3 ba seed
   nằm riêng, dùng `resources/v3_test_metrics.csv`, khác số demo một seed.

Tổng và bảng tuần luôn dùng **Dự báo cuối**; các ô tích chỉ đổi đường hiển thị.
Đây là mô phỏng lịch sử, chưa đủ cơ sở tự động nhập hàng.

Các helper `scripts/run_forecast_v2.py`, `run_forecast_v3.py`, `report_forecast_v2.py`
được giữ vì pipeline/tests dùng chúng để kiểm tra thủ tục và cache. Chúng không
thay lệnh khởi động ở bước 3; không chạy lại thí nghiệm đã tiêu thụ test.
