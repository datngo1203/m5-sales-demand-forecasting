# Phân tích dữ liệu bán hàng và dự báo nhu cầu sản phẩm

Đồ án môn Nhập môn Big Data, đề tài 12; sử dụng bộ dữ liệu M5 và Apache Spark. Tên repository: `m5-sales-demand-forecasting`.

Phần bàn giao nằm trong `GuiDat/`. Phạm vi bổ sung xem `SPEC.md`.

Nguồn dữ liệu, chuỗi xử lý bàn giao và giới hạn đối chiếu xem [DATA_SOURCE.md](DATA_SOURCE.md).

Trình tự thao tác demo, lời thuyết trình 6–8 phút và câu hỏi phản biện xem [DEMO.md](DEMO.md).

Repository chứa source, tài liệu và kiểm tra. Sau khi clone, chép bộ dữ liệu bàn giao vào `GuiDat/data/processed_m5/` (32 file `*.parquet` và `_SUCCESS`) trước khi chạy. Dữ liệu, `.venv/`, `.runtime/` và `outputs/` không được đưa lên GitHub; kết quả được tạo lại bằng các lệnh bên dưới.

## Cấu trúc và các bước

```text
GuiDat/                    Mã và dữ liệu của thành viên còn lại
SPEC.md                    Spec v1 và các giả định
code/11_inspect_input.py    Kiểm tra đầu vào, đã bổ sung
code/12_spark_analysis.py   Tổng hợp bán hàng bằng Spark
code/13_forecasting.py      Chọn 20 chuỗi, dự báo và đánh giá
code/14_dashboard.py        Demo Streamlit đọc CSV tổng hợp
run_pipeline.ps1            Chạy lại bước 1–3 và toàn bộ kiểm tra
tests/test_inspect_input.py Kiểm tra script đầu vào
tests/test_spark_analysis.py Kiểm tra tổng hợp và giá thiếu
tests/test_forecasting.py   Kiểm tra chia ngày, chống rò rỉ và xuất dự báo
tests/test_dashboard.py     Kiểm tra bộ lọc, biểu đồ và lỗi đầu vào dashboard
outputs/                   Kết quả tạo khi chạy
```

Đã bổ sung source bước 1–4. Bước 4 trong kế hoạch README là demo và chạy lại quy trình; mục 4 trong SPEC (chia ngày, đánh giá) đã được triển khai trong `13_forecasting.py`.

| Bước | Thời lượng dự kiến | Kết quả kiểm chứng được |
|---|---|---|
| 1. Mở bàn giao và kiểm tra đầu vào | 1–2 giờ tối đa | Môi trường Python riêng, kiểm tra số dòng/schema, JSON đầu vào, xác định phụ thuộc thiếu |
| 2. Chuẩn bị Spark và tổng hợp | 45–60 phút | Chạy Spark đọc dữ liệu thật, xuất thống kê nhỏ và mức bao phủ giá |
| 3. Dự báo và đánh giá | 60–90 phút | Baseline + hồi quy, tách ngày đúng, CSV dự báo và MAE/RMSE |
| 4. Demo và chạy lại quy trình | 30–45 phút | Biểu đồ, hướng dẫn chạy và kiểm tra cuối |

Các khoảng trên là ước lượng. Các bước có lệnh chạy bên dưới; HDFS cần được kiểm thử riêng khi có dịch vụ.

## Chạy bước 1 bằng PowerShell

