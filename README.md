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
code/13_forecasting.py      V1: chọn 20 chuỗi, dự báo và đánh giá
code/15_forecasting_v3.py   V2 mặc định: blend đã qua cổng V3, tái dùng cache
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

## Dự báo và đánh giá

Sau khi chuẩn bị môi trường như trên, chạy:

```powershell
.\.venv\Scripts\python.exe code\13_forecasting.py
```

Spark chọn 20 sản phẩm CA_1 bằng tổng lượng bán trước cửa sổ validation đầu tiên.
Danh sách giữ cố định trong toàn bộ thí nghiệm; các chuỗi thiếu hoặc trùng ngày bị từ chối.
Có bốn cửa sổ validation liên tiếp, mỗi cửa sổ 28 ngày, và 28 ngày cuối làm test.
Mỗi cửa sổ dự báo từ một mốc cố định, không cập nhật lượng bán thật trong 28 ngày đó.

RF thử sáu cấu hình: lịch sử toàn bộ/365/180 ngày × hai bộ độ sâu và kích thước lá
`(12, 5)` hoặc `(None, 2)`. Mỗi cấu hình có 100 cây, seed 42 và 2 workers.
Chọn cấu hình theo MAE gộp bốn cửa sổ; hòa thì xét RMSE.
Thử thêm một RF dự báo trực tiếp 28 đầu ra, dùng cửa sổ/độ sâu của cấu hình đệ quy tốt nhất.
Chọn giữa bảy phương án RF bằng validation, rồi chọn baseline hoặc RF cho từng sản phẩm
theo MAE gộp validation, hòa dùng baseline.
Mô hình được fit lại trên dữ liệu trước test, với cửa sổ lịch sử đã chọn.

Đặc trưng gồm lag 1/7/14/28, mean 7/28, lịch ngày, số ngày từ đầu chuỗi, mã sản phẩm,
tỷ lệ ngày bán 0 trong 7/28 ngày, chuỗi ngày bán 0 liên tiếp tối đa 28 ngày và mean_7 trừ mean_28.
Đặc trưng chỉ dùng quá khứ hoặc dự báo đã sinh. Chưa đưa giá, sự kiện, SNAP vào mô hình.
RF dùng scikit-learn trên panel nhỏ; Spark vẫn kiểm tra và chọn panel từ toàn bộ dữ liệu.

### Đầu ra tại outputs/forecast

| File | Nội dung |
|---|---|
| selected_series.csv | 20 sản phẩm và tổng lượng bán trước validation đầu tiên |
| history.csv | Lịch sử ngày của panel |
| rolling_metrics.csv | MAE/RMSE và dư/thiếu từng sản phẩm cho 7 phương án RF và baseline qua 4 cửa sổ |
| model_selection.csv | Cách được chọn cho từng sản phẩm và MAE validation của baseline/RF |
| predictions.csv | Thực tế và ba đường dự báo ở validation cuối và test |
| metrics.csv | Sai số từng sản phẩm và ALL, tổng thực tế/dự báo, bias_units, bias_pct |
| random_forest.joblib | RF đã fit lại trước test; đọc cùng thứ tự đặc trưng/sản phẩm trong report |
| forecast_report.json | Tham số, mốc chia dữ liệu, lựa chọn, kết quả và môi trường |

`seasonal_naive` lặp tuần cuối; `random_forest` dùng RF cho mọi sản phẩm;
`selected_forecast` dùng baseline hoặc RF theo lựa chọn riêng từng sản phẩm.
`bias_units = predicted_units - actual_units`; dương là dư, âm là thiếu.
`bias_pct` là phần trăm so với tổng thực tế, để trống khi tổng thực tế bằng 0.
ALL gộp các quan sát sản phẩm–ngày, không phải sai số tổng cửa hàng.
Các cột bias cho biết dư/thiếu tổng lượng bán; RF không được hiệu chỉnh bằng số thực tế test.

### Kết quả lần cải tiến

Cấu hình chọn: đệ quy, 180 ngày gần nhất, max_depth=12,
min_samples_leaf=5.
Danh sách sản phẩm được chốt sớm hơn bản trước, nên RF cũ được tính lại trên cùng panel để so sánh.

| Cách dự báo | MAE test | RMSE test | Dự báo dư hoặc thiếu |
|---|---:|---:|---:|
| RF cũ trên cùng panel | 7,53 | 10,69 | 20,10% |
| Baseline | 8,36 | 12,61 | 13,11% |
| RF sau cải tiến | 7,47 | 11,16 | 19,10% |
| Cách chọn theo sản phẩm | 7,21 | 11,13 | 17,24% |

Validation đã được dùng để chọn mô hình; số của validation không phải đánh giá độc lập.
Test cũ đã được xem trong quá trình chẩn đoán, nên đây là so sánh hồi cứu, không phải test mới chưa từng xem.
Chưa suy ra khả năng tổng quát sang cửa hàng hoặc thời điểm khác; dự báo lượng bán quan sát được,
không xác định được nhu cầu bị mất do hết hàng. Không cam kết RF luôn thắng baseline.
Các phiên bản kết quả trước khi cải tiến được giữ local tại outputs/before_forecast_improvement.

## Mở dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run code\14_dashboard.py
```

Dashboard đọc CSV/JSON nhỏ, không huấn luyện khi đổi bộ lọc. Chọn cửa hàng/nhóm/ngày để xem
thống kê bán hàng; chọn sản phẩm và test/validation để xem dự báo, sai số và tổng dư/thiếu.
Bộ lọc ngày chỉ áp dụng doanh thu và lịch sử; đánh giá luôn dùng đủ 28 ngày.
Dashboard hiển thị store/panel của bộ CSV đang mở. Pipeline mặc định dùng V2:
blend 0,5 RF + 0,5 trung bình 4 tuần cùng thứ, panel recent, công bố seed42.
Thủ tục đã qua cổng trên CA_3, TX_1, WI_1; mọi test trong báo cáo hiện đều đã xem.
Xem [kế hoạch](docs/review/V3_PLAN.md) và [kết quả V3](docs/review/V3_RESULTS.md).
`code/15_forecasting_v3.py --store CA_3 --panel legacy` tái dùng kết quả đã có;
store mới fit RF và ước lượng k từ validation của chính nó, không chọn lại ứng viên.
Các lệnh chạy trực tiếp `code/13_forecasting.py` ở phần trên vẫn là V1.
Chạy lại ghi đè kết quả dự báo cũ, nên không chạy khi đang dùng dashboard để trình bày.
Dashboard cũng giải thích cách chọn mô hình và giới hạn đánh giá.

## Kiểm tra và chạy toàn bộ

```powershell
.\run_pipeline.ps1 -SkipInstall
# Giữ cách chạy V1 nguyên bản:
.\run_pipeline.ps1 -SkipInstall -V1
# Đổi store/panel V2:
.\run_pipeline.ps1 -SkipInstall -Store TX_1 -Panel legacy
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kiểm thử gồm đầu vào/Spark/dashboard, cửa sổ lịch sử, đặc trưng bán 0, cách chọn mô hình,
đối chiếu sai số và kiểm tra thay nhãn test không làm đổi kết quả lựa chọn trên validation.
Nhật ký lần cải tiến: outputs/improvement_tests.log và outputs/improvement_forecast.log.
Đối chiếu CSV thật: outputs/forecast_validation.json.
Các kết quả chỉ hoàn tất khi report tương ứng có status=success.
HDFS và cụm nhiều máy chưa được kiểm chứng trong luồng hiện tại.
