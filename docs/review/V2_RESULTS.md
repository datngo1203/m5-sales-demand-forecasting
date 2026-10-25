# Kết quả thí nghiệm V2

Thiết kế đã xem trước: panel recent được gợi ý từ chẩn đoán hồi cứu trên CA_1 có test đã xem. CA_1 test là đối chiếu hồi cứu; CA_2 dùng nguyên cấu hình và quyết định đóng băng từ CA_1, không chọn lại bằng validation/test CA_2. Chỉ CA_2 test được xem là test tươi trong công việc này. Đã chạy một lượt test cuối cho cả hai cửa hàng, hai panel và ba seed; không chỉnh tham số/ngưỡng/feature sau khi xem test.

## Kết luận mô tả

- Baseline mới có MAE thấp hơn seasonal_naive cũ ở 8/8 tổ hợp store/panel/split. Đây là đối chiếu cùng sản phẩm/ngày; bảng dưới ghi rõ mức thay đổi từng tổ hợp.
- Raw direct có MAE thấp hơn RF ở 4/4 tổ hợp test. Kết quả test này không được dùng để đảo quyết định validation; cổng chung đã trượt ở panel legacy CA_1 nên V2 frozen vẫn là RF.
- Trên test tươi CA_2/recent, raw direct MAE 5.5964 so với RF 6.4811 (-13.6504%), nhưng bias_pct là -11.2255% so với RF 2.9625%. Giảm Δ có dấu không bảo đảm giảm |bias|.
- Đổi panel không cải thiện đồng đều: xem riêng metric recent và legacy dưới cùng RF. Hai tập sản phẩm khác nhau nên không diễn giải chênh lệch đó là tác động nhân quả của cách chọn.

## Cổng quyết định và cấu hình giữ lại

| Panel CA_1 | Origin Δ_direct < Δ_RF | Điểm MAE RF | Điểm MAE direct | Tỷ số MAE | Qua cổng |
| --- | --- | --- | --- | --- | --- |
| recent | 12/13 | 9.7986 | 8.8044 | 0.8985 | có |
| legacy | 11/13 | 7.2116 | 8.2262 | 1.1407 | không |

Điểm chọn = trung vị origin trong từng nhóm sau trung bình metric ba seed, rồi trung vị bốn nhóm; Δ là chênh bias có dấu so với seasonal_naive. Cổng yêu cầu ít nhất 9/13 origin và tỷ số MAE ≤1.03 trên **cả hai** panel CA_1.

**Cổng không đạt: không thực hiện Bước 2.** Không fit k, không chọn sparse fallback, không đổi sang direct. `v2_frozen` giữ `random_forest` trên cả hai panel; raw direct vẫn được báo cáo như đối chứng, kể cả khi kém hơn. Do Bước 2 bị khóa, phân tích loại fold chuỗi 0 và các candidate hiệu chỉnh/fallback được ghi là không thực hiện, không ghi bằng số 0 hoặc coi là không có tác động.

Pipeline/dashboard mặc định vẫn là V1 và giữ nguyên CSV/JSON tại `outputs/forecast`; kết quả V2 nằm riêng trong `outputs/forecast_v2`. V1 trong các bảng là **RF hiện hành** window=180, depth=12, leaf=5, 100 cây; không phải RF cũ hơn `reference_test` và không phải toàn bộ chiến lược V1 chọn model theo sản phẩm. Không rerun grid search V1 để tạo một đối chứng khác. Bản đầy đủ V1 được bảo tồn ở `code/13_forecasting_v1.py`.

## Panel và giới hạn so sánh

| Cửa hàng | Panel | 20 sản phẩm |
| --- | --- | --- |
| CA_1 | recent | FOODS_3_090, FOODS_3_586, FOODS_3_120, FOODS_3_252, FOODS_3_064, FOODS_3_587, FOODS_3_714, FOODS_3_282, FOODS_3_499, FOODS_3_362, FOODS_3_555, FOODS_3_080, FOODS_3_741, FOODS_3_099, FOODS_3_681, FOODS_2_197, FOODS_3_785, FOODS_3_501, FOODS_2_019, FOODS_3_702 |
| CA_1 | legacy | FOODS_3_090, FOODS_3_586, FOODS_3_252, FOODS_3_120, FOODS_3_714, FOODS_3_587, FOODS_3_808, FOODS_2_197, FOODS_3_080, FOODS_3_541, FOODS_3_555, FOODS_3_635, FOODS_3_741, FOODS_2_019, FOODS_3_318, FOODS_3_099, FOODS_3_681, FOODS_3_202, FOODS_3_319, FOODS_3_694 |
| CA_2 | recent | FOODS_3_252, FOODS_3_090, FOODS_3_586, FOODS_3_555, FOODS_3_288, FOODS_3_120, FOODS_3_714, FOODS_3_080, FOODS_3_804, FOODS_3_739, FOODS_3_362, FOODS_3_587, FOODS_1_218, FOODS_3_282, FOODS_3_008, FOODS_3_499, FOODS_3_389, FOODS_3_723, FOODS_1_012, FOODS_3_135 |
| CA_2 | legacy | FOODS_3_586, FOODS_3_252, FOODS_3_090, FOODS_3_555, FOODS_1_218, FOODS_3_080, FOODS_3_808, FOODS_3_804, FOODS_3_635, FOODS_3_541, FOODS_3_319, FOODS_3_714, FOODS_3_288, FOODS_1_012, FOODS_3_587, FOODS_3_318, FOODS_3_739, FOODS_3_228, FOODS_3_491, FOODS_3_723 |

