# Kết quả V3

Ứng viên đã chọn trước test: **blend**. Cổng tích hợp: **3/3 cửa hàng** đạt đồng thời MAE và |bias_pct| trên cả recent và legacy; yêu cầu ít nhất 2/3. Quyết định: đưa thủ tục V2 đã chọn làm mặc định; giữ V1 qua cờ.

CA_1 và CA_2, kể cả test, đều đã xem. V3 chỉ chọn bằng validation của hai store này, tái dùng nguyên output V2, không train lại RF/direct. CA_3, TX_1, WI_1 là ba store chưa dùng trước lượt test này; cấu hình/thủ tục đóng băng trước validation mới. Giờ các test đó cũng đã được xem; không gọi chúng là test tươi cho lần phát triển kế tiếp.

## Chọn bằng validation đã có

| Ứng viên | Điểm MAE / RF | Thay đổi % | TB trị tuyệt đối bias_pct | Đủ điều kiện bias |
| --- | --- | --- | --- | --- |
| weekday_mean4 | 0.9964 | -0.3639 | 3.3725 | True |
| blend | 0.9467 | -5.3256 | 3.3896 | True |
| rf_calibrated | 0.9730 | -2.6969 | 0.0000 | True |
| random_forest | 1.0000 | 0.0000 | 8.1696 | True |

Điểm = trung bình bốn tỷ số điểm MAE qua CA_1/CA_2 × hai panel. Điểm mỗi bộ = trung vị origin trong nhóm rồi trung vị bốn nhóm, sau trung bình metric ba seed. Metric gộp dưới đây khác điểm chọn. RF×k có bias validation gần 0 theo định nghĩa vì fit k và đánh giá trên cùng nhãn; không coi đó là bằng chứng độc lập về hiệu chỉnh. Hệ số k không bị đóng băng chung: mỗi store/panel dùng validation của chính nó.

| Store | Panel | Ứng viên | Điểm MAE nhóm | MAE gộp | RMSE | Bias % |
| --- | --- | --- | --- | --- | --- | --- |
| CA_1 | recent | random_forest | 9.7986 | 9.6640 | 14.1412 | 10.5559 |
| CA_1 | recent | weekday_mean4 | 8.7096 | 8.9295 | 13.9829 | -0.6095 |
| CA_1 | recent | blend | 9.0748 | 8.9679 | 13.0744 | 4.9732 |
| CA_1 | recent | rf_calibrated | 9.5672 | 9.4264 | 13.7695 | 0.0000 |
| CA_1 | legacy | random_forest | 7.2116 | 7.5205 | 11.5304 | 4.9567 |
| CA_1 | legacy | weekday_mean4 | 7.5312 | 7.7711 | 13.0600 | -2.3713 |
| CA_1 | legacy | blend | 6.9832 | 7.3185 | 11.7076 | 1.2927 |
| CA_1 | legacy | rf_calibrated | 7.0922 | 7.4160 | 11.4677 | 0.0000 |
| CA_2 | recent | random_forest | 7.2103 | 7.3703 | 10.0665 | 10.1584 |
| CA_2 | recent | weekday_mean4 | 7.4174 | 7.4472 | 10.8780 | 3.9642 |
| CA_2 | recent | blend | 6.9056 | 7.1723 | 10.0306 | 7.0613 |
| CA_2 | recent | rf_calibrated | 6.9891 | 7.1218 | 9.8604 | 0.0000 |
| CA_2 | legacy | random_forest | 7.1838 | 7.2558 | 10.0897 | 7.0076 |
| CA_2 | legacy | weekday_mean4 | 7.3529 | 7.8872 | 11.8230 | -6.5450 |
| CA_2 | legacy | blend | 6.7153 | 7.1994 | 10.3591 | 0.2313 |
| CA_2 | legacy | rf_calibrated | 6.9178 | 7.0564 | 9.9376 | 0.0000 |

## Lượt test cuối duy nhất tại ba store mới

Trung bình metric seed42/43/44, không phải metric của ensemble. nRMSE chia sai số từng item cho max(mean_28 trước origin,1), rồi căn trung bình bình phương. Δ = bias model − bias seasonal_naive, có dấu; Δ thấp hơn không bảo đảm |bias| thấp hơn.

