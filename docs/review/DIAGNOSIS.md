# Chẩn đoán bốn giả thuyết dự báo M5

Phân tích hồi cứu trên dữ liệu cục bộ của repo `m5-sales-demand-forecasting`. Chỉ đọc dữ liệu, không sửa `code/`, `tests/`, không tải model để suy luận, không fit/train lại, không chọn cấu hình mới bằng nhãn test. Số liệu thập phân dưới đây dùng dấu chấm; đơn vị bán là đơn vị sản phẩm, không phải số giao dịch.

## Tóm tắt kết luận

1. **Bác bỏ** nhận định tuần origin cao bất thường cho cả nhóm: 2951 so với 2858 đơn vị, chỉ +3.2540%. **Xác nhận** chênh lệch lớn riêng FOODS_3_090 (+42.3333%) và FOODS_3_587 (+53.1429%); FOODS_3_120 ngược lại (-34.1176%). **Chưa đủ dữ liệu** kết luận Phục sinh gây chênh lệch.
2. **Bác bỏ** giả thuyết FOODS_3_090 bán 0 do `sell_price` null: tháng 12/2015 không null ngày nào; fold 1 có 28/28 ngày bán 0 và 28/28 ngày có giá. Trong toàn panel, 92.1298% ngày bán 0 vẫn có giá.
3. **Xác nhận** xu hướng bias tăng theo h trên test (slope dương ở cả hai mô hình), nhưng **bác bỏ** tăng đơn điệu và tăng nhất quán ở hai split: validation cuối có slope âm ở cả hai mô hình.
4. **Xác nhận** RF làm trơn phần lớn đường dự báo (SD thấp hơn thực tế: test 17/20, validation 19/20). **Bác bỏ** mọi sản phẩm đều phẳng dần trong 28 ngày; **chưa đủ dữ liệu** chứng minh hội tụ dài hạn. **Xác nhận** RF không dự báo 0 trên các sản phẩm bán rất ít trong hai cửa sổ quan sát.

## Dữ liệu và cách tái lập

Đã đọc `docs/REVIEW_REQUEST.md`, toàn bộ `code/13_forecasting.py`, `tests/test_forecasting.py` và các CSV/JSON trong `docs/review/`. Đã kiểm tra trực tiếp:

- `outputs/forecast/history.csv`: 38260 dòng = 20 sản phẩm CA_1 × 1913 ngày, 29/01/2011–24/04/2016.
- `outputs/forecast/predictions.csv`: 3360 dòng; 2 split × 3 mô hình × 20 sản phẩm × 28 horizon. Chẩn đoán dùng `seasonal_naive` và `random_forest`, không trộn với `selected_forecast` hay RF cũ trong `reference_test`.
- `GuiDat/data/processed_m5/*.parquet`: 32 file; pyarrow lọc CA_1 và đúng 20 sản phẩm, đọc 38260 dòng. Demand khớp toàn bộ history theo item/date, không trùng khóa.
- Validation cuối: origin 28/02/2016, dự báo 29/02–27/03/2016. Test: origin 27/03/2016, dự báo 28/03–24/04/2016. Validation này đã được dùng chọn mô hình, không phải holdout độc lập.
- Cấu hình RF ghi trong artifact: window_days=180, max_depth=12, min_samples_leaf=5; không có strategy=direct. Đây là mô hình đệ quy được chọn sẵn, không phải đề xuất cấu hình.

Script [diagnose_forecasts.py](../../scripts/diagnose_forecasts.py) chỉ mở file đọc và in JSON ra stdout; không import module forecasting, không ghi dataset/artifact, không gọi fit/predict. Dùng đúng numpy và pyarrow đã có trong requirements. Lệnh đã chạy từ thư mục repo:

```powershell
.\.venv\Scripts\python.exe scripts\diagnose_forecasts.py > .runtime/diagnosis_measurements.json
```

Thư mục `.runtime/` đã tồn tại cục bộ. Có thể bỏ phần `> ...` để xem JSON trực tiếp; JSON chứa số đầy đủ chưa làm tròn, cả dữ liệu giá từng ngày của tháng 12 và fold 1. Các bảng trong báo cáo này lấy từ JSON đó.

Script có self-check công thức và assert: panel đủ/trùng khóa, actual khớp history/Parquet, h đúng khoảng cách origin→date, mỗi h đủ 20 sản phẩm, tổng bias khớp forecast_report, giá không null phải hữu hạn. Các bản `forecast_report.json`, `metrics.csv` (126 dòng), `model_selection.csv` (20), `rolling_metrics.csv` (640), `selected_series.csv` (20) trong review giống byte với outputs. Hai sparse extract (history 278 dòng, predictions 336 dòng) khớp dữ liệu đầy đủ. Hai validation JSON cũ ghi success; không xem chúng là kết quả chạy lại test hôm nay.

SHA-256 của các đầu vào CSV/report đã dùng:

- `outputs/forecast/history.csv`: `5f288fa6bf79cd878e4e2e71c74796984177871f16630ed6a6ebf189825d9d04`
- `outputs/forecast/predictions.csv`: `0061676b7286b0b95c32a24164bbb859ff795513d849c8162b856780cccb2d42`
- `outputs/forecast/selected_series.csv`: `232acaeaf4f1e87dcd17742a80521bc42346f070f2aaffbb91b9cb640eff658d`
- `outputs/forecast/forecast_report.json`: `f62ab198cc4a21dc464ea03cfe686b0b2e379a6ed84a7c45ed5c06e3a7fc2342`

Ở máy này không thiếu đầu vào. Trên clone GitHub, `.gitignore` loại `outputs/` và `GuiDat/data/`: nếu thiếu, cần cụ thể `outputs/forecast/history.csv`, `predictions.csv`, `selected_series.csv`, `forecast_report.json` và nguồn Parquet. Các sparse extract không thay thế panel 20 sản phẩm. Khôi phục nguồn theo [DATA_SOURCE.md](../../DATA_SOURCE.md), tạo môi trường theo README, rồi có thể tái tạo outputs bằng:

```powershell
./run_pipeline.ps1 -SkipInstall
```

Lệnh pipeline **có train lại và ghi đè outputs**, nên chỉ là hướng dẫn khôi phục cho lần chạy được cho phép riêng; không được thực thi trong chẩn đoán này. Nếu phụ thuộc chưa cài, xem README và requirements trước, hoặc dùng pipeline không có `-SkipInstall` trong lần tái tạo được cho phép.

## 1. Tuần origin có cao bất thường không?

Cộng `units` trực tiếp từ history, đủ 7 ngày × số sản phẩm; tuần Thứ hai–Chủ nhật. Chênh lệch % = 100 × (tuần origin / tuần sau − 1), mẫu số là tuần sau.