Từ thư mục gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-preflight.txt
.\.venv\Scripts\python.exe code\11_inspect_input.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_inspect_input.py -v
```

Kết quả nằm ở `outputs/input_inventory.json`. Script băm SHA-256 toàn bộ byte theo luồng, đọc footer của **tất cả** part files và 5 dòng mẫu của part đầu, không nạp 58 triệu dòng vào RAM. Script kiểm tra schema, số dòng, dấu hoàn tất Parquet và ghi phiên bản thư viện thực tế; đây chưa phải kiểm tra toàn bộ null/trùng lặp/chất lượng hay chạy thử Spark/HDFS.

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
- HDFS chưa chạy; phần dự báo được bổ sung ở bước 3 bên dưới, dashboard thuộc bước tiếp theo.

## Chạy bước 3 bằng PowerShell

Sau khi thiết lập `JAVA_HOME`, `PATH`, `SPARK_LOCAL_IP`, `PYSPARK_PYTHON` như bước 2:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-forecast.txt
.\.venv\Scripts\python.exe code\13_forecasting.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Mặc định cửa hàng `CA_1`; có thể đổi bằng `--store CA_2`. `--input`, `--output`, `--master`, `--driver-memory` giống bước 2. Spark đọc và kiểm tra toàn bộ đầu vào, xếp hạng tổng lượng bán **chỉ trong tập train**, chọn 20 sản phẩm trong cửa hàng (hòa điểm thì theo `item_id`), rồi gom dữ liệu ngày của 20 chuỗi sang Python. Không thu toàn bộ dữ liệu thô về Python. Script yêu cầu mỗi chuỗi được chọn có đúng một dòng mỗi ngày trên toàn khoảng dữ liệu; ngày thiếu/trùng bị từ chối, không tự điền lượng bán 0.

Hai khoảng cuối lần lượt là validation 28 ngày và test 28 ngày; phần trước đó là train. Baseline `seasonal_naive` lặp tuần cuối đã biết. Random Forest dùng lag 1/7/14/28, trung bình 7/28 ngày trước, thứ/ngày trong năm/tháng, số ngày từ đầu chuỗi và mã sản phẩm one-hot. Giá, đặc trưng dự báo bàn giao và lượng bán tương lai không được dùng. RF chạy scikit-learn trên panel nhỏ sau khi Spark xử lý dữ liệu lớn.

RF dùng 100 cây, seed 42, 2 CPU workers; thử hai bộ `(max_depth=12, min_samples_leaf=5)` và `(max_depth=None, min_samples_leaf=2)`. Chọn bằng MAE validation rồi huấn luyện lại trên train+validation để đánh giá test một lần. Mỗi cửa sổ có một mốc dự báo cố định: ngày thứ hai trở đi dùng các dự báo đã sinh khi cần lag/trung bình, không cập nhật bằng thực tế trong cửa sổ. Khi sang test, lượng bán thật của validation đã thuộc quá khứ và được phép dùng. 28 ngày đầu lịch sử chỉ làm lag, không làm nhãn huấn luyện.

Kết quả tại `outputs/forecast/`:

| File | Nội dung |
|---|---|
| `selected_series.csv` | 20 sản phẩm, thứ hạng và tổng lượng bán train |
| `history.csv` | Lịch sử ngày của 20 chuỗi để bước dashboard dùng |
| `predictions.csv` | Validation/test × hai mô hình, mốc dự báo, horizon 1–28, thực tế và dự báo |
| `metrics.csv` | MAE/RMSE từng sản phẩm và `ALL` cho từng mô hình, từng tập |
| `random_forest.joblib` | Mô hình đã huấn luyện lại trên train+validation |
| `forecast_report.json` | Trạng thái, nguồn, phiên bản, cách chia ngày, tham số, độ đo, thời gian |

MAE/RMSE tính theo lượng bán/ngày/sản phẩm; `ALL` gộp các quan sát của 20 chuỗi, không tính sai số tổng cửa hàng. Dự báo RF là số thực không âm, không làm tròn trước khi đánh giá. Đây là dự báo **lượng bán quan sát được** trên nhóm bán nhiều của một cửa hàng; không đại diện mọi sản phẩm và không suy ra nhu cầu bị mất vì hết hàng. Không cam kết RF thắng baseline. Dự báo xuất là backtest 28 ngày có thực tế để đối chiếu, chưa phải dự báo sau ngày cuối dữ liệu.

Chỉ coi lần chạy hoàn tất khi có `forecast_report.json` với `status=success`; báo cáo cũ bị xóa trước khi đọc dữ liệu, các file khác có thể dở dang nếu lỗi. Mô hình và thứ tự đặc trưng/sản phẩm được ghi trong report; chỉ nạp file joblib từ nguồn tin cậy. HDFS cần kiểm thử ở bước riêng.

### Kết quả bước 3 ngày 25/10/2026

Chạy thành công local trên **58.327.370 dòng**, chọn **20 sản phẩm của CA_1** bằng doanh số train. Panel có **38.260 dòng** (20 × 1.913 ngày). Train: **29/01/2011–28/02/2016**; validation: **29/02–27/03/2016**; test: **28/03–24/04/2016**. Có 36.580 mẫu train sau khi tạo lag; huấn luyện lại có 37.140 mẫu. Bộ RF được chọn: `max_depth=12`, `min_samples_leaf=5`.

| Tập | Mô hình | MAE | RMSE |
|---|---|---:|---:|
| Validation | Lặp tuần trước | 8,2875 | 15,1952 |
| Validation | Random Forest | 7,0584 | 10,2581 |
| Test | Lặp tuần trước | 8,0625 | 12,4043 |
| Test | Random Forest | 7,0504 | 10,4685 |

Trên test, RF giảm khoảng **12,6% MAE** và **15,6% RMSE** so với baseline. RF kết hợp lịch sử gần đây, lịch ngày và dữ liệu nhiều sản phẩm; chưa có thử nghiệm tách riêng đóng góp của từng nhóm đặc trưng. Kết quả chưa chứng minh mô hình tốt hơn ở cửa hàng, sản phẩm hay thời điểm khác. Tập test chỉ có một cửa sổ 28 ngày; chưa đánh giá cuốn chiếu nhiều mốc hoặc dự báo nhu cầu khi hết hàng.

Thời gian xử lý **128,64 giây**, không gồm cài đặt/khởi động JVM, trên `local[2]`, driver `2g`, Python **3.11.9**, Spark **3.5.3**, Java **17.0.20.1**, NumPy **2.1.3**, scikit-learn **1.5.2**. Xuất **2.240 dòng dự báo** (validation + test × 20 sản phẩm × 28 ngày × 2 mô hình), **84 dòng độ đo**, danh sách lựa chọn, lịch sử và mô hình.

Bộ kiểm tra đạt **9/9**, gồm 4 kiểm tra mới cho dự báo và 5 kiểm tra bước trước. Các kiểm tra mới bao gồm thay đổi dữ liệu tương lai không làm thay đổi mẫu train, dùng dự báo trước đó cho lag, sản phẩm bán nhiều chỉ trong tương lai không được chọn, ngày thiếu/trùng và xóa báo cáo thành công cũ khi chạy lại lỗi. Đối chiếu thêm các CSV thực tế bằng thư viện chuẩn: khóa duy nhất, tổng train của sản phẩm đã chọn, nhãn thực tế khớp lịch sử, horizon từ mốc cố định, baseline lặp tuần cuối và tính lại toàn bộ 84 dòng MAE/RMSE đều khớp. Bằng chứng tại `outputs/forecast_validation.json`; nhật ký tại `outputs/step3_run.log`, `outputs/step3_tests.log`.

## Chạy bước 4 và chạy lại quy trình

Cài và mở dashboard từ thư mục gốc dự án:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.txt
.\.venv\Scripts\python.exe -m streamlit run code\14_dashboard.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Mở `http://127.0.0.1:8501`. Dashboard không cần Spark/Java khi xem kết quả có sẵn. Phiên bản đã chạy: Streamlit **1.50.0**, pandas **2.2.3**; các phiên bản xử lý/mô hình như bước 3.