- CA_1: giao hai panel = 13/20. Khác biệt metric giữa panel còn do khác thành phần sản phẩm, không được quy toàn bộ cho cải thiện thuật toán.
- CA_2: giao hai panel = 13/20. Khác biệt metric giữa panel còn do khác thành phần sản phẩm, không được quy toàn bộ cho cải thiện thuật toán.

## So sánh V1 RF và phương án V2 đóng băng

Các metric là trung bình metric tính riêng cho seed 42,43,44; không phải metric của dự báo ensemble. Validation gộp 13 origin đếm lặp nhãn giữa các nhóm. Normalized RMSE dùng scale max(mean_28 trước mỗi origin,1) cho từng sản phẩm.

| Store | Panel | Split | Mô hình | MAE | RMSE | Bias % | B_SN | Δ | nRMSE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CA_1 | recent | validation | V1 RF | 9.6640 | 14.1412 | 10.5559 | -1521.0000 | 16969.4650 | 6.4410 |
| CA_1 | recent | validation | V2 frozen | 9.6640 | 14.1412 | 10.5559 | -1521.0000 | 16969.4650 | 6.4410 |
| CA_1 | recent | test | V1 RF | 8.7286 | 12.8631 | 12.0459 | 167.0000 | 1360.5398 | 5.7742 |
| CA_1 | recent | test | V2 frozen | 8.7286 | 12.8631 | 12.0459 | 167.0000 | 1360.5398 | 5.7742 |
| CA_1 | legacy | validation | V1 RF | 7.5205 | 11.5304 | 4.9567 | -2474.0000 | 8611.0636 | 4.1161 |
| CA_1 | legacy | validation | V2 frozen | 7.5205 | 11.5304 | 4.9567 | -2474.0000 | 8611.0636 | 4.1161 |
| CA_1 | legacy | test | V1 RF | 7.5459 | 11.1965 | 18.6229 | 1368.0000 | 575.4812 | 1.5766 |
| CA_1 | legacy | test | V2 frozen | 7.5459 | 11.1965 | 18.6229 | 1368.0000 | 575.4812 | 1.5766 |
| CA_2 | recent | validation | V1 RF | 7.3703 | 10.0665 | 10.1584 | 2284.0000 | 10661.8061 | 3.6909 |
| CA_2 | recent | validation | V2 frozen | 7.3703 | 10.0665 | 10.1584 | 2284.0000 | 10661.8061 | 3.6909 |
| CA_2 | recent | test | V1 RF | 6.4811 | 8.6169 | 2.9625 | 800.0000 | -481.4689 | 4.2256 |
| CA_2 | recent | test | V2 frozen | 6.4811 | 8.6169 | 2.9625 | 800.0000 | -481.4689 | 4.2256 |
| CA_2 | legacy | validation | V1 RF | 7.2558 | 10.0897 | 7.0076 | -5997.0000 | 15425.4042 | 5.0942 |
| CA_2 | legacy | validation | V2 frozen | 7.2558 | 10.0897 | 7.0076 | -5997.0000 | 15425.4042 | 5.0942 |
| CA_2 | legacy | test | V1 RF | 7.6167 | 10.0744 | 15.2628 | 2557.0000 | -1109.0165 | 0.6005 |
| CA_2 | legacy | test | V2 frozen | 7.6167 | 10.0744 | 15.2628 | 2557.0000 | -1109.0165 | 0.6005 |

## Toàn bộ đối chứng trên validation gộp và test