| Store | Panel | Mô hình | MAE | RMSE | Bias % | nRMSE | Δ đơn vị |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CA_3 | recent | blend | 12.5922 | 17.0023 | 2.7767 | 0.7492 | -1250.8868 |
| CA_3 | recent | random_forest | 12.7780 | 16.9674 | 9.1025 | 0.7632 | 9.2264 |
| CA_3 | recent | weekday_mean4 | 13.5009 | 18.5796 | -3.5492 | 0.7911 | -2511.0000 |
| CA_3 | recent | seasonal_naive | 16.5071 | 22.4794 | 9.0562 | 0.9557 | 0.0000 |
| CA_3 | legacy | blend | 11.8323 | 16.6571 | 12.4114 | 0.7969 | -961.7391 |
| CA_3 | legacy | random_forest | 12.5332 | 17.0968 | 21.6603 | 0.8255 | 538.5218 |
| CA_3 | legacy | weekday_mean4 | 12.4429 | 17.7918 | 3.1626 | 0.8127 | -2462.0000 |
| CA_3 | legacy | seasonal_naive | 15.0089 | 20.7944 | 18.3404 | 0.9205 | 0.0000 |
| TX_1 | recent | blend | 6.9515 | 8.9033 | 13.0990 | 0.5066 | 11.6736 |
| TX_1 | recent | random_forest | 8.4816 | 10.4661 | 26.7527 | 0.6070 | 1685.3473 |
| TX_1 | recent | weekday_mean4 | 6.9098 | 9.4529 | -0.5547 | 0.5254 | -1662.0000 |
| TX_1 | recent | seasonal_naive | 9.5321 | 13.6198 | 13.0038 | 0.7280 | 0.0000 |
| TX_1 | legacy | blend | 6.7647 | 8.7920 | 14.1494 | 1.9206 | 356.5747 |
| TX_1 | legacy | random_forest | 8.6109 | 10.7464 | 30.6237 | 1.8865 | 2220.1494 |
| TX_1 | legacy | weekday_mean4 | 6.5848 | 9.3886 | -2.3250 | 2.0981 | -1507.0000 |
| TX_1 | legacy | seasonal_naive | 8.6500 | 12.9971 | 10.9972 | 2.1160 | 0.0000 |
| WI_1 | recent | blend | 5.0923 | 6.9597 | 6.8973 | 2.0203 | -188.2527 |
| WI_1 | recent | random_forest | 5.6772 | 7.6326 | 16.8191 | 2.7753 | 592.4945 |
| WI_1 | recent | weekday_mean4 | 5.1054 | 7.1466 | -3.0245 | 2.2378 | -969.0000 |
| WI_1 | recent | seasonal_naive | 7.0161 | 10.3181 | 9.2896 | 2.2759 | 0.0000 |
| WI_1 | legacy | blend | 4.6435 | 6.0550 | 8.2808 | 0.4966 | -190.3418 |
| WI_1 | legacy | random_forest | 4.8182 | 6.2986 | 12.2969 | 0.5213 | 122.3165 |
| WI_1 | legacy | weekday_mean4 | 4.7795 | 6.2148 | 4.2646 | 0.5083 | -503.0000 |
| WI_1 | legacy | seasonal_naive | 6.3054 | 8.6302 | 10.7258 | 0.6830 | 0.0000 |

## Thay đổi giúp hoặc không giúp bao nhiêu