- Chọn cửa hàng và nhóm sản phẩm để xem lượng bán, doanh thu phần biết giá, bao phủ giá theo dòng/lượng bán và hai biểu đồ theo ngày.
- Chọn khoảng ngày để lọc doanh thu và lịch sử sản phẩm; tổng lượng bán, doanh thu và bao phủ giá được tính lại trong khoảng chọn. Biểu đồ thực tế/dự báo và MAE/RMSE vẫn dùng đủ 28 ngày của tập đánh giá.
- Chọn sản phẩm trong panel dự báo và tập `test` hoặc `validation` để xem lịch sử, biểu đồ thực tế so với hai mô hình, MAE/RMSE từng sản phẩm và `ALL`, bảng 28 ngày và tải CSV.
- Doanh thu thuộc toàn bộ sản phẩm của nhóm/cửa hàng; không phải doanh thu riêng sản phẩm đang dự báo. Mô hình dự báo lượng bán, không dự báo doanh thu. Chọn nhóm doanh thu không thay đổi panel dự báo.
- Hiện chỉ CA_1 có dự báo. Chọn cửa hàng khác vẫn xem được doanh thu và hiện hướng dẫn tạo dự báo bằng `13_forecasting.py --store CA_2`. Chạy lại bước 3 mặc định thay bộ dự báo cũ bằng một cửa hàng mới.
- Trường “Thư mục kết quả” cho phép chọn thư mục khác có hai thư mục con `analysis/` và `forecast/`; hoặc đặt biến môi trường `M5_OUTPUT_DIR`. Hai report phải có `status=success` và cùng nguồn đầu vào. Thiếu file/báo cáo lỗi được hiển thị cùng hướng dẫn chạy, không mở mô hình joblib hoặc Parquet trong giao diện.