| Store | Panel | Split | Mô hình | MAE | RMSE | Bias % | B_SN | Δ | nRMSE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CA_1 | recent | validation | seasonal_naive | 9.7685 | 15.3548 | -1.0393 | -1521.0000 | 0.0000 | 3.6362 |
| CA_1 | recent | validation | weekday_mean4 | 8.9295 | 13.9829 | -0.6095 | -1521.0000 | 629.0000 | 3.6266 |
| CA_1 | recent | validation | random_forest | 9.6640 | 14.1412 | 10.5559 | -1521.0000 | 16969.4650 | 6.4410 |
| CA_1 | recent | validation | direct_poisson | 9.4845 | 14.7756 | -3.7590 | -1521.0000 | -3980.2753 | 4.4310 |
| CA_1 | recent | test | seasonal_naive | 9.7125 | 13.7872 | 1.3169 | 167.0000 | 0.0000 | 2.2415 |
| CA_1 | recent | test | weekday_mean4 | 7.8250 | 11.5830 | -9.1318 | 167.0000 | -1325.0000 | 2.2028 |
| CA_1 | recent | test | random_forest | 8.7286 | 12.8631 | 12.0459 | 167.0000 | 1360.5398 | 5.7742 |
| CA_1 | recent | test | direct_poisson | 7.8228 | 11.3912 | -7.1740 | 167.0000 | -1076.7376 | 2.1756 |
| CA_1 | legacy | validation | seasonal_naive | 8.5346 | 14.1998 | -1.9982 | -2474.0000 | 0.0000 | 4.0447 |
| CA_1 | legacy | validation | weekday_mean4 | 7.7711 | 13.0600 | -2.3713 | -2474.0000 | -462.0000 | 4.0105 |
| CA_1 | legacy | validation | random_forest | 7.5205 | 11.5304 | 4.9567 | -2474.0000 | 8611.0636 | 4.1161 |
| CA_1 | legacy | validation | direct_poisson | 8.1469 | 13.5172 | -3.5560 | -2474.0000 | -1928.7964 | 3.9628 |
| CA_1 | legacy | test | seasonal_naive | 8.3607 | 12.6112 | 13.1085 | 1368.0000 | 0.0000 | 1.1226 |
| CA_1 | legacy | test | weekday_mean4 | 6.4098 | 10.1445 | -4.1299 | 1368.0000 | -1799.0000 | 0.8706 |
| CA_1 | legacy | test | random_forest | 7.5459 | 11.1965 | 18.6229 | 1368.0000 | 575.4812 | 1.5766 |
| CA_1 | legacy | test | direct_poisson | 6.4208 | 10.4382 | 0.2819 | 1368.0000 | -1338.5800 | 0.7863 |
| CA_2 | recent | validation | seasonal_naive | 8.0676 | 11.8090 | 1.7922 | 2284.0000 | 0.0000 | 3.6564 |
| CA_2 | recent | validation | weekday_mean4 | 7.4472 | 10.8780 | 3.9642 | 2284.0000 | 2768.0000 | 3.6544 |
| CA_2 | recent | validation | random_forest | 7.3703 | 10.0665 | 10.1584 | 2284.0000 | 10661.8061 | 3.6909 |
| CA_2 | recent | validation | direct_poisson | 7.8223 | 11.2947 | 0.2281 | 2284.0000 | -1993.2814 | 3.1253 |
| CA_2 | recent | test | seasonal_naive | 8.1821 | 11.5916 | 7.4405 | 800.0000 | 0.0000 | 0.7375 |
| CA_2 | recent | test | weekday_mean4 | 5.7929 | 8.0646 | -12.3977 | 800.0000 | -2133.0000 | 0.6496 |
| CA_2 | recent | test | random_forest | 6.4811 | 8.6169 | 2.9625 | 800.0000 | -481.4689 | 4.2256 |
| CA_2 | recent | test | direct_poisson | 5.5964 | 7.8520 | -11.2255 | 800.0000 | -2006.9607 | 0.7701 |
| CA_2 | legacy | validation | seasonal_naive | 8.3922 | 12.4168 | -4.4572 | -5997.0000 | 0.0000 | 6.4826 |
| CA_2 | legacy | validation | weekday_mean4 | 7.8872 | 11.8230 | -6.5450 | -5997.0000 | -2809.0000 | 6.4922 |
| CA_2 | legacy | validation | random_forest | 7.2558 | 10.0897 | 7.0076 | -5997.0000 | 15425.4042 | 5.0942 |
| CA_2 | legacy | validation | direct_poisson | 10.2762 | 20.8226 | 0.6891 | -5997.0000 | 6924.1133 | 6.4215 |
| CA_2 | legacy | test | seasonal_naive | 10.1018 | 13.8237 | 26.9527 | 2557.0000 | 0.0000 | 0.7441 |
| CA_2 | legacy | test | weekday_mean4 | 7.5241 | 10.2807 | 10.4037 | 2557.0000 | -1570.0000 | 0.6100 |
| CA_2 | legacy | test | random_forest | 7.6167 | 10.0744 | 15.2628 | 2557.0000 | -1109.0165 | 0.6005 |
| CA_2 | legacy | test | direct_poisson | 6.9115 | 9.2621 | 10.4092 | 2557.0000 | -1569.4818 | 0.5433 |