| Nhóm | 21–27/03/2016 | 28/03–03/04/2016 | Chênh lệch đơn vị | Chênh lệch % |
| --- | --- | --- | --- | --- |
| ALL | 2951.0000 | 2858.0000 | 93.0000 | 3.2540 |
| FOODS_3_120 | 280.0000 | 425.0000 | -145.0000 | -34.1176 |
| FOODS_3_090 | 427.0000 | 300.0000 | 127.0000 | 42.3333 |
| FOODS_3_587 | 268.0000 | 175.0000 | 93.0000 | 53.1429 |

Bằng chứng bối cảnh lịch sử: so với 268 tuần đầy đủ Thứ hai–Chủ nhật trước 21/03/2016 (31/01/2011–20/03/2016):

| Nhóm | Trung vị tuần cũ | P95 tuần cũ | % tuần cũ ≤ tuần origin |
| --- | --- | --- | --- |
| ALL | 3401.0000 | 5104.2500 | 28.7313 |
| FOODS_3_120 | 223.5000 | 531.6500 | 55.5970 |
| FOODS_3_090 | 484.5000 | 996.4500 | 36.5672 |
| FOODS_3_587 | 204.0000 | 404.4500 | 77.9851 |

**Kết luận:** bác bỏ mức tăng lớn trên toàn nhóm; xác nhận tăng lớn tương đối với tuần kế tiếp ở 090 và 587, bác bỏ ở 120. Cả bốn tổng tuần origin đều dưới P95 lịch sử. “Bất thường” không có ngưỡng kiểm định định trước; các phân vị chỉ là mô tả và lịch sử dài có thể không dừng, không chứng minh có/không có hiệu ứng lễ.

