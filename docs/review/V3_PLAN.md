# V3 — đăng ký trước khi chạy kiểm thử/thí nghiệm

Nhánh `forecast-v2`, nền `dd8b678`. Bốn pha, mỗi pha một commit; chạy toàn bộ unittest trước và sau mỗi commit, không push/merge. Không thêm dependency. CA_1 và CA_2, kể cả test, đều đã xem; không gọi chúng là test tươi. Tái dùng nguyên dự báo V2, không fit lại RF/direct ở hai store này.

## Cách xử lý điểm mơ hồ (chọn thận trọng)

- Panel chính `recent`, phụ `legacy`, cùng luật và ngày chốt 06/12/2015 của V2; báo cáo cả hai. Các so sánh thuật toán luôn cùng panel.
- Ba cửa hàng mới ưu tiên CA_3, TX_1, WI_1. Kiểm tra tồn tại bằng khóa store, không xem demand test. Nếu thiếu, lấy tên store chưa dùng theo thứ tự chữ cái, ghi manifest trước validation. Không đổi cửa hàng theo kết quả.
- Chẩn đoán tổng tuần quanh 27/03/2016 dùng **cùng 20 item của CA_1 legacy** tại mọi store để so sánh cùng giỏ sản phẩm. Đây không phải tổng toàn cửa hàng hoặc panel riêng của mỗi store. In đủ 8 tuần ở CA_1/CA_2; với store chưa dùng, chỉ in bốn tuần trước origin trong Pha 1, **trì hoãn bốn tuần sau đến sau lượt test cuối**. Nếu đọc/in tổng tuần test của store mới trước đó thì test không còn tươi. Phần trì hoãn sẽ được bổ sung vào cùng mục Bổ sung 3 sau test, không dùng chọn ứng viên.
- Chẩn đoán nRMSE: xếp hạng bằng đóng góp tổng squared normalized error (NSSE), mẫu số max(mean_28 tại từng origin,1), cộng 13 origin và ba seed. NSSE cộng được, nRMSE không cộng trực tiếp. Báo cáo recent validation và test đã xem riêng cho CA_1/CA_2.
- “last28_units thấp” trong chẩn đoán = tổng 28 ngày trước **từng origin** ≤28 (trung bình ≤1/ngày), tách thêm đúng 0. Đây chỉ là ngưỡng mô tả, không thêm feature hoặc rule dự báo, không tuning.
- Tỷ trọng bias top 3 là phần của bias tổng có dấu; nêu cả bù trừ và tỷ trọng trong tổng phần dư dương để không hiểu nhầm khi mẫu số nhỏ.

## Ứng viên và điểm chọn (chỉ validation CA_1/CA_2)

RF hiện hành: V2 window180/depth12/leaf5/100 cây, seed42/43/44. Không thử direct lại. Các ứng viên: `random_forest`, `weekday_mean4`, `rf_calibrated` = RF×k, `blend` = 0.5 RF + 0.5 weekday_mean4. Blend 0.5 cố định.

Từng store/panel/seed: k = tổng actual validation / tổng dự báo RF validation, qua 13 origin đóng băng. Không clamp, không fit từ test. Nếu tổng dự báo=0 và actual>0, candidate calibrated không hợp lệ; nếu cả hai=0 dùng k=1. K được ước lượng và đánh giá trên cùng validation nên có lạc quan in-sample; báo cáo rõ. Cửa hàng mới **tự fit k từ validation của chính nó**, không mang giá trị k CA_1/CA_2 sang.

13 origin và 4 nhóm mod4 giữ nguyên V2. Trung bình metric ba seed tại mỗi origin; trung vị origin trong từng nhóm; trung vị bốn nhóm = điểm MAE của một bộ. Điểm chung = trung bình bốn tỷ số điểm MAE candidate / điểm MAE RF, bốn bộ = CA_1/CA_2 × recent/legacy. Nếu RF score=0, tỷ số là 1 khi candidate cũng 0, không hợp lệ nếu candidate>0. Điều kiện đủ: trung bình |bias_pct| qua bốn bộ không lớn hơn RF; bias_pct của một bộ = trung bình metric bias_pct ba seed trên toàn 13 origin, sau đó lấy trị tuyệt đối. RF luôn là lựa chọn dự phòng. Hòa số học trong 1e-12: weekday_mean4 < blend < rf_calibrated < random_forest.