Dashboard đọc bốn CSV: `daily_category_store.csv`, `history.csv`, `predictions.csv`, `metrics.csv` và hai JSON báo cáo. Không đọc 58 triệu dòng, không huấn luyện lại khi đổi bộ lọc. Doanh thu thiếu hoàn toàn được giữ trống/“Chưa biết”; số 0 chỉ dùng khi dữ liệu thực sự có giá trị 0. Chỉ xem các kết quả đã chạy hoàn tất; không ghi đè CSV trong lúc người khác xem demo.

Chạy lại bước 1–3 và tất cả kiểm tra, dừng nếu bước nào lỗi:

```powershell
.\run_pipeline.ps1
# Nếu đã cài phụ thuộc:
.\run_pipeline.ps1 -SkipInstall
# Chỉ chạy kiểm tra dashboard:
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_dashboard.py -v
```

Script dùng `.venv` có sẵn, JDK từ `JAVA_HOME` hoặc `.runtime/jdk-17*`, lưu log vào `outputs/pipeline_*.log`; không tự mở server dashboard. Tạo `.venv`, đặt dữ liệu và chuẩn bị JDK theo bước 1–2 trước lần chạy đầu. Tắt server Streamlit bằng Ctrl+C trong terminal khởi chạy.

### Kết quả bước 4 ngày 25/10/2026

Đã chạy lại thành công toàn bộ pipeline local trên **58.327.370 dòng**: Spark tổng hợp **40,94 giây**, dự báo **44,67 giây** (thời gian trong từng script, không gồm khởi động/cài đặt). Kết quả test giữ nguyên: baseline MAE **8,0625**, RMSE **12,4043**; Random Forest MAE **7,0504**, RMSE **10,4685**. Đây là backtest một cửa sổ 28 ngày trên 20 sản phẩm CA_1.

Toàn bộ **12/12 kiểm tra đạt**, gồm 3 kiểm tra dashboard mới: đổi cửa hàng/nhóm/sản phẩm/tập và tạo đủ 4 biểu đồ; thông báo khi thiếu kết quả; từ chối report chưa hoàn tất/khác nguồn và giữ doanh thu chưa biết. Bộ kiểm tra dùng Streamlit AppTest theo [tài liệu chính thức](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).