Parquet ghi `event_name_1/2` có `Easter` tại 27/03/2016. **Chưa đủ dữ liệu** quy nguyên nhân cho lễ: so sánh hai tuần không kiểm soát tồn kho, khuyến mãi, xu hướng hay thay đổi bán hàng. Seasonal naive lặp chính tuần origin bốn lần (`recursive_predict`, [code dòng 108](../../code/13_forecasting.py#L108)); tổng dự báo test 11804 = 4 × 2951, trong khi thực tế 10436. Đây là cơ chế lặp quan sát được, không chứng minh toàn bộ bias do Phục sinh.

## 2. Ngày bán 0 có thiếu giá không?

Đọc cột gốc `sell_price` bằng pyarrow, xét null thật (`None`), không điền giá/không đổi null thành 0. Assert xác nhận giá không null đều hữu hạn trong panel.

| FOODS_3_090 tại CA_1 | Ngày | Tổng bán | Ngày bán 0 | Giá null | Giá hiện diện |
| --- | --- | --- | --- | --- | --- |
| 01–31/12/2015 | 31 | 84 | 28 | 0 | 31 |
| Fold 1: 07/12/2015–03/01/2016 | 28 | 0 | 28 | 0 | 28 |

Tháng 12 giá đều 1.50. Ba ngày 01, 02, 03/12 bán lần lượt 36, 47, 1 đơn vị; 04–31/12 bán 0, tổng tháng 84. Fold 1 không đồng nhất với tháng 12: nó kéo dài đến 03/01; có giá 1.50 hoặc 1.60, tất cả 28 ngày bán 0. `rolling_metrics.csv` cũng ghi actual_units=0 cho 090 ở fold 1.

Thống kê toàn lịch sử 20 sản phẩm (38260 item-ngày, 4714 ngày demand=0):

- 371 ngày demand=0 và giá null: **7.8702% trong các ngày bán 0**, hoặc **0.9697% toàn bộ item-ngày**.
- 4343 ngày demand=0 và có giá: **92.1298% trong các ngày bán 0**, hoặc **11.3513% toàn bộ item-ngày**.
- Tổng giá null là 371; trong panel này tất cả các ngày giá null đều có demand=0. Chiều ngược lại không đúng.

Chi tiết theo sản phẩm; mẫu số hai cột % là tổng ngày bán 0 của từng sản phẩm (mỗi sản phẩm có 1913 ngày):

| Sản phẩm | Ngày bán 0 | 0 & giá null | 0 & có giá | % null trong ngày bán 0 | % có giá trong ngày bán 0 |
| --- | --- | --- | --- | --- | --- |
| FOODS_2_019 | 162 | 0 | 162 | 0.0000 | 100.0000 |
| FOODS_2_197 | 159 | 0 | 159 | 0.0000 | 100.0000 |
| FOODS_3_080 | 6 | 0 | 6 | 0.0000 | 100.0000 |
| FOODS_3_090 | 469 | 0 | 469 | 0.0000 | 100.0000 |
| FOODS_3_099 | 91 | 7 | 84 | 7.6923 | 92.3077 |
| FOODS_3_120 | 667 | 364 | 303 | 54.5727 | 45.4273 |
| FOODS_3_202 | 211 | 0 | 211 | 0.0000 | 100.0000 |
| FOODS_3_252 | 6 | 0 | 6 | 0.0000 | 100.0000 |
| FOODS_3_318 | 579 | 0 | 579 | 0.0000 | 100.0000 |
| FOODS_3_319 | 354 | 0 | 354 | 0.0000 | 100.0000 |
| FOODS_3_541 | 389 | 0 | 389 | 0.0000 | 100.0000 |
| FOODS_3_555 | 6 | 0 | 6 | 0.0000 | 100.0000 |
| FOODS_3_586 | 7 | 0 | 7 | 0.0000 | 100.0000 |
| FOODS_3_587 | 455 | 0 | 455 | 0.0000 | 100.0000 |
| FOODS_3_635 | 450 | 0 | 450 | 0.0000 | 100.0000 |
| FOODS_3_681 | 179 | 0 | 179 | 0.0000 | 100.0000 |
| FOODS_3_694 | 8 | 0 | 8 | 0.0000 | 100.0000 |
| FOODS_3_714 | 7 | 0 | 7 | 0.0000 | 100.0000 |
| FOODS_3_741 | 124 | 0 | 124 | 0.0000 | 100.0000 |
| FOODS_3_808 | 385 | 0 | 385 | 0.0000 | 100.0000 |

**Kết luận: bác bỏ** thiếu giá ở FOODS_3_090 tháng 12/fold 1; bác bỏ quy tắc “ngày bán 0 đồng nghĩa giá null” trên 20 sản phẩm. **Chưa đủ dữ liệu** phân biệt hết hàng với không có nhu cầu: có giá không bảo đảm có hàng, null cũng không tự chứng minh hết hàng. Dữ liệu ở đây là lượng bán quan sát, không phải nhu cầu tiềm ẩn.

## 3. Bias theo h=1..28 có tăng dần không?

Bias = prediction − actual. Bảng dưới là **mean bias trên 20 sản phẩm tại từng h**, đơn vị sản phẩm/ngày/sản phẩm; tổng bias tại h bằng số trong bảng × 20 (dùng giá trị chưa làm tròn). Không phải bias lũy kế. h được tính từ một origin cố định của mỗi split, không rolling cập nhật actual.

| h | Validation seasonal_naive | Validation RF | Test seasonal_naive | Test RF |
| --- | --- | --- | --- | --- |
| 1 | 5.0500 | 4.2188 | -1.3000 | 3.7916 |
| 2 | 3.8000 | 3.0168 | -5.8000 | -0.3479 |
| 3 | -0.3500 | 1.9795 | 2.9000 | 6.0522 |
| 4 | 1.3500 | 1.5642 | 3.6500 | 4.2111 |
| 5 | 0.8000 | 2.5691 | 2.2500 | -0.8372 |
| 6 | 2.7000 | 3.8296 | 2.1000 | -3.8172 |
| 7 | -1.1000 | 0.6618 | 0.8500 | 1.6731 |
| 8 | 1.8000 | 0.1993 | -4.1000 | 0.2899 |
| 9 | 3.8000 | 3.3270 | -0.9500 | 4.2098 |
| 10 | 1.6000 | 3.4754 | 0.5000 | 3.0066 |
| 11 | 2.5500 | 3.7584 | 5.6500 | 5.8912 |
| 12 | 0.6500 | 3.2002 | 3.5500 | 0.2660 |
| 13 | 2.9500 | 4.6217 | 6.0000 | 0.7473 |
| 14 | 4.6500 | 6.8151 | 9.2000 | 10.1529 |
| 15 | 3.4500 | 3.8576 | 1.0500 | 5.9528 |
| 16 | 3.8000 | 3.7768 | 0.8500 | 6.3768 |
| 17 | -1.0500 | 1.4327 | 2.0500 | 5.1922 |
| 18 | 0.6000 | 1.5002 | 3.6500 | 4.0096 |
| 19 | -0.4000 | 2.4269 | 6.2000 | 2.8724 |
| 20 | -3.7500 | -1.9290 | 8.4000 | 3.9672 |
| 21 | -8.0500 | -5.1881 | 1.8000 | 4.1868 |
| 22 | 3.3000 | 3.4356 | 1.8000 | 7.0066 |
| 23 | 3.8000 | 3.6424 | -3.2500 | 2.2948 |
| 24 | -1.5000 | 0.6599 | 0.1500 | 3.2321 |
| 25 | -2.6000 | -1.5200 | 1.8000 | 2.7435 |
| 26 | -7.4000 | -5.0096 | 5.2500 | 2.8021 |
| 27 | -10.7000 | -8.5198 | 8.6500 | 5.4132 |
| 28 | -6.6000 | -3.4688 | 5.5000 | 8.3128 |

Tóm tắt xu hướng tuyến tính OLS của mean bias theo h (có intercept); Pearson r mô tả đồng biến, không phải kiểm định nhân quả hay kiểm định ý nghĩa thống kê:

| Split / model | Bias tổng 560 điểm | Slope / h | Pearson r | Bước tăng/27 | Bước giảm/27 |
| --- | --- | --- | --- | --- | --- |
| validation / seasonal_naive | 63.0000 | -0.3095 | -0.6155 | 12 | 15 |
| validation / random_forest | 766.6692 | -0.2427 | -0.5751 | 12 | 15 |
| test / seasonal_naive | 1368.0000 | 0.1722 | 0.3855 | 15 | 11 |
| test / random_forest | 1993.0477 | 0.1348 | 0.3745 | 14 | 13 |

Mean bias theo bốn khối 7 ngày liên tiếp:

| Split / model | h1–7 | h8–14 | h15–21 | h22–28 |
| --- | --- | --- | --- | --- |
| validation / seasonal_naive | 1.7500 | 2.5714 | -0.7714 | -3.1000 |
| validation / random_forest | 2.5485 | 3.6281 | 0.8396 | -1.5401 |
| test / seasonal_naive | 0.6643 | 2.8357 | 3.4286 | 2.8429 |
| test / random_forest | 1.5322 | 3.5091 | 4.6511 | 4.5436 |

**Kết luận:** xác nhận xu hướng tăng trung bình trên test, nhưng bác bỏ tăng đơn điệu (RF có 13 bước giảm; seasonal naive 11 bước giảm và 1 bước bằng nhau). Validation cuối có xu hướng giảm, không tái hiện xu hướng test. Vì cả seasonal naive cũng có slope dương trên test, chưa đủ bằng chứng quy slope dương riêng cho tích lũy lỗi RF đệ quy. Bias phụ thuộc đồng thời dự báo và actual ở từng ngày; ngày trong tuần, biến động actual và thay đổi mức bán đều có thể ảnh hưởng. Hai origin không đủ suy ra quy luật chung cho mọi giai đoạn.

## 4. RF đệ quy phẳng dần và bỏ qua mức bán gần 0?

SD là độ lệch chuẩn tổng thể trong mỗi cửa sổ 28 ngày (`ddof=0`). Tỷ số = SD prediction / SD actual; không xác định nếu actual hằng 0. SD thấp hơn actual chỉ chứng minh làm trơn, không tự chứng minh hội tụ theo h. Vì vậy kiểm tra thêm SD dự báo h1–7 và h22–28 để phân biệt độ biến động thấp với biến động giảm dần.

### SD trên toàn bộ 20 sản phẩm

| Sản phẩm | Val SD actual | Val SD RF | Val tỷ số | Test SD actual | Test SD RF | Test tỷ số |
| --- | --- | --- | --- | --- | --- | --- |
| FOODS_2_019 | 6.6627 | 3.5654 | 0.5351 | 6.7577 | 3.4055 | 0.5039 |
| FOODS_2_197 | 5.7413 | 3.9486 | 0.6878 | 9.1748 | 3.3483 | 0.3649 |
| FOODS_3_080 | 9.5823 | 3.5982 | 0.3755 | 6.4834 | 4.4573 | 0.6875 |
| FOODS_3_090 | 21.8084 | 15.9141 | 0.7297 | 21.3626 | 12.6171 | 0.5906 |
| FOODS_3_099 | 7.4213 | 3.6712 | 0.4947 | 6.2987 | 3.7155 | 0.5899 |
| FOODS_3_120 | 32.9776 | 5.2928 | 0.1605 | 31.4775 | 12.1735 | 0.3867 |
| FOODS_3_202 | 4.7834 | 3.3021 | 0.6903 | 6.4127 | 4.0634 | 0.6337 |
| FOODS_3_252 | 15.4132 | 8.2743 | 0.5368 | 12.6561 | 10.5147 | 0.8308 |
| FOODS_3_318 | 6.5304 | 2.9563 | 0.4527 | 6.3551 | 4.3621 | 0.6864 |
| FOODS_3_319 | 4.5541 | 2.7490 | 0.6036 | 3.4766 | 2.8075 | 0.8075 |
| FOODS_3_541 | 2.3677 | 0.8595 | 0.3630 | 0.1856 | 0.8573 | 4.6196 |
| FOODS_3_555 | 6.2010 | 3.9522 | 0.6373 | 6.4349 | 4.5422 | 0.7059 |
| FOODS_3_586 | 10.4359 | 7.4630 | 0.7151 | 11.7210 | 9.7180 | 0.8291 |
| FOODS_3_587 | 13.0452 | 2.0468 | 0.1569 | 7.7666 | 9.3431 | 1.2030 |
| FOODS_3_635 | 0.0000 | 0.9107 | không xác định | 1.4228 | 1.5025 | 1.0560 |
| FOODS_3_681 | 7.3411 | 1.9860 | 0.2705 | 7.5448 | 4.2064 | 0.5575 |
| FOODS_3_694 | 4.0838 | 2.6010 | 0.6369 | 4.6368 | 3.7787 | 0.8149 |
| FOODS_3_714 | 8.9400 | 3.8734 | 0.4333 | 9.8620 | 5.1111 | 0.5183 |
| FOODS_3_741 | 8.9764 | 2.2316 | 0.2486 | 6.6032 | 4.0915 | 0.6196 |
| FOODS_3_808 | 2.8237 | 0.8996 | 0.3186 | 3.8576 | 0.7204 | 0.1867 |

### SD dự báo đầu và cuối cửa sổ: validation

| Sản phẩm | SD h1–7 | SD h22–28 |
| --- | --- | --- |
| FOODS_2_019 | 3.1088 | 3.7405 |
| FOODS_2_197 | 3.9599 | 4.2965 |
| FOODS_3_080 | 3.7203 | 3.6500 |
| FOODS_3_090 | 15.5811 | 15.9897 |
| FOODS_3_099 | 3.5077 | 3.9622 |
| FOODS_3_120 | 4.7745 | 3.8834 |
| FOODS_3_202 | 3.7314 | 3.0927 |
| FOODS_3_252 | 7.3918 | 9.3344 |
| FOODS_3_318 | 1.8123 | 2.9647 |
| FOODS_3_319 | 2.6962 | 3.0607 |
| FOODS_3_541 | 1.0095 | 0.4990 |
| FOODS_3_555 | 4.2102 | 3.9221 |
| FOODS_3_586 | 7.7208 | 7.5396 |
| FOODS_3_587 | 3.0962 | 0.8763 |
| FOODS_3_635 | 1.0081 | 0.6700 |
| FOODS_3_681 | 2.3180 | 2.1706 |
| FOODS_3_694 | 2.8292 | 2.0809 |
| FOODS_3_714 | 4.0807 | 3.7871 |
| FOODS_3_741 | 2.1387 | 2.5038 |
| FOODS_3_808 | 0.8876 | 0.8956 |

### SD dự báo đầu và cuối cửa sổ: test

| Sản phẩm | SD h1–7 | SD h22–28 |
| --- | --- | --- |
| FOODS_2_019 | 2.9094 | 3.6376 |
| FOODS_2_197 | 2.2529 | 3.7033 |
| FOODS_3_080 | 3.8613 | 4.2016 |
| FOODS_3_090 | 13.8165 | 12.1995 |
| FOODS_3_099 | 2.8172 | 4.6516 |
| FOODS_3_120 | 11.0071 | 13.2017 |
| FOODS_3_202 | 3.7267 | 4.1992 |
| FOODS_3_252 | 10.1213 | 11.4632 |
| FOODS_3_318 | 4.2584 | 4.8070 |
| FOODS_3_319 | 1.5303 | 3.6506 |
| FOODS_3_541 | 0.9018 | 0.6969 |
| FOODS_3_555 | 4.3380 | 4.3350 |
| FOODS_3_586 | 10.4820 | 10.5909 |
| FOODS_3_587 | 7.3152 | 9.9981 |
| FOODS_3_635 | 1.8984 | 0.5124 |
| FOODS_3_681 | 3.3302 | 4.5817 |
| FOODS_3_694 | 2.7166 | 3.9029 |
| FOODS_3_714 | 5.4573 | 4.4731 |
| FOODS_3_741 | 2.9964 | 4.2131 |
| FOODS_3_808 | 0.8244 | 0.3422 |

**Kết luận về phẳng/hội tụ:** xác nhận làm trơn phần lớn sản phẩm: test 17/20 có SD dự báo thấp hơn actual, trung vị tỷ số 0.6600; validation 19/20 thấp hơn actual, trung vị tỷ số trên 19 sản phẩm actual có SD>0 là 0.4947. Không sản phẩm nào có SD RF bằng 0 ở hai split. SD tuần cuối thấp hơn tuần đầu chỉ ở 6/20 sản phẩm test và 11/20 validation, nên bác bỏ nhận định cả panel đều phẳng dần theo h. Ví dụ FOODS_3_587 test có SD RF=9.3431 > SD actual=7.7666, SD tuần cuối tăng từ 7.3152 lên 9.9981; validation của cùng sản phẩm lại giảm từ 3.0962 xuống 0.8763. Chưa đủ dữ liệu chứng minh hội tụ dài hạn vì chỉ có 28 bước.

### Dự báo dương khi thực tế gần 0

Trên cả 20 sản phẩm, RF có **0/560 dự báo bằng 0 ở mỗi split** (1120/1120 giá trị dương qua hai split). “Không bao giờ” ở đây chỉ trong các cửa sổ được kiểm tra. Bảng sau liệt kê toàn bộ sản phẩm có ít nhất 20/28 ngày actual bằng 0; đây là tiêu chí mô tả mức bán thưa, không phải ngưỡng chọn mô hình hoặc hiệu chỉnh dự báo.

| Split | Sản phẩm | Ngày actual=0 | Tổng actual | Tổng RF | Min RF | Max RF | Ngày RF=0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| validation | FOODS_3_541 | 20 | 29.0000 | 86.9352 | 1.8486 | 5.3476 | 0 |
| validation | FOODS_3_635 | 28 | 0.0000 | 83.3116 | 1.3724 | 4.7090 | 0 |
| test | FOODS_3_319 | 24 | 38.0000 | 421.0256 | 11.8452 | 23.2668 | 0 |
| test | FOODS_3_541 | 27 | 1.0000 | 71.2838 | 1.1138 | 4.6059 | 0 |
| test | FOODS_3_635 | 26 | 11.0000 | 79.8911 | 1.0557 | 7.9795 | 0 |
| test | FOODS_3_808 | 23 | 39.0000 | 66.3020 | 0.8323 | 3.5027 | 0 |

**Kết luận: xác nhận** RF vẫn dự báo dương ngay cả khi actual gần 0, rõ nhất FOODS_3_541 test: 27/28 ngày bằng 0, tổng actual 1 nhưng tổng RF 71.2838. FOODS_3_635 validation actual=0 cả 28 ngày, RF vẫn tổng 83.3116; tỷ số SD ở đây không xác định, không gán bằng 0 hoặc vô hạn.

Bằng chứng code: [features, dòng 84](../../code/13_forecasting.py#L84) tính `zero_fraction` bằng so sánh `==0`, còn streak dựa vào `>0`. [recursive_predict, dòng 108–120](../../code/13_forecasting.py#L108) kẹp dự báo ở mức ≥0 rồi thêm số thực dự báo vào history. Khi dự báo đều dương như artifact này, các số dương dần thay thế quan sát trong cửa sổ lag/mean/zero; đến sau h28, 28 phần tử vừa thêm đều dương. Đây là cơ chế có thật và phù hợp với việc đặc trưng zero thay đổi khi chạy đệ quy. **Suy đoán chưa được chứng minh:** cơ chế đó gây ra bao nhiêu bias hoặc làm phẳng ở từng sản phẩm; CSV đầu ra không chứa trạng thái đặc trưng/cây, và chẩn đoán không chạy thí nghiệm đối chứng hay train lại.

## Giới hạn và kiểm tra đã thực hiện

- Tất cả bốn giả thuyết có dữ liệu trực tiếp; các assert của script hoàn tất thành công. Đã đối chiếu báo cáo review với outputs và actual với nguồn Parquet, không suy số liệu từ biểu đồ.
- Chỉ mô tả hiện tượng hồi cứu. Test lịch sử đã được xem trước; không dùng nhãn test để chọn cửa sổ, tham số, ngưỡng cắt, mô hình hay cấu hình mới. Không đưa khuyến nghị cấu hình từ kết quả này.
- Đã đọc các kiểm thử về split/features, recursion, selection không dùng test, Spark/export. Không chạy bộ unittest vì một số test thực hiện fit/train, trái phạm vi lần này; số “15 tests passed” trong review request là bằng chứng lịch sử, không phải xác nhận chạy mới.
- Không có nhãn tồn kho, ngày ngừng bán hay nhu cầu tiềm ẩn; không kết luận nguyên nhân của bán 0. Không kiểm định nhân quả Phục sinh hoặc chứng minh hội tụ ngoài 28 ngày. Kết luận không tự mở rộng sang cửa hàng/sản phẩm khác.


## Bổ sung 2

Phạm vi giữ nguyên: phân tích CSV đã có, không sửa `code/`, `tests/`, không train/suy luận lại, không dùng nhãn test đề xuất cấu hình. Mọi bias dưới đây là tổng có dấu, prediction − actual, không phải MAE hoặc tổng trị tuyệt đối sai số. Các tỷ lệ đóng góp có mẫu số ghi rõ; số âm là bù trừ, không phải đóng góp lỗi tuyệt đối.

### 2.1. Phân rã bias RF theo sản phẩm và nhóm

Đặt B_SN = Σ(seasonal_naive − actual), B_RF = Σ(RF − actual), Δ = B_RF − B_SN = Σ(RF − seasonal_naive). Khi đó **B_RF = B_SN + Δ**. Đây là đồng nhất thức số học trên cùng 28 ngày, không phải phân rã nguyên nhân. Δ không thể được gọi là phần lỗi chỉ do đệ quy, vì hai mô hình còn khác mức dự báo và cách học.

Nhóm 5 sản phẩm thưa được cố định đúng theo yêu cầu: FOODS_3_541, FOODS_3_635, FOODS_3_319, FOODS_3_808, FOODS_3_318. Tên nhóm không hàm ý cả năm đều thưa ở mọi cửa sổ; 15 sản phẩm còn lại là phần bù của panel.

#### validation: 29/02–27/03/2016, origin 2016-02-28

| Sản phẩm | Nhóm | Tổng actual | B_SN | Δ = B_RF − B_SN | B_RF |
| --- | --- | --- | --- | --- | --- |
| FOODS_2_019 | 15 còn lại | 433.0000 | 79.0000 | -23.1387 | 55.8613 |
| FOODS_2_197 | 15 còn lại | 435.0000 | 33.0000 | 10.3619 | 43.3619 |
| FOODS_3_080 | 15 còn lại | 531.0000 | -39.0000 | 8.0819 | -30.9181 |
| FOODS_3_090 | 15 còn lại | 1513.0000 | -77.0000 | 33.9367 | -43.0633 |
| FOODS_3_099 | 15 còn lại | 415.0000 | 101.0000 | -19.4716 | 81.5284 |
| FOODS_3_120 | 15 còn lại | 689.0000 | 187.0000 | 67.1815 | 254.1815 |
| FOODS_3_202 | 15 còn lại | 409.0000 | -1.0000 | 48.6996 | 47.6996 |
| FOODS_3_252 | 15 còn lại | 926.0000 | 10.0000 | 82.2723 | 92.2723 |
| FOODS_3_318 | 5 thưa | 345.0000 | 43.0000 | 31.8900 | 74.8900 |
| FOODS_3_319 | 5 thưa | 230.0000 | 150.0000 | 26.8963 | 176.8963 |
| FOODS_3_541 | 5 thưa | 29.0000 | 43.0000 | 14.9352 | 57.9352 |
| FOODS_3_555 | 15 còn lại | 487.0000 | -47.0000 | 45.8668 | -1.1332 |
| FOODS_3_586 | 15 còn lại | 1040.0000 | -20.0000 | 3.7006 | -16.2994 |
| FOODS_3_587 | 15 còn lại | 883.0000 | -235.0000 | 93.0869 | -141.9131 |
| FOODS_3_635 | 5 thưa | 0.0000 | 8.0000 | 75.3116 | 83.3116 |
| FOODS_3_681 | 15 còn lại | 351.0000 | -59.0000 | 86.4480 | 27.4480 |
| FOODS_3_694 | 15 còn lại | 309.0000 | -49.0000 | 58.0101 | 9.0101 |
| FOODS_3_714 | 15 còn lại | 534.0000 | -126.0000 | 55.5954 | -70.4046 |
| FOODS_3_741 | 15 còn lại | 397.0000 | 11.0000 | 6.0947 | 17.0947 |
| FOODS_3_808 | 5 thưa | 49.0000 | 51.0000 | -2.0899 | 48.9101 |

| Nhóm | Tổng actual | B_SN | Δ | B_RF |
| --- | --- | --- | --- | --- |
| 5 thưa | 653.0000 | 295.0000 | 146.9432 | 441.9432 |
| 15 còn lại | 9352.0000 | -232.0000 | 556.7261 | 324.7261 |
| ALL | 10005.0000 | 63.0000 | 703.6692 | 766.6692 |

| Nhóm | % B_SN toàn panel | % Δ toàn panel | % B_RF toàn panel |
| --- | --- | --- | --- |
| 5 thưa | 468.2540 | 20.8824 | 57.6446 |
| 15 còn lại | -368.2540 | 79.1176 | 42.3554 |

**Bằng chứng:** toàn panel 766.6692 = 63.0000 + 703.6692. Trong bias RF tổng, thành phần B_SN chiếm 8.2174% và Δ chiếm 91.7826%. Tỷ trọng theo nhóm ở bảng trên dùng tổng của từng cột làm mẫu số; có thể vượt 100% khi nhóm kia có bias âm.

#### test: 28/03–24/04/2016, origin 2016-03-27

| Sản phẩm | Nhóm | Tổng actual | B_SN | Δ = B_RF − B_SN | B_RF |
| --- | --- | --- | --- | --- | --- |
| FOODS_2_019 | 15 còn lại | 459.0000 | -103.0000 | 105.4680 | 2.4680 |
| FOODS_2_197 | 15 còn lại | 559.0000 | -239.0000 | 144.0272 | -94.9728 |
| FOODS_3_080 | 15 còn lại | 519.0000 | 117.0000 | -67.6687 | 49.3313 |
| FOODS_3_090 | 15 còn lại | 1423.0000 | 285.0000 | -57.0259 | 227.9741 |
| FOODS_3_099 | 15 còn lại | 404.0000 | 8.0000 | 91.5966 | 99.5966 |
| FOODS_3_120 | 15 còn lại | 1071.0000 | 49.0000 | 183.1472 | 232.1472 |
| FOODS_3_202 | 15 còn lại | 452.0000 | 16.0000 | 5.1710 | 21.1710 |
| FOODS_3_252 | 15 còn lại | 1051.0000 | -19.0000 | 65.0051 | 46.0051 |
| FOODS_3_318 | 5 thưa | 324.0000 | 172.0000 | -16.9244 | 155.0756 |
| FOODS_3_319 | 5 thưa | 38.0000 | 306.0000 | 77.0256 | 383.0256 |
| FOODS_3_541 | 5 thưa | 1.0000 | 23.0000 | 47.2838 | 70.2838 |
| FOODS_3_555 | 15 còn lại | 536.0000 | 12.0000 | -40.3186 | -28.3186 |
| FOODS_3_586 | 15 còn lại | 1075.0000 | 89.0000 | -18.2919 | 70.7081 |
| FOODS_3_587 | 15 còn lại | 643.0000 | 429.0000 | 39.9483 | 468.9483 |
| FOODS_3_635 | 5 thưa | 11.0000 | -11.0000 | 79.8911 | 68.8911 |
| FOODS_3_681 | 15 còn lại | 534.0000 | -22.0000 | -35.9979 | -57.9979 |
| FOODS_3_694 | 15 còn lại | 308.0000 | 8.0000 | 135.9531 | 143.9531 |
| FOODS_3_714 | 15 còn lại | 525.0000 | 115.0000 | 0.3239 | 115.3239 |
| FOODS_3_741 | 15 còn lại | 464.0000 | 112.0000 | -119.8680 | -7.8680 |
| FOODS_3_808 | 5 thưa | 39.0000 | 21.0000 | 6.3020 | 27.3020 |

| Nhóm | Tổng actual | B_SN | Δ | B_RF |
| --- | --- | --- | --- | --- |
| 5 thưa | 413.0000 | 511.0000 | 193.5782 | 704.5782 |
| 15 còn lại | 10023.0000 | 857.0000 | 431.4695 | 1288.4695 |
| ALL | 10436.0000 | 1368.0000 | 625.0477 | 1993.0477 |

| Nhóm | % B_SN toàn panel | % Δ toàn panel | % B_RF toàn panel |
| --- | --- | --- | --- |
| 5 thưa | 37.3538 | 30.9702 | 35.3518 |
| 15 còn lại | 62.6462 | 69.0298 | 64.6482 |

**Bằng chứng:** toàn panel 1993.0477 = 1368.0000 + 625.0477. Trong bias RF tổng, thành phần B_SN chiếm 68.6386% và Δ chiếm 31.3614%. Tỷ trọng theo nhóm ở bảng trên dùng tổng của từng cột làm mẫu số; có thể vượt 100% khi nhóm kia có bias âm.

### 2.2. Tổng tuần trước origin test và bốn tuần test

Origin ở mục này là **27/03/2016**. 52 tuần trước origin được định nghĩa là 52 tuần đầy đủ Thứ hai–Chủ nhật kết thúc đúng ngày origin (30/03/2015–27/03/2016); tuần cuối chứa ngày origin, đều đã quan sát khi lập dự báo. Bốn tuần test là 28/03–24/04/2016. Đánh số t=−51..0 cho 52 tuần lịch sử, t=1..4 cho test.

| t | Cửa sổ | Từ ngày | Đến ngày | Tổng 20 sản phẩm |
| --- | --- | --- | --- | --- |
| -51 | trước/đến origin | 2015-03-30 | 2015-04-05 | 3105.0000 |
| -50 | trước/đến origin | 2015-04-06 | 2015-04-12 | 2794.0000 |
| -49 | trước/đến origin | 2015-04-13 | 2015-04-19 | 2727.0000 |
| -48 | trước/đến origin | 2015-04-20 | 2015-04-26 | 2937.0000 |
| -47 | trước/đến origin | 2015-04-27 | 2015-05-03 | 3174.0000 |
| -46 | trước/đến origin | 2015-05-04 | 2015-05-10 | 3356.0000 |
| -45 | trước/đến origin | 2015-05-11 | 2015-05-17 | 2700.0000 |
| -44 | trước/đến origin | 2015-05-18 | 2015-05-24 | 2413.0000 |
| -43 | trước/đến origin | 2015-05-25 | 2015-05-31 | 2564.0000 |
| -42 | trước/đến origin | 2015-06-01 | 2015-06-07 | 2773.0000 |
| -41 | trước/đến origin | 2015-06-08 | 2015-06-14 | 2940.0000 |
| -40 | trước/đến origin | 2015-06-15 | 2015-06-21 | 3365.0000 |
| -39 | trước/đến origin | 2015-06-22 | 2015-06-28 | 3700.0000 |
| -38 | trước/đến origin | 2015-06-29 | 2015-07-05 | 3450.0000 |
| -37 | trước/đến origin | 2015-07-06 | 2015-07-12 | 3351.0000 |
| -36 | trước/đến origin | 2015-07-13 | 2015-07-19 | 3048.0000 |
| -35 | trước/đến origin | 2015-07-20 | 2015-07-26 | 3165.0000 |
| -34 | trước/đến origin | 2015-07-27 | 2015-08-02 | 3478.0000 |
| -33 | trước/đến origin | 2015-08-03 | 2015-08-09 | 3577.0000 |
| -32 | trước/đến origin | 2015-08-10 | 2015-08-16 | 3375.0000 |
| -31 | trước/đến origin | 2015-08-17 | 2015-08-23 | 3306.0000 |
| -30 | trước/đến origin | 2015-08-24 | 2015-08-30 | 3056.0000 |
| -29 | trước/đến origin | 2015-08-31 | 2015-09-06 | 3026.0000 |
| -28 | trước/đến origin | 2015-09-07 | 2015-09-13 | 3583.0000 |
| -27 | trước/đến origin | 2015-09-14 | 2015-09-20 | 3439.0000 |
| -26 | trước/đến origin | 2015-09-21 | 2015-09-27 | 3410.0000 |
| -25 | trước/đến origin | 2015-09-28 | 2015-10-04 | 3148.0000 |
| -24 | trước/đến origin | 2015-10-05 | 2015-10-11 | 3030.0000 |
| -23 | trước/đến origin | 2015-10-12 | 2015-10-18 | 2949.0000 |
| -22 | trước/đến origin | 2015-10-19 | 2015-10-25 | 2537.0000 |
| -21 | trước/đến origin | 2015-10-26 | 2015-11-01 | 2451.0000 |
| -20 | trước/đến origin | 2015-11-02 | 2015-11-08 | 2474.0000 |
| -19 | trước/đến origin | 2015-11-09 | 2015-11-15 | 2356.0000 |
| -18 | trước/đến origin | 2015-11-16 | 2015-11-22 | 2287.0000 |
| -17 | trước/đến origin | 2015-11-23 | 2015-11-29 | 2889.0000 |
| -16 | trước/đến origin | 2015-11-30 | 2015-12-06 | 2313.0000 |
| -15 | trước/đến origin | 2015-12-07 | 2015-12-13 | 1969.0000 |
| -14 | trước/đến origin | 2015-12-14 | 2015-12-20 | 2022.0000 |
| -13 | trước/đến origin | 2015-12-21 | 2015-12-27 | 2083.0000 |
| -12 | trước/đến origin | 2015-12-28 | 2016-01-03 | 2122.0000 |
| -11 | trước/đến origin | 2016-01-04 | 2016-01-10 | 2451.0000 |
| -10 | trước/đến origin | 2016-01-11 | 2016-01-17 | 2255.0000 |
| -9 | trước/đến origin | 2016-01-18 | 2016-01-24 | 2291.0000 |
| -8 | trước/đến origin | 2016-01-25 | 2016-01-31 | 2268.0000 |
| -7 | trước/đến origin | 2016-02-01 | 2016-02-07 | 2503.0000 |
| -6 | trước/đến origin | 2016-02-08 | 2016-02-14 | 2574.0000 |
| -5 | trước/đến origin | 2016-02-15 | 2016-02-21 | 2967.0000 |
| -4 | trước/đến origin | 2016-02-22 | 2016-02-28 | 2517.0000 |
| -3 | trước/đến origin | 2016-02-29 | 2016-03-06 | 2272.0000 |
| -2 | trước/đến origin | 2016-03-07 | 2016-03-13 | 2157.0000 |
| -1 | trước/đến origin | 2016-03-14 | 2016-03-20 | 2625.0000 |
| 0 | trước/đến origin | 2016-03-21 | 2016-03-27 | 2951.0000 |
| 1 | test | 2016-03-28 | 2016-04-03 | 2858.0000 |
| 2 | test | 2016-04-04 | 2016-04-10 | 2554.0000 |
| 3 | test | 2016-04-11 | 2016-04-17 | 2471.0000 |
| 4 | test | 2016-04-18 | 2016-04-24 | 2553.0000 |

Bằng chứng mô tả xu hướng (OLS có intercept, không kiểm định ý nghĩa/nhân quả):

- 52 tuần trước/đến origin: slope OLS = **-17.2511 đơn vị/tuần mỗi bước tuần**; trung bình = 2812.9423 đơn vị/tuần; số bước giảm = 27/51.
- 4 tuần test: slope OLS = **-99.8000 đơn vị/tuần mỗi bước tuần**; trung bình = 2609.0000 đơn vị/tuần; số bước giảm = 2/3.
- Toàn bộ 56 tuần, đối chiếu hồi cứu: slope OLS = **-15.2954 đơn vị/tuần mỗi bước tuần**; trung bình = 2798.3750 đơn vị/tuần; số bước giảm = 30/55.
- Hai nửa năm trước origin: 26 tuần đầu 3146.6154 → 26 tuần sau 2479.2692 đơn vị/tuần (-21.2084%).
- Bốn tuần cuối trước origin 2501.2500 → bốn tuần test 2609.0000 đơn vị/tuần (4.3078%).

**Kết luận:** xác nhận xu hướng giảm tuyến tính trên 52 tuần lịch sử theo dấu slope; xác nhận xu hướng giảm tuyến tính trong bốn tuần test. Xu hướng trung bình không đồng nghĩa giảm đơn điệu. So sánh trung bình bốn tuần test với bốn tuần cuối lịch sử được nêu riêng, không đồng nhất với slope trong từng cửa sổ.

#### Tỷ số cho từng sản phẩm tại origin test

Mẫu số là trung bình tuần của **26 tuần ngay trước bốn tuần cuối**, không chồng lấp: 31/08/2015–28/02/2016. Tử số là trung bình tuần của bốn tuần cuối: 29/02–27/03/2016. Trung bình ngày cho cùng khoảng cho đúng tỷ số này. Tỷ số <1 là mức bán gần origin thấp hơn khoảng đối chiếu, không tự chứng minh xu hướng đơn điệu.

| Sản phẩm | TB tuần 26 tuần trước đó | TB tuần 4 tuần cuối | Tỷ số 4/26 |
| --- | --- | --- | --- |
| FOODS_2_019 | 114.1154 | 108.2500 | 0.9486 |
| FOODS_2_197 | 118.7308 | 108.7500 | 0.9159 |
| FOODS_3_080 | 122.1923 | 132.7500 | 1.0864 |
| FOODS_3_090 | 325.1538 | 378.2500 | 1.1633 |
| FOODS_3_099 | 124.1154 | 103.7500 | 0.8359 |
| FOODS_3_120 | 246.6538 | 172.2500 | 0.6983 |
| FOODS_3_202 | 107.8462 | 102.2500 | 0.9481 |
| FOODS_3_252 | 245.3462 | 231.5000 | 0.9436 |
| FOODS_3_318 | 41.8846 | 86.2500 | 2.0592 |
| FOODS_3_319 | 30.5385 | 57.5000 | 1.8829 |
| FOODS_3_541 | 27.0385 | 7.2500 | 0.2681 |
| FOODS_3_555 | 119.4615 | 121.7500 | 1.0192 |
| FOODS_3_586 | 268.9231 | 260.0000 | 0.9668 |
| FOODS_3_587 | 174.7308 | 220.7500 | 1.2634 |
| FOODS_3_635 | 13.3077 | 0.0000 | 0.0000 |
| FOODS_3_681 | 159.3077 | 87.7500 | 0.5508 |
| FOODS_3_694 | 80.3462 | 77.2500 | 0.9615 |
| FOODS_3_714 | 153.8077 | 133.5000 | 0.8680 |
| FOODS_3_741 | 95.8846 | 99.2500 | 1.0351 |
| FOODS_3_808 | 42.6923 | 12.2500 | 0.2869 |

**Bằng chứng:** 13/20 sản phẩm có tỷ số <1. Tỷ số của tổng panel = 0.9576 (2501.2500 / 2612.0769); đây không phải trung bình các tỷ số sản phẩm.

### 2.3. Panel chọn bằng tổng bán: chỉ dùng dữ liệu đến origin đầu tiên

**Giới hạn nhận diện:** thời điểm chốt panel là cuối 06/12/2015; code chọn bằng tổng bán trước 07/12/2015. Yêu cầu chỉ dùng dữ liệu trước/đến mốc này không cho phép quan sát mức bán sau khi chọn. Vì vậy **chưa đủ dữ liệu trong phạm vi mục 2.3 để xác nhận/bác bỏ bán giảm sau thời điểm chọn**. Không dùng số liệu test/validation của mục 2.1–2.2 để lấp khoảng trống này. Phần có thể kiểm tra là dấu hiệu giảm đã xuất hiện trước lúc chốt panel hay chưa. Ngày 06/12 được tính vào lịch sử vì là ngày origin, quan sát đã biết trước dự báo 07/12.

Hàm `selection_period` chỉ nhận 35460 dòng history có date ≤ 2015-12-06, assert không có dòng sau mốc, và assert tổng bán từng sản phẩm khớp `train_units` trong selected_series.csv. Không tái chọn sản phẩm từ nhãn tương lai. Đây là đối chiếu panel đã lưu; không tự xác minh thứ hạng top 20 so với toàn bộ sản phẩm CA_1 vì history chỉ chứa panel đã chọn.

Bối cảnh hoàn toàn trước lúc chọn: 52 tuần 08/12/2014–06/12/2015.

- 52 tuần trước/đến origin đầu tiên: slope OLS = **-0.1768 đơn vị/tuần mỗi bước tuần**; trung bình = 2978.3077 đơn vị/tuần; số bước giảm = 29/51.
- TB 26 tuần đầu 2891.1154 → 26 tuần sau 3065.5000 đơn vị/tuần (6.0317%).
- TB bốn tuần cuối 2461.2500 / TB 26 tuần ngay trước đó 3088.7692 = 0.7968.

Chi tiết tỷ số chỉ dùng lịch sử trước chọn: tử số 09/11–06/12/2015; mẫu số 11/05–08/11/2015 (26 tuần liền trước, không chồng lấp).

| Sản phẩm | TB tuần 26 tuần trước đó | TB tuần 4 tuần cuối trước chọn | Tỷ số 4/26 |
| --- | --- | --- | --- |
| FOODS_2_019 | 108.1923 | 99.0000 | 0.9150 |
| FOODS_2_197 | 120.6923 | 110.5000 | 0.9156 |
| FOODS_3_080 | 132.0385 | 132.0000 | 0.9997 |
| FOODS_3_090 | 364.5385 | 396.7500 | 1.0884 |
| FOODS_3_099 | 125.1154 | 131.0000 | 1.0470 |
| FOODS_3_120 | 349.3077 | 132.7500 | 0.3800 |
| FOODS_3_202 | 97.3846 | 105.0000 | 1.0782 |
| FOODS_3_252 | 301.5769 | 238.5000 | 0.7908 |
| FOODS_3_318 | 65.5000 | 0.0000 | 0.0000 |
| FOODS_3_319 | 29.0385 | 0.0000 | 0.0000 |
| FOODS_3_541 | 70.1154 | 0.0000 | 0.0000 |
| FOODS_3_555 | 130.6538 | 127.2500 | 0.9739 |
| FOODS_3_586 | 344.6154 | 299.7500 | 0.8698 |
| FOODS_3_587 | 204.2692 | 162.0000 | 0.7931 |
| FOODS_3_635 | 39.5769 | 0.0000 | 0.0000 |
| FOODS_3_681 | 133.1154 | 165.0000 | 1.2395 |
| FOODS_3_694 | 80.5000 | 101.0000 | 1.2547 |
| FOODS_3_714 | 181.9615 | 164.2500 | 0.9027 |
| FOODS_3_741 | 132.8077 | 96.5000 | 0.7266 |
| FOODS_3_808 | 77.7692 | 0.0000 | 0.0000 |

**Bằng chứng:** 15/20 sản phẩm có mức bán bốn tuần sát ngày chọn thấp hơn 26 tuần đối chiếu. Cả 5 sản phẩm thuộc nhóm thưa đều có tổng bán bằng 0 trong bốn tuần sát ngày chọn (09/11–06/12/2015), dù tổng bán tích lũy vẫn đủ để nằm trong panel đã lưu. Slope cả năm gần 0 (-0.1768), trong khi trung bình nửa năm sau còn cao hơn nửa năm đầu 6.0317%; vì vậy không mô tả cả năm trước chọn là một đợt giảm nhất quán. Các con số này chỉ mô tả mức giảm trước ngày chọn và sự khác biệt giữa sản phẩm. Tổng bán tích lũy cao không đồng nghĩa mức bán gần ngày chọn vẫn cao. **Suy đoán chưa được chứng minh:** chọn theo tổng lịch sử có thể giữ lại sản phẩm từng bán mạnh nhưng gần đây bán ít; chưa thể nói chính cách chọn gây giảm bán sau đó, hoặc quy giảm bán cho hết hàng, vòng đời, giá hay mùa vụ.

### 2.4. Tái lập và kiểm tra của phần bổ sung

Script [diagnose_supplement2.py](../../scripts/diagnose_supplement2.py) chỉ đọc ba CSV đầu vào, dùng thư viện chuẩn và numpy trong requirements, rồi in toàn bộ mục Bổ sung 2 ra stdout. Không ghi file từ trong script, không import code huấn luyện. Lệnh đã dùng:

```powershell
.\.venv\Scripts\python.exe scripts\diagnose_supplement2.py > .runtime/supplement2.md
```

Sau đó nối nội dung UTF-8 của `.runtime/supplement2.md` vào cuối `docs/review/DIAGNOSIS.md` một lần. Script có assert tính slope, khóa panel, actual khớp history, đủ 28 h cho từng sản phẩm/mô hình/split, origin đúng, seasonal naive khớp lặp tuần origin, đồng nhất thức bias ở mỗi nhóm và tổng test khớp bốn tuần. Không chạy unittest có fit/train; không dùng phân tích này để chọn cấu hình mới.

SHA-256 đầu vào phần bổ sung:

- `outputs/forecast/history.csv`: `5f288fa6bf79cd878e4e2e71c74796984177871f16630ed6a6ebf189825d9d04`
- `outputs/forecast/predictions.csv`: `0061676b7286b0b95c32a24164bbb859ff795513d849c8162b856780cccb2d42`
- `outputs/forecast/selected_series.csv`: `232acaeaf4f1e87dcd17742a80521bc42346f070f2aaffbb91b9cb640eff658d`