| Store | Panel | Đối chứng | Chênh MAE với RF | Chênh MAE % | Chênh độ lớn bias (điểm %) | Chênh RMSE | Chênh nRMSE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CA_3 | recent | blend | -0.1858 | -1.4537 | -6.3259 | 0.0349 | -0.0141 |
| CA_3 | recent | weekday_mean4 | 0.7229 | 5.6573 | -5.5533 | 1.6122 | 0.0279 |
| CA_3 | recent | seasonal_naive | 3.7291 | 29.1841 | -0.0463 | 5.5120 | 0.1925 |
| CA_3 | legacy | blend | -0.7009 | -5.5921 | -9.2489 | -0.4396 | -0.0286 |
| CA_3 | legacy | weekday_mean4 | -0.0903 | -0.7205 | -18.4978 | 0.6950 | -0.0128 |
| CA_3 | legacy | seasonal_naive | 2.4758 | 19.7537 | -3.3199 | 3.6976 | 0.0949 |
| TX_1 | recent | blend | -1.5301 | -18.0404 | -13.6537 | -1.5628 | -0.1004 |
| TX_1 | recent | weekday_mean4 | -1.5718 | -18.5319 | -26.1980 | -1.0133 | -0.0815 |
| TX_1 | recent | seasonal_naive | 1.0505 | 12.3858 | -13.7490 | 3.1537 | 0.1210 |
| TX_1 | legacy | blend | -1.8462 | -21.4402 | -16.4743 | -1.9545 | 0.0341 |
| TX_1 | legacy | weekday_mean4 | -2.0261 | -23.5294 | -28.2987 | -1.3578 | 0.2116 |
| TX_1 | legacy | seasonal_naive | 0.0391 | 0.4539 | -19.6265 | 2.2507 | 0.2295 |
| WI_1 | recent | blend | -0.5849 | -10.3019 | -9.9218 | -0.6729 | -0.7550 |
| WI_1 | recent | weekday_mean4 | -0.5718 | -10.0722 | -13.7946 | -0.4860 | -0.5375 |
| WI_1 | recent | seasonal_naive | 1.3389 | 23.5839 | -7.5295 | 2.6854 | -0.4994 |
| WI_1 | legacy | blend | -0.1748 | -3.6274 | -4.0162 | -0.2437 | -0.0247 |
| WI_1 | legacy | weekday_mean4 | -0.0388 | -0.8047 | -8.0323 | -0.0839 | -0.0130 |
| WI_1 | legacy | seasonal_naive | 1.4871 | 30.8644 | -1.5712 | 2.3316 | 0.1617 |

Giảm là tốt hơn cho cả hai cột chênh MAE và chênh |bias|. Giữ cả hàng kém hơn RF. Không chọn lại weekday_mean4 hoặc RF×k bằng test. Không thử direct nữa vì Pha 1 chỉ chẩn đoán model đã có.
Blend không cải thiện mọi metric: bảng giữ cả RMSE CA_3/recent và nRMSE TX_1/legacy kém RF. Cổng đã đăng ký chỉ kiểm MAE và độ lớn bias; không thay điều kiện sau khi thấy các metric này. Weekday_mean4 cũng không luôn giảm MAE so với RF, dù tốt hơn seasonal_naive.

## Cổng tích hợp đã đăng ký trước

| Store | Recent đạt | Legacy đạt | Store đạt |
| --- | --- | --- | --- |
| CA_3 | True | True | True |
| TX_1 | True | True | True |
| WI_1 | True | True | True |

Một store chỉ đạt khi cả hai panel đồng thời có MAE candidate≤RF và |bias_pct candidate|≤|bias_pct RF|. Không gộp hai panel để che panel kém. Cổng test chỉ accept/reject thủ tục đã chọn, không được đổi candidate hoặc tham số sau khi biết test.

## Bằng chứng và tái lập

- [Kế hoạch](V3_PLAN.md), [lựa chọn từ validation](V3_SELECTION.json), [manifest đóng băng](V3_FROZEN.json).
- [V3_TEST_METRICS.csv](V3_TEST_METRICS.csv), [V3_SEED_METRICS.csv](V3_SEED_METRICS.csv), [V3_BIAS_BY_H.csv](V3_BIAS_BY_H.csv), [V3_AUDIT.json](V3_AUDIT.json).
- [Chẩn đoán Bổ sung 3](DIAGNOSIS.md): cặp item/origin lỗi direct, top NSSE RF, bias tập trung, và tổng tuần cùng giỏ 20 item mọi store; bốn tuần sau ở store mới chỉ công bố sau test_complete.

```powershell
.\.venv\Scripts\python.exe scripts/diagnose_supplement3.py
.\.venv\Scripts\python.exe scripts/select_forecast_v3.py
.\.venv\Scripts\python.exe scripts/run_forecast_v3.py prepare
.\.venv\Scripts\python.exe scripts/run_forecast_v3.py test
.\.venv\Scripts\python.exe scripts/diagnose_supplement3.py --reveal-after-test
.\.venv\Scripts\python.exe scripts/report_forecast_v3.py
```