Kiểm tra thêm trên CSV thật: **57.390** dòng tổng hợp, **38.260** dòng lịch sử, **2.240** dòng dự báo và **84** dòng độ đo; tổng bốn CSV **6.110.662 byte (~6,11 MB)**. AppTest mở được dữ liệu thật, tạo 4 biểu đồ, bảng 28 ngày, độ đo validation/test khớp CSV; chuyển CA_2 hiện đúng thông báo chưa có dự báo. Đã mở và kiểm tra giao diện trình duyệt tại `http://127.0.0.1:8501`; health endpoint trả `ok`; `pip check` không báo phụ thuộc hỏng.

Bằng chứng lần chạy này: `outputs/step4_pipeline.log`, `outputs/pipeline_tests.log`, `outputs/step4_dashboard_tests.log`, `outputs/step4_app_smoke.log`, `outputs/step4_validation.json`. HDFS chưa kiểm thử; chưa đánh giá nhiều cửa sổ thời gian hay dự báo sau ngày cuối dữ liệu. Không tạo Word/PPT trong bước này.

### Bước 5 theo SPEC — dashboard ngày 25/10/2026

Mục 5 của SPEC tương ứng phần demo đã gọi là bước 4 trong kế hoạch README ở trên. Dashboard nằm tại `code/14_dashboard.py`; dùng lệnh Streamlit trong phần hướng dẫn trên và mở `http://127.0.0.1:8501`.

Đã bổ sung bộ lọc khoảng ngày cho doanh thu và lịch sử, xử lý chọn chưa đủ hai ngày hoặc sản phẩm không có lịch sử trong khoảng chọn. Số sản phẩm trong chú thích sai số lấy từ báo cáo thay vì cố định 20. Bộ lọc ngày không thay đổi cửa sổ dự báo hoặc MAE/RMSE.

Chạy AppTest trên dữ liệu thật: đủ **4 biểu đồ**, bảng đối chiếu **28 ngày**, MAE/RMSE validation/test khớp CSV; kiểm tra chọn cả **10 cửa hàng**, trong đó **CA_1** có dự báo cho **20 sản phẩm**. Lọc tháng 03/2016 ở CA_1 cho **136.557** đơn vị bán, khớp tổng hợp độc lập. Bốn CSV giao diện đọc có **6.110.662 byte (~6,11 MB)**, không đọc lại Parquet. Health endpoint của server local trả `ok`.

Toàn bộ **13/13 kiểm tra đạt** trong **27,74 giây**, gồm **4 kiểm tra dashboard**. Nhật ký: `outputs/step5_dashboard_tests.log`, `outputs/step5_tests.log`, `outputs/step5_app_smoke.log`; kết quả dữ liệu thật tại `outputs/step5_validation.json`. Lần này sử dụng kết quả tổng hợp/dự báo có sẵn, không chạy lại toàn bộ dữ liệu thô; HDFS chưa kiểm thử.

## Bước 6 theo SPEC — lệnh chạy, môi trường, kiểm tra và nguồn dữ liệu

Từ thư mục gốc, sau khi đặt dữ liệu và JDK 17 theo hướng dẫn bước 1–2:

