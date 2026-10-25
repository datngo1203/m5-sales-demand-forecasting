# Hướng dẫn trình bày demo M5

## Giới thiệu

Hệ thống dùng Spark để tổng hợp dữ liệu bán hàng lớn, rồi dự báo 28 ngày cho 20 sản phẩm CA_1.
Phần thống kê dùng toàn bộ dữ liệu; phần mô hình dùng panel nhỏ sau khi Spark chọn.
Đây là backtest có thực tế để đối chiếu, chưa phải chức năng dự báo kỳ tiếp theo hoặc đặt hàng.

## Trình tự xem

1. Mở dashboard theo README. Chọn cửa hàng, nhóm hàng và khoảng ngày để xem lượng bán và doanh thu.
2. Giải thích doanh thu chỉ tính phần biết giá; hiển thị cả bao phủ giá.
3. Chọn CA_1 và một sản phẩm, xem lịch sử rồi so sánh các đường dự báo.
4. `actual` là thực tế, `seasonal_naive` là lặp tuần trước, `random_forest` là RF;
   `selected_forecast` là cách được chọn cho sản phẩm từ validation.
5. Đọc MAE/RMSE cùng bias_units/bias_pct. Bias dương nghĩa là dự báo dư, âm là thiếu.
6. Chuyển validation để minh họa, nhắc rằng đây chỉ là cửa sổ cuối trong bốn cửa sổ đã dùng lựa chọn.
7. Chọn cửa hàng khác để xem thống kê; hiện các cửa hàng đó chưa có panel dự báo.

## Giải thích cách xử lý sai lệch

Đã thử lịch sử toàn bộ, 365 và 180 ngày; thêm thông tin ngày bán 0 và mức thay đổi gần đây.
Mỗi cấu hình được kiểm tra trên bốn giai đoạn 28 ngày; thử cả đệ quy và dự báo trực tiếp.
Phương án được chọn là đệ quy. Sau khi chọn RF chung,
từng sản phẩm dùng RF hoặc baseline theo sai số validation. Không dùng test để chọn.
Danh sách sản phẩm được chốt trước validation đầu tiên để tránh nhìn trước dữ liệu.
Mỗi lần vẫn dự báo trước đủ 28 ngày, không cập nhật thực tế vào giữa cửa sổ.

## Số liệu để trình bày

Trên cùng panel, RF cũ: MAE 7,53, RMSE 10,69, bias 20,10%.
Cách chọn theo sản phẩm: MAE 7,21, RMSE 11,13, bias 17,24%.
Đọc forecast_report.json và metrics.csv nếu chạy lại, không dùng các số này cho một lần chạy khác.
MAE giảm không có nghĩa là phần trăm chính xác tăng tương ứng.

## Giới hạn cần nói rõ

Test cũ đã được xem khi tìm lỗi nên kết quả cải tiến là đối chiếu hồi cứu.
Validation là dữ liệu phát triển, không phải chứng cứ độc lập.
Không kết luận mọi sản phẩm đều tốt hơn; chưa biết ngày bán 0 là hết hàng hay không có nhu cầu.
Spark mới chạy local, HDFS chưa kiểm chứng; mô hình không huấn luyện phân tán bằng Spark MLlib.
File Word giải thích dễ đọc nằm trong docs/Giai_thich_chuc_nang_va_quy_trinh_M5.docx.