## Từng thay đổi giúp hoặc không giúp bao nhiêu

Chênh MAE = MAE mô hình − MAE RF cùng store/panel/split; âm là tốt hơn. Chênh bias = bias mô hình − bias RF, có dấu nên thấp hơn có thể thành dự báo thiếu. Các số test chỉ dùng mô tả hồi cứu, không quay lại chọn candidate.

| Store | Panel | Split | Đối chứng | Chênh MAE | Chênh MAE % | Chênh bias đơn vị |
| --- | --- | --- | --- | --- | --- | --- |
| CA_1 | recent | validation | seasonal_naive | 0.1045 | 1.0817 | -16969.4650 |
| CA_1 | recent | validation | weekday_mean4 | -0.7345 | -7.6001 | -16340.4650 |
| CA_1 | recent | validation | direct_poisson | -0.1795 | -1.8579 | -20949.7402 |
| CA_1 | recent | test | seasonal_naive | 0.9839 | 11.2718 | -1360.5398 |
| CA_1 | recent | test | weekday_mean4 | -0.9036 | -10.3525 | -2685.5398 |
| CA_1 | recent | test | direct_poisson | -0.9058 | -10.3778 | -2437.2774 |
| CA_1 | legacy | validation | seasonal_naive | 1.0141 | 13.4844 | -8611.0636 |
| CA_1 | legacy | validation | weekday_mean4 | 0.2506 | 3.3317 | -9073.0636 |
| CA_1 | legacy | validation | direct_poisson | 0.6263 | 8.3285 | -10539.8601 |
| CA_1 | legacy | test | seasonal_naive | 0.8148 | 10.7984 | -575.4812 |
| CA_1 | legacy | test | weekday_mean4 | -1.1361 | -15.0554 | -2374.4812 |
| CA_1 | legacy | test | direct_poisson | -1.1251 | -14.9096 | -1914.0612 |
| CA_2 | recent | validation | seasonal_naive | 0.6973 | 9.4606 | -10661.8061 |
| CA_2 | recent | validation | weekday_mean4 | 0.0769 | 1.0431 | -7893.8061 |
| CA_2 | recent | validation | direct_poisson | 0.4520 | 6.1333 | -12655.0876 |
| CA_2 | recent | test | seasonal_naive | 1.7011 | 26.2468 | 481.4689 |
| CA_2 | recent | test | weekday_mean4 | -0.6882 | -10.6188 | -1651.5311 |
| CA_2 | recent | test | direct_poisson | -0.8847 | -13.6504 | -1525.4918 |
| CA_2 | legacy | validation | seasonal_naive | 1.1363 | 15.6611 | -15425.4042 |
| CA_2 | legacy | validation | weekday_mean4 | 0.6313 | 8.7009 | -18234.4042 |
| CA_2 | legacy | validation | direct_poisson | 3.0204 | 41.6270 | -8501.2909 |
| CA_2 | legacy | test | seasonal_naive | 2.4851 | 32.6269 | 1109.0165 |
| CA_2 | legacy | test | weekday_mean4 | -0.0926 | -1.2156 | -460.9835 |
| CA_2 | legacy | test | direct_poisson | -0.7052 | -9.2581 | -460.4653 |

Riêng thay baseline: weekday_mean4 so với seasonal_naive cũ trên cùng sản phẩm/ngày:

| Store | Panel | Split | Chênh MAE mới−cũ | Chênh MAE % | Chênh RMSE mới−cũ |
| --- | --- | --- | --- | --- | --- |
| CA_1 | recent | validation | -0.8390 | -8.5889 | -1.3719 |
| CA_1 | recent | test | -1.8875 | -19.4337 | -2.2042 |
| CA_1 | legacy | validation | -0.7635 | -8.9463 | -1.1398 |
| CA_1 | legacy | test | -1.9509 | -23.3340 | -2.4667 |
| CA_2 | recent | validation | -0.6204 | -7.6900 | -0.9310 |
| CA_2 | recent | test | -2.3893 | -29.2012 | -3.5270 |
| CA_2 | legacy | validation | -0.5050 | -6.0177 | -0.5938 |
| CA_2 | legacy | test | -2.5777 | -25.5171 | -3.5430 |

Tác động thay panel được mô tả riêng dưới cùng RF (hai tập sản phẩm khác nhau, không phải thí nghiệm ghép cặp trên cùng nhãn):