Nhóm chồng lấp nhau, 13 origin không độc lập. Không dùng CI giả định độc lập, không coi ba seed là ba test độc lập. Báo cáo điểm chọn và metric gộp riêng. Đóng băng tên ứng viên, thuật toán, feature, 0.5, luật k, panel, origin, seeds và cổng tích hợp trước validation/test cửa hàng mới; không đóng băng các k cụ thể.

## Test tươi và cổng tích hợp

- Chuẩn bị và train **chỉ RF** ở ba store mới, hai panel, cùng 13 origin. Baseline tính từ lịch sử, không train. Cache validation và mô hình RF ở origin test; không train lại nếu cache đã có và hash/config khớp. Chỉ đọc demand ≤27/03/2016 cho tới lượt test.
- Tạo dự báo test cho mọi ứng viên từ history trước khi mở nhãn, nhưng chỉ đánh giá/báo cáo ứng viên đã chọn cùng RF, weekday_mean4 và seasonal_naive. Mỗi store/panel dùng k tự fit từ validation của nó nếu cần. Guard `test_started` tạo độc quyền trước mở nhãn; `test_complete` chỉ ghi khi hoàn tất cả ba store. Không chạy test lại, không đổi luật sau xem test.
- Metrics: MAE, RMSE, bias_pct, normalized RMSE như V2, B_SN và Δ=model bias−seasonal_naive bias; trung bình metric ba seed, không metric của ensemble. Lưu từng seed và bias h=1..28 để đối chiếu, không tìm cấu hình bằng test.
- **Cổng tích hợp đã định trước:** một store đạt khi ứng viên đã chọn có MAE ≤ RF **và |bias_pct| ≤ |bias_pct RF| trên cả hai panel** (không gộp để che một panel kém). Cần ít nhất 2/3 store đạt. Đây là phép accept/reject thủ tục đã chọn, không lựa chọn lại ứng viên/siêu tham số từ test. Không xét ứng viên khác nếu ứng viên chọn trượt. Báo cáo cả trường hợp kém hơn.
- Qua cổng: pipeline V2 làm mặc định với candidate và thủ tục k đã chọn; V1 chạy được qua `--v1`/`-V1`. Không qua: giữ V1 mặc định, ghi rõ lý do, chỉ có cờ opt-in V2. Không train lại hay đánh giá lại test khi tích hợp.
- Hợp đồng dashboard giữ nguyên tên file/cột; default output chỉ seed42 để không trùng pivot, bằng chứng thí nghiệm vẫn ba seed/hai panel riêng. Không gắn nhãn weekday/blend/calibrated thành RF: dashboard dùng metadata phiên bản/tên ứng viên mới và diễn giải đúng; sửa tests nếu cần. Lịch sử/metrics/predictions full 28 ngày, validation hiển thị origin cuối như V1. V1 archive bất biến và gọi được trực tiếp.

## Kiểm tra và tái lập

Viết kế hoạch này trước **bất kỳ test nào** của V3, gồm unittest trước commit Pha 1. Tests mới: mutation demand sau origin→1e9 không đổi panel/features/forecast; k chỉ đọc validation; cổng/selection tie và absolute bias; guard test một lần; schema/dashboard đa mô hình không diễn giải sai; cached RF không fit lại khi tích hợp. Không sửa thiết kế sau khi biết test mới; sửa lỗi vận hành nếu có phải ghi audit, không dùng để tuning. Mỗi pha một commit; kết quả unittest và hashes/markers lưu trong outputs và báo cáo bàn giao.
