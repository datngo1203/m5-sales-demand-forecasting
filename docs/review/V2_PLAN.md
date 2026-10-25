# Kế hoạch V2 — đóng băng trước thí nghiệm

Nhánh `forecast-v2`, gốc `f3784b6`. `code/13_forecasting_v1.py` là bản sao nguyên byte của forecasting cũ. Pipeline/dashboard mặc định và các file `outputs/forecast` hiện có giữ nguyên; V2 là lệnh thí nghiệm riêng, không tự đổi mặc định khi cổng đạt. Không thêm dependency ngoài requirements-forecast.txt.

## Nguồn gốc thiết kế và panel

Tiêu chí mới được gợi ý từ chẩn đoán hồi cứu trên sản phẩm có test CA_1 đã bị xem: đây là thiết kế **đã xem trước**, không phải thiết kế độc lập với test lịch sử. CA_1 test chỉ là đối chiếu hồi cứu. CA_2 với toàn bộ cấu hình/quy tắc đóng băng từ CA_1 là test tươi duy nhất trong công việc này; không dùng CA_2 validation hoặc test để thay đổi quyết định.

Ngày chốt: hết 06/12/2015, trước origin validation đầu. Panel chính `recent`: xếp hạng giảm dần theo tổng demand 182 ngày 08/06–06/12/2015 (26 tuần), loại sản phẩm có tổng 28 ngày 09/11–06/12/2015 bằng 0, item_id tăng dần phá hòa, lấy 20. Panel phụ `legacy`: 20 sản phẩm có tổng bán toàn lịch sử đến hết 06/12/2015 cao nhất, item_id phá hòa; ở CA_1 phải khớp panel cũ. CA_2 áp dụng cùng tiêu chí ở cùng ngày, không lấy danh sách item CA_1. Giữ hai panel riêng, không coi khác biệt thành phần là cải thiện thuật toán trên cùng sản phẩm.

## Validation được người dùng chốt

13 origin: 06/12/2015, mỗi 7 ngày, đến 28/02/2016. Mỗi origin dự báo 28 ngày tiếp theo; cửa sổ cuối kết thúc 27/03/2016, không nhãn nào chạm 28/03/2016. Nhóm = chỉ số origin mod 4 (0..3); trong nhóm nhãn không chồng nhau. Các nhóm chồng lấp nhau, **13 origin không phải 13 mẫu độc lập**. Báo cáo từng origin, từng nhóm và phần gộp; không tính CI coi origin độc lập. Không cần CI cho thí nghiệm này; nếu bổ sung phải bootstrap theo khối.

Điểm chọn: tính MAE trung bình qua 3 seed cho từng origin, lấy trung vị qua origin trong từng nhóm, rồi lấy trung vị bốn nhóm. Báo cáo cả metric gộp các dự báo, nhưng chúng đếm lặp nhãn giữa các nhóm và không dùng thay cho điểm chọn. RMSE chuẩn hóa dùng RMSE / max(mean của 28 ngày trước origin, 1) cho mỗi sản phẩm, gộp căn trung bình bình phương sai số đã chuẩn hóa. Scale luôn chỉ từ quá khứ. Báo cáo kết quả từng seed và trung bình metric 3 seed, không gọi dự báo ensemble là trung bình metric.

## Bước 1: đối chứng đóng băng, không tìm siêu tham số

- `seasonal_naive`: lặp 7 ngày cuối như V1.
- `weekday_mean4`: trung bình 4 quan sát cùng thứ trong 28 ngày đã biết trước origin, lặp theo thứ ngày đích.
- `random_forest`: RF đệ quy hiện tại, window_days=180, 100 cây, max_depth=12, min_samples_leaf=5, n_jobs=2; 14 đặc trưng hiện tại + mã one-hot sản phẩm. Đây là đối chứng **V1 RF hiện hành** đã chọn trước trong repo, không chạy lại tìm 7 cấu hình V1. Không trộn với RF cũ hơn trong `reference_test`.
- `direct_poisson`: HistGradientBoostingRegressor(loss='poisson', learning_rate=0.1, max_iter=100, max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=1, early_stopping=False). Không tuning. Mã sản phẩm là categorical. Mỗi dòng (item, origin, h=1..28); y chuẩn hóa bằng max(mean_28 tại origin,1), dự báo nhân lại scale đó. Đặc trưng: mean 4 tuần cùng thứ ngày đích, mean_28, tỷ lệ ngày 0 trong 28 ngày, thứ/tháng ngày đích, h, mã sản phẩm. Không dùng giá hoặc feature nguồn.
- Dữ liệu train RF: target của 180 ngày gần origin như hiện tại. Direct: các anchor mỗi 7 ngày trong 180 ngày gần origin; chỉ nhận anchor có toàn bộ 28 target ≤ origin. Mỗi anchor có features từ 28 ngày đến anchor; không teacher forcing trong 28 target. Không có train target sau origin đang dự báo. 180 ngày cố định để đối chiếu cửa sổ hiện hành, không chọn bằng test.
- Seeds cố định: 42,43,44 cho RF và direct; baseline lặp tương tự qua seed cho định dạng báo cáo. Giới hạn thread OpenMP=2 để tránh quá tải máy, không đổi thuật toán.