```powershell
python -m venv .venv
.\run_pipeline.ps1
# Các lần sau dùng môi trường đã cài:
.\run_pipeline.ps1 -SkipInstall
# Mở demo sau khi pipeline thành công:
.\.venv\Scripts\python.exe -m streamlit run code\14_dashboard.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Dùng Python **3.11** để tạo `.venv`. Script cài chuỗi `requirements-dashboard.txt`
→ `requirements-forecast.txt` → `requirements-spark.txt` → `requirements-preflight.txt`,
chạy `pip check`, kiểm tra đầu vào, Spark, dự báo và toàn bộ unittest; mỗi lệnh
thất bại sẽ dừng pipeline. `-SkipInstall` bỏ cài đặt nhưng vẫn kiểm tra phụ thuộc.
Lệnh này dùng đầu vào local mặc định, không kiểm chứng HDFS. Không tự tải dữ liệu
hay JDK; `JAVA_HOME` có sẵn được ưu tiên hơn JDK portable trong `.runtime`.

| Thành phần | Phiên bản môi trường đã chạy |
|---|---|
| OS / Python | Windows / 3.11.9 (64 bit) |
| Java / Spark | Temurin 17.0.20.1 / PySpark 3.5.3 |
| PyArrow / NumPy | 23.0.1 / 2.1.3 |
| scikit-learn | 1.5.2 |
| pandas / Streamlit | 2.2.3 / 1.50.0 |

Inventory ghi phiên bản thư viện **thực tế**, `JAVA_HOME`, Python, thời điểm UTC,
tên/kích thước/SHA-256 của 32 file Parquet. Java đang chạy trong JVM và cấu hình
Spark nằm trong hai report phân tích/dự báo. Các requirements ghim thư viện
chính; chưa khóa toàn bộ phụ thuộc gián tiếp hoặc thử trên máy sạch.
Thông tin nguồn và giới hạn tái lập được ghi tại [DATA_SOURCE.md](DATA_SOURCE.md).

Kiểm tra đầu vào bao gồm đối chiếu SHA-256 độc lập bằng thư viện chuẩn, phát hiện
file thay đổi và không để báo cáo `success` cũ tồn tại sau lần chạy lại lỗi.
Các kiểm tra Spark/dự báo/dashboard tiếp tục dùng trong cùng lệnh pipeline.

### Kết quả bước 6 ngày 25/10/2026

Đã chạy `.\run_pipeline.ps1 -SkipInstall` thành công trên **32 file,
58.327.370 dòng**; `pip check` trả `No broken requirements found`.
Spark tổng hợp **37,62 giây**, dự báo **47,20 giây** (thời gian trong từng
script); toàn bộ **14/14 kiểm tra đạt** trong **15,25 giây**. Inventory có đủ
32 SHA-256 và phiên bản của cả 6 thư viện chính. RF test MAE **7,0504**,
RMSE **10,4685**; baseline MAE **8,0625**, RMSE **12,4043**.

Nhật ký toàn bộ lần chạy: `outputs/step6_pipeline.log`; kiểm tra phụ thuộc:
`outputs/pipeline_dependencies.log`; kiểm tra logic: `outputs/pipeline_tests.log`.
Inventory và hai report trong `outputs/analysis/`, `outputs/forecast/` được tạo
lại từ dữ liệu thật. Dashboard được kiểm tra qua AppTest trong bộ kiểm tra;
lần này không kiểm tra lại bằng trình duyệt. Chưa thử cài trên máy sạch,
chưa chạy HDFS hoặc đối chiếu dữ liệu CSV gốc.

### Kiểm tra trước khi push ngày 25/10/2026

Đọc lại source các bước 11–14, bộ kiểm tra, chuỗi requirements và lệnh pipeline.
Chạy lại `run_pipeline.ps1 -SkipInstall` thành công trên toàn bộ **58.327.370 dòng**;
**14/14 kiểm tra đạt** trong **30,91 giây**. Tổng hợp Spark **38,75 giây**, dự báo
**73,01 giây** theo report của lần chạy; MAE/RMSE test giữ nguyên bảng phía trên.
Đối chiếu CSV dự báo có đủ **2.240 dòng**, mọi ngày dự báo sau mốc dự báo;
CA_1 tháng 03/2016 có **136.557** đơn vị bán. Health endpoint dashboard trả `ok`.
Log lần kiểm tra: `outputs/review_pipeline.log`. Có ResourceWarning về socket
trong PySpark khi chạy unittest; quá trình kết thúc với `OK` và exit code 0.
Chưa chạy lại bằng trình duyệt, trên máy sạch hoặc HDFS trong lượt kiểm tra này.