| Store | Split | RF legacy MAE | RF recent MAE | Chênh recent−legacy | Legacy bias % | Recent bias % |
| --- | --- | --- | --- | --- | --- | --- |
| CA_1 | validation | 7.5205 | 9.6640 | 2.1435 | 4.9567 | 10.5559 |
| CA_1 | test | 7.5459 | 8.7286 | 1.1827 | 18.6229 | 12.0459 |
| CA_2 | validation | 7.2558 | 7.3703 | 0.1145 | 7.0076 | 10.1584 |
| CA_2 | test | 7.6167 | 6.4811 | -1.1356 | 15.2628 | 2.9625 |

## Kết quả theo bốn nhóm validation và phần gộp

Nhóm 0/1/2/3 có lần lượt 4/3/3/3 origin, trong nhóm nhãn không chồng. Các nhóm chồng lấp nhau: 13 origin không độc lập; không tính CI coi chúng độc lập. Bảng nhóm là metric gộp các điểm dự báo trong nhóm, khác điểm chọn trung vị nhóm đã ghi ở trên.

### CA_1 / recent

| Nhóm | Mô hình | MAE | RMSE | Bias % | B_SN | Δ | nRMSE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | seasonal_naive | 9.7685 | 15.3548 | -1.0393 | -1521.0000 | 0.0000 | 3.6362 |
| all | weekday_mean4 | 8.9295 | 13.9829 | -0.6095 | -1521.0000 | 629.0000 | 3.6266 |
| all | random_forest | 9.6640 | 14.1412 | 10.5559 | -1521.0000 | 16969.4650 | 6.4410 |
| all | direct_poisson | 9.4845 | 14.7756 | -3.7590 | -1521.0000 | -3980.2753 | 4.4310 |
| all | v2_frozen | 9.6640 | 14.1412 | 10.5559 | -1521.0000 | 16969.4650 | 6.4410 |
| 0 | seasonal_naive | 9.7871 | 15.5339 | -2.0319 | -913.0000 | 0.0000 | 6.0256 |
| 0 | weekday_mean4 | 9.2498 | 14.8590 | 0.9614 | -913.0000 | 1345.0000 | 6.0161 |
| 0 | random_forest | 9.2441 | 13.1959 | 9.9541 | -913.0000 | 5385.6720 | 6.4074 |
| 0 | direct_poisson | 10.0816 | 15.7052 | -2.8244 | -913.0000 | -356.0786 | 6.7622 |
| 0 | v2_frozen | 9.2441 | 13.1959 | 9.9541 | -913.0000 | 5385.6720 | 6.4074 |
| 1 | seasonal_naive | 9.4929 | 14.8038 | -0.3993 | -134.0000 | 0.0000 | 0.8162 |
| 1 | weekday_mean4 | 9.2595 | 14.0804 | -0.4827 | -134.0000 | -28.0000 | 0.8443 |
| 1 | random_forest | 9.2840 | 13.6474 | 11.5579 | -134.0000 | 4013.0501 | 4.7607 |
| 1 | direct_poisson | 9.3021 | 14.6161 | -2.1748 | -134.0000 | -595.9183 | 0.8764 |
| 1 | v2_frozen | 9.2840 | 13.6474 | 11.5579 | -134.0000 | 4013.0501 | 4.7607 |
| 2 | seasonal_naive | 9.3137 | 14.3442 | -2.7714 | -933.0000 | 0.0000 | 1.5077 |
| 2 | weekday_mean4 | 8.8488 | 13.4954 | -0.7218 | -933.0000 | 690.0000 | 1.5123 |
| 2 | random_forest | 10.0836 | 14.8723 | 10.8232 | -933.0000 | 4576.6305 | 6.9450 |
| 2 | direct_poisson | 9.2921 | 14.3063 | -3.6457 | -933.0000 | -294.3282 | 1.5491 |
| 2 | v2_frozen | 10.0836 | 14.8723 | 10.8232 | -933.0000 | 4576.6305 | 6.9450 |
| 3 | seasonal_naive | 10.4744 | 16.5840 | 1.3425 | 459.0000 | 0.0000 | 2.4383 |
| 3 | weekday_mean4 | 8.2533 | 13.1337 | -2.6880 | 459.0000 | -1378.0000 | 2.3947 |
| 3 | random_forest | 10.1843 | 15.0600 | 10.1001 | 459.0000 | 2994.1124 | 7.3009 |
| 3 | direct_poisson | 9.0630 | 14.1025 | -6.6540 | 459.0000 | -2733.9501 | 4.5762 |
| 3 | v2_frozen | 10.1843 | 15.0600 | 10.1001 | 459.0000 | 2994.1124 | 7.3009 |

### CA_1 / legacy