## Cổng quyết định — ghi trước khi chạy

Áp dụng riêng cho cả hai panel **CA_1**; chỉ mở Bước 2 khi **cả hai** qua:

1. Δ_direct < Δ_RF ở ít nhất ceil(2×13/3)=9 origin; Δ có dấu, bằng bias(model) − bias(seasonal_naive), dùng trung bình qua 3 seed. Đây không phải so |Δ|; giảm Δ có thể thành dự báo thiếu, vì thế cần công bố bias có dấu.
2. Điểm MAE direct (trung vị qua bốn nhóm như trên) ≤ 1.03 × điểm MAE RF.

Nếu một panel trượt: không thực hiện hiệu chỉnh, sparse fallback hay chọn direct; V2 giữ RF làm phương án đối chứng được giữ lại. Vẫn báo cáo raw direct và cả hai baseline, kể cả kết quả kém. Không dùng test để xét lại cổng. Không tự chuyển cấu hình mặc định dù qua cổng.

## Bước 2 chỉ khi cổng đạt

- Candidate k = tổng actual / tổng dự báo trên toàn bộ origin validation CA_1 đóng băng, một k cho mỗi panel và mỗi seed; không cắt/clamp k. Báo cáo direct raw và direct×k. Giá trị k CA_1 được mang nguyên sang panel cùng tên của CA_2; không refit bằng CA_2.
- Sparse fallback cố định: tổng demand 28 ngày trước/đến origin bằng 0 → dùng weekday_mean4. 28 là hằng số giao thức, không tuning trên test. Candidate raw+fallback và calibrated+fallback; fallback không nhân k để giữ đúng baseline quy định.
- Chọn trong bốn candidate direct (raw/calibrated × có/không fallback) bằng điểm MAE trung vị qua nhóm; hòa ưu tiên raw, rồi ít biến đổi hơn. Điểm hiệu chỉnh trên cùng validation ước lượng k là in-sample đối với k, phải ghi rõ lạc quan; không coi là validation độc lập của k. k được đóng băng trước test.
- Độ nhạy: fold bị gắn cờ nếu một sản phẩm thuộc top 10 của panel theo tổng bán 26 tuần trước ngày chốt có chuỗi demand=0 liên tiếp ≥14 ngày trong 28 ngày nhãn validation. Mốc top 10, 14 ngày được ghi cố định, không tối ưu bằng test. Báo cáo cả có/không các fold đó; cờ chỉ để phân tích, không mask train/eval, không gán nhãn hết hàng, không dùng sell_price. Không dùng lọc sensitivity để thay đổi cổng hoặc mô hình.

## Đóng băng và test một lần cuối

Các lệnh tách pha `prepare`, `validate`, `freeze`, `test`, `report`. Chuẩn bị panel chỉ đọc demand đến 06/12/2015; validation chỉ lấy panel demand đến 27/03/2016. Lệnh test là lần đầu thí nghiệm V2 đọc nhãn từ 28/03/2016. Sau validate CA_1 và xét cổng, lưu manifest quyết định + k + candidate + cấu hình và hash trước test. Chạy validation CA_2 để báo cáo bằng manifest đó, không chọn lại. Lượt test cuối cùng đánh giá đồng thời CA_1 và CA_2, hai panel, 3 seed và mọi đối chứng đóng băng; lưu dấu bắt đầu chống vô tình chạy lại. Nếu gặp lỗi chỉ sửa lỗi vận hành và ghi audit, không đổi thiết kế bằng nhãn vừa thấy.

Báo cáo MAE, RMSE, bias_pct, B_SN và Δ; bias theo h cho từng origin/nhóm/gộp; normalized RMSE; trung bình và metric từng seed. Bảng V1 RF hiện hành vs V2 cho CA_1/CA_2, legacy/recent, validation/test. Tách tác động panel, baseline, direct, hiệu chỉnh/fallback nếu được phép. Nhãn test không được chọn tham số/ngưỡng/đặc trưng, không thay quy tắc sau khi xem kết quả.

## Kiểm tra và commit

Mỗi thay đổi logic là một commit, chạy `.venv/Scripts/python.exe -m unittest discover -s tests -v` trước commit để không commit đỏ và sau mỗi commit. Bổ sung test đổi dữ liệu sau origin thành 1e9: panel, feature, train matrix và forecast không đổi; label train direct kết thúc ≤ origin. Kiểm tra nhóm nhãn không chồng, chặn test trước freeze/chạy lại, quyết định không phụ thuộc test, schema CSV/JSON dashboard vẫn giữ nguyên. Không commit dữ liệu thô hoặc model lớn; đưa số tổng hợp và manifest tái lập vào docs/review.