Không lặp lệnh test trên output đã tiêu thụ: test_started tạo độc quyền và chặn trước đọc nhãn; test_complete chỉ ghi khi đủ cả ba store/hai panel. Cache validation và dự báo/model RF ở origin test được dùng lại, không train lại kết quả đã có. Các lệnh chẩn đoán/report chỉ đọc; chạy lại report không phải chạy lại test. Bản tích hợp cuối và kết quả unittest ghi ở mục bàn giao bên dưới.

## Giới hạn

Thiết kế đã chịu ảnh hưởng chẩn đoán hồi cứu. Validation 13 origin chồng giữa nhóm nên không phải 13 mẫu độc lập; không tính CI giả định độc lập. Ba seed không thay thế ba dataset độc lập. RF×k in-sample validation có lạc quan, không được kết luận hiệu chỉnh tốt trên test khi không được chọn để đánh giá. Tổng tuần giỏ CA_1 legacy không đại diện toàn store hoặc panel riêng. Bảng tuần sau test làm lộ thêm tổng gộp của các store khác; không gọi những tổng này là dữ liệu chưa xem cho thí nghiệm sau. Không suy ra stockout hoặc nhân quả từ scale thấp, chuỗi 0 hay lễ. Ba store dùng cùng khoảng lịch test trong cùng dataset, không phải thử trên một giai đoạn tương lai độc lập; kết quả có thể cùng chịu bối cảnh chung. Hai panel không cùng tập sản phẩm; không diễn giải đổi panel là tác động nhân quả. Không thêm thư viện hoặc tìm siêu tham số mới.

## Bàn giao tích hợp Pha 4

`run_pipeline.ps1` mặc định gọi `code/15_forecasting_v3.py` (V2, blend đóng băng, panel recent, seed42). `-V1` gọi `code/13_forecasting_v1.py` nguyên bản; `code/13_forecasting.py` cũng giữ nguyên để tương thích các lệnh V1 trực tiếp. `-Store` và `-Panel` đổi bộ dữ liệu, không chọn lại ứng viên. Các tên file/cột history/predictions/metrics CSV dashboard đọc giữ nguyên; thêm hàng weekday_mean4 và metadata phiên bản/tên candidate. Dashboard đã cập nhật nhãn blend, k, validation và giới hạn test để không gọi blend là RF hoặc validation độc lập.

```powershell
.\run_pipeline.ps1 -SkipInstall
.\run_pipeline.ps1 -SkipInstall -V1
.\run_pipeline.ps1 -SkipInstall -Store TX_1 -Panel legacy
# Chỉ xuất lại cache, không chạy lại phân tích Spark hoặc train kết quả đã có:
.\.venv\Scripts\python.exe code/15_forecasting_v3.py --store CA_1 --panel recent
```

Đã công bố lại `outputs/forecast` từ cache CA_1/recent, không fit RF lại. Bộ V1 trước đó được sao lưu nguyên file ở `outputs/forecast_v1_retained`, đã đối chiếu hash. Không xuất lại model blend pickle; JSON ghi rõ file random_forest.joblib V1 còn tồn tại không phải model V2 được chọn. Dashboard dùng CSV/JSON. Kết quả nghiên cứu vẫn ba seed; artifact demo chỉ seed42 để mỗi item/ngày/model có một dòng. Khi store thực sự chưa có cache, pipeline fit RF theo giao thức cố định và tính k từ validation riêng, rồi lưu cache để không fit lại.

Kiểm tra: 33 unittest đạt trước commit cuối, gồm V1/Spark/dashboard cũ, mutation 1e9, selection/cổng, guard test, schema CSV, cache không fit lại, nhánh store mới tự tính k bằng fixture không cần output V2. Dashboard chạy được với cache thật CA_1/recent và TX_1/legacy; dự báo xuất TX_1/legacy khớp từng giá trị blend đã test. Đã kiểm cú pháp PowerShell, CLI help V1/V2, 2016 dòng bias h khớp 72 seed metric, và hash thủ tục dự báo không đổi từ freeze. Nhật ký trước/sau từng commit: `.runtime/v3_phase{1..4}_{pre,post}.log`.

Không chạy lại toàn bộ phân tích 58 triệu dòng hoặc grid search V1 trong Pha 4, vì đã có kết quả; nhánh bootstrap store mới được kiểm bằng fixture, chưa train store thứ tư. Không push, không merge main. Chạy lại report/chẩn đoán từ cache không phải lượt test mới.