| Nhóm | Mô hình | MAE | RMSE | Bias % | B_SN | Δ | nRMSE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | seasonal_naive | 8.5346 | 14.1998 | -1.9982 | -2474.0000 | 0.0000 | 4.0447 |
| all | weekday_mean4 | 7.7711 | 13.0600 | -2.3713 | -2474.0000 | -462.0000 | 4.0105 |
| all | random_forest | 7.5205 | 11.5304 | 4.9567 | -2474.0000 | 8611.0636 | 4.1161 |
| all | direct_poisson | 8.1469 | 13.5172 | -3.5560 | -2474.0000 | -1928.7964 | 3.9628 |
| all | v2_frozen | 7.5205 | 11.5304 | 4.9567 | -2474.0000 | 8611.0636 | 4.1161 |
| 0 | seasonal_naive | 8.3424 | 14.0838 | -3.0163 | -1147.0000 | 0.0000 | 6.0895 |
| 0 | weekday_mean4 | 7.9339 | 13.8926 | -0.4208 | -1147.0000 | 987.0000 | 6.0721 |
| 0 | random_forest | 7.6069 | 11.4782 | 6.1602 | -1147.0000 | 3489.5329 | 5.6181 |
| 0 | direct_poisson | 8.4919 | 14.5836 | -3.2305 | -1147.0000 | -81.4788 | 5.9794 |
| 0 | v2_frozen | 7.6069 | 11.4782 | 6.1602 | -1147.0000 | 3489.5329 | 5.6181 |
| 1 | seasonal_naive | 8.2196 | 13.5675 | -2.2348 | -633.0000 | 0.0000 | 2.7852 |
| 1 | weekday_mean4 | 8.1283 | 13.2538 | -3.0786 | -633.0000 | -239.0000 | 2.7381 |
| 1 | random_forest | 7.1728 | 10.8986 | 5.0470 | -633.0000 | 2062.5680 | 3.0716 |
| 1 | direct_poisson | 8.3280 | 13.5613 | -3.5765 | -633.0000 | -380.0434 | 2.9626 |
| 1 | v2_frozen | 7.1728 | 10.8986 | 5.0470 | -633.0000 | 2062.5680 | 3.0716 |
| 2 | seasonal_naive | 8.3143 | 13.4225 | -3.7105 | -1056.0000 | 0.0000 | 2.2704 |
| 2 | weekday_mean4 | 7.7113 | 12.5408 | -2.5299 | -1056.0000 | 336.0000 | 2.1997 |
| 2 | random_forest | 7.5270 | 11.6326 | 3.3029 | -1056.0000 | 1995.9949 | 3.0617 |
| 2 | direct_poisson | 7.9558 | 13.1979 | -2.2598 | -1056.0000 | 412.8519 | 2.1488 |
| 2 | v2_frozen | 7.5270 | 11.6326 | 3.3029 | -1056.0000 | 1995.9949 | 3.0617 |
| 3 | seasonal_naive | 9.3262 | 15.6538 | 1.2482 | 362.0000 | 0.0000 | 2.9217 |
| 3 | weekday_mean4 | 7.2565 | 12.1997 | -4.0825 | 362.0000 | -1546.0000 | 2.8641 |
| 3 | random_forest | 7.7465 | 12.0968 | 4.9133 | 362.0000 | 1062.9678 | 3.5193 |
| 3 | direct_poisson | 7.6968 | 12.2514 | -5.2346 | 362.0000 | -1880.1261 | 2.6426 |
| 3 | v2_frozen | 7.7465 | 12.0968 | 4.9133 | 362.0000 | 1062.9678 | 3.5193 |

### CA_2 / recent

| Nhóm | Mô hình | MAE | RMSE | Bias % | B_SN | Δ | nRMSE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | seasonal_naive | 8.0676 | 11.8090 | 1.7922 | 2284.0000 | 0.0000 | 3.6564 |
| all | weekday_mean4 | 7.4472 | 10.8780 | 3.9642 | 2284.0000 | 2768.0000 | 3.6544 |
| all | random_forest | 7.3703 | 10.0665 | 10.1584 | 2284.0000 | 10661.8061 | 3.6909 |
| all | direct_poisson | 7.8223 | 11.2947 | 0.2281 | 2284.0000 | -1993.2814 | 3.1253 |
| all | v2_frozen | 7.3703 | 10.0665 | 10.1584 | 2284.0000 | 10661.8061 | 3.6909 |
| 0 | seasonal_naive | 8.2228 | 12.0970 | 3.7098 | 1451.0000 | 0.0000 | 5.3555 |
| 0 | weekday_mean4 | 7.7049 | 11.5157 | 5.4227 | 1451.0000 | 670.0000 | 5.3474 |
| 0 | random_forest | 7.5572 | 10.4304 | 10.7956 | 1451.0000 | 2771.5022 | 4.5560 |
| 0 | direct_poisson | 8.4053 | 12.1439 | 5.5464 | 1451.0000 | 718.3663 | 4.2362 |
| 0 | v2_frozen | 7.5572 | 10.4304 | 10.7956 | 1451.0000 | 2771.5022 | 4.5560 |
| 1 | seasonal_naive | 7.2363 | 10.5708 | -3.5708 | -1061.0000 | 0.0000 | 1.5131 |
| 1 | weekday_mean4 | 7.6119 | 10.9342 | 3.5641 | -1061.0000 | 2120.0000 | 1.6412 |
| 1 | random_forest | 7.0932 | 9.6898 | 6.6837 | -1061.0000 | 3046.9140 | 2.8321 |
| 1 | direct_poisson | 7.6896 | 11.2338 | -2.5993 | -1061.0000 | 288.6683 | 1.6319 |
| 1 | v2_frozen | 7.0932 | 9.6898 | 6.6837 | -1061.0000 | 3046.9140 | 2.8321 |
| 2 | seasonal_naive | 7.9952 | 11.7040 | 4.0146 | 1186.0000 | 0.0000 | 2.2246 |
| 2 | weekday_mean4 | 7.3357 | 10.4810 | 3.2801 | 1186.0000 | -217.0000 | 2.2035 |
| 2 | random_forest | 7.4316 | 10.1037 | 10.4885 | 1186.0000 | 1912.5031 | 2.8663 |
| 2 | direct_poisson | 7.7515 | 11.0969 | -1.5420 | 1186.0000 | -1641.5334 | 2.2225 |
| 2 | v2_frozen | 7.4316 | 10.1037 | 10.4885 | 1186.0000 | 1912.5031 | 2.8663 |
| 3 | seasonal_naive | 8.7643 | 12.6669 | 2.4353 | 708.0000 | 0.0000 | 3.5289 |
| 3 | weekday_mean4 | 7.0503 | 10.3218 | 3.1061 | 708.0000 | 195.0000 | 3.4921 |
| 3 | random_forest | 7.3369 | 9.9018 | 12.5168 | 708.0000 | 2930.8869 | 3.8614 |
| 3 | direct_poisson | 7.2487 | 10.3362 | -2.2385 | 708.0000 | -1358.7826 | 3.2856 |
| 3 | v2_frozen | 7.3369 | 9.9018 | 12.5168 | 708.0000 | 2930.8869 | 3.8614 |

### CA_2 / legacy

| Nhóm | Mô hình | MAE | RMSE | Bias % | B_SN | Δ | nRMSE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all | seasonal_naive | 8.3922 | 12.4168 | -4.4572 | -5997.0000 | 0.0000 | 6.4826 |
| all | weekday_mean4 | 7.8872 | 11.8230 | -6.5450 | -5997.0000 | -2809.0000 | 6.4922 |
| all | random_forest | 7.2558 | 10.0897 | 7.0076 | -5997.0000 | 15425.4042 | 5.0942 |
| all | direct_poisson | 10.2762 | 20.8226 | 0.6891 | -5997.0000 | 6924.1133 | 6.4215 |
| all | v2_frozen | 7.2558 | 10.0897 | 7.0076 | -5997.0000 | 15425.4042 | 5.0942 |
| 0 | seasonal_naive | 7.9656 | 11.8301 | -1.0254 | -415.0000 | 0.0000 | 6.2229 |
| 0 | weekday_mean4 | 7.8929 | 12.0984 | -2.9231 | -415.0000 | -768.0000 | 6.2366 |
| 0 | random_forest | 7.3897 | 10.2353 | 10.8516 | -415.0000 | 4806.7620 | 5.1296 |
| 0 | direct_poisson | 8.3757 | 12.8356 | -8.0897 | -415.0000 | -2858.9690 | 6.0538 |
| 0 | v2_frozen | 7.3897 | 10.2353 | 10.8516 | -415.0000 | 4806.7620 | 5.1296 |
| 1 | seasonal_naive | 7.5988 | 11.2170 | -9.3452 | -2886.0000 | 0.0000 | 5.5694 |
| 1 | weekday_mean4 | 7.9926 | 11.8500 | -8.1277 | -2886.0000 | 376.0000 | 5.6494 |
| 1 | random_forest | 6.7957 | 9.6222 | 2.9838 | -2886.0000 | 3807.4593 | 4.7854 |
| 1 | direct_poisson | 8.1503 | 12.1717 | -17.5859 | -2886.0000 | -2544.8740 | 5.6225 |
| 1 | v2_frozen | 6.7957 | 9.6222 | 2.9838 | -2886.0000 | 3807.4593 | 4.7854 |
| 2 | seasonal_naive | 8.6304 | 12.8054 | -0.2888 | -91.0000 | 0.0000 | 6.2573 |
| 2 | weekday_mean4 | 7.7125 | 11.4068 | -8.2405 | -91.0000 | -2506.0000 | 6.2379 |
| 2 | random_forest | 7.4979 | 10.2676 | 8.1028 | -91.0000 | 2644.6093 | 4.7521 |
| 2 | direct_poisson | 11.8187 | 23.0871 | 11.0704 | -91.0000 | 3579.8375 | 6.2529 |
| 2 | v2_frozen | 7.4979 | 10.2676 | 8.1028 | -91.0000 | 2644.6093 | 4.7521 |
| 3 | seasonal_naive | 9.5161 | 13.8454 | -8.2236 | -2605.0000 | 0.0000 | 7.7653 |
| 3 | weekday_mean4 | 7.9488 | 11.8332 | -7.9427 | -2605.0000 | 89.0000 | 7.7431 |
| 3 | random_forest | 7.2954 | 10.1703 | 4.9297 | -2605.0000 | 4166.5737 | 5.6431 |
| 3 | direct_poisson | 13.3936 | 31.2732 | 19.3930 | -2605.0000 | 8748.1188 | 7.6884 |
| 3 | v2_frozen | 7.2954 | 10.1703 | 4.9297 | -2605.0000 | 4166.5737 | 5.6431 |

## Bằng chứng chi tiết và tái lập

- [V2_METRICS.csv](V2_METRICS.csv): metric trung bình ba seed theo store/panel/split/nhóm.
- [V2_SEED_METRICS.csv](V2_SEED_METRICS.csv): metric của từng seed (bao gồm normalized RMSE).
- [V2_ORIGIN_METRICS.csv](V2_ORIGIN_METRICS.csv): từng origin, seed, model; hỗ trợ đối chiếu cổng và trung vị.
- [V2_BIAS_BY_H.csv](V2_BIAS_BY_H.csv): đủ h=1..28, từng nhóm/gộp, store/panel/seed/model; bias_units là tổng có dấu, bias_mean chia cho số origin ×20, không phải bias lũy kế.
- [V2_FROZEN.json](V2_FROZEN.json): quyết định, k nếu được phép, cấu hình, hashes code và validation trước test.
- [V2_PANELS.json](V2_PANELS.json): danh sách rank/train_units/recent_units/last28_units của hai panel hai store.

Lệnh đã dùng theo thứ tự; test chỉ gọi một lần cuối, không chạy lại để chọn cấu hình:

```powershell
.\.venv\Scripts\python.exe scripts/run_forecast_v2.py prepare
.\.venv\Scripts\python.exe scripts/run_forecast_v2.py validate --store CA_1
.\.venv\Scripts\python.exe scripts/run_forecast_v2.py freeze
.\.venv\Scripts\python.exe scripts/run_forecast_v2.py validate --store CA_2
.\.venv\Scripts\python.exe scripts/run_forecast_v2.py test
.\.venv\Scripts\python.exe scripts/report_forecast_v2.py
```

Không tự chạy lại trên output cũ: prepare/validation/freeze/test có guard tránh thay evidence; test_started.json được tạo trước đọc nhãn, test_complete.json chỉ có khi hoàn tất. Các forecast test được tạo từ history trước khi mở nhãn test. CA_2 validation chạy sau freeze, không dùng chỉnh quyết định. Thời điểm/hashes được lưu trong manifest và marker ở outputs. Dữ liệu/model lớn không đưa vào Git; cần nguồn Parquet và môi trường theo README để tái lập vào output mới, nhưng lượt CA_2 test sau đó không còn là test tươi.

Giới hạn: không kết luận nguyên nhân bán 0 hoặc suy bias giảm là sửa được nhu cầu tiềm ẩn. Đổi panel sau chẩn đoán là thiết kế đã xem trước. Chênh metric giữa panel chịu ảnh hưởng quy mô/thành phần; so thuật toán phải dùng cùng panel. Không phát biểu nhân quả từ các đối chứng này.

## Kiểm tra bàn giao

Bộ `python -m unittest discover -s tests -v` hiện có 24 test, gồm leakage mutation 1e9, đối chiếu selector Spark, nhãn train direct, cổng/nhóm, guard freeze/test một lần, schema và metric báo cáo, cùng các test dashboard/V1 cũ. Chạy trước và sau từng commit; không commit khi test đỏ. [V2_AUDIT.json](V2_AUDIT.json) lưu mốc freeze/test và kết quả đối chiếu 10080 dòng bias horizon với 360 seed summaries; cả 780 dòng metric từng origin được lưu để tính lại cổng. Artifact dashboard gốc được so hash trước/sau và không thay đổi. Bước 2 không chạy do cổng; các k=1 trong manifest là giá trị identity mặc định không fit/không áp dụng.
