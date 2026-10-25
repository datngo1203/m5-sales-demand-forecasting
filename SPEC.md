# Spec source code đồ án M5

Ngày 25/10/2026 — mục tiêu hoàn thành source trước khoảng 17:00, giờ Việt Nam.

## Bài toán và phạm vi
Tiếp nối phần Data Engineering của thành viên còn lại để hoàn thiện đề tài số 12: phân tích dữ liệu bán hàng và dự báo nhu cầu sản phẩm phục vụ tham khảo quản lý kho. Đối tượng sử dụng là người xem demo và giảng viên. Đầu ra dự báo là số lượng sản phẩm bán theo ngày, không phải nhu cầu tiềm ẩn khi hết hàng.

## Yêu cầu lấy từ kế hoạch môn học
Dùng công nghệ Big Data; đề tài 12 gợi ý HDFS để lưu trữ, Spark để làm sạch/tổng hợp, mô hình hồi quy hoặc chuỗi thời gian và trực quan hóa doanh thu cùng dự báo. Có quy trình chạy, đánh giá, giải thích kết quả và giới hạn. Source, Word và PPT là đầu ra của cả nhóm; lượt công việc này chỉ làm source và hướng dẫn chạy. Mô hình và trực quan hóa mỗi tiêu chí 2,5/10 điểm.

## Đầu vào và hiện trạng
Giữ nguyên mã bàn giao `GuiDat/code/01` đến `10` cùng reports. Dùng Parquet trong `GuiDat/data/processed_m5` làm đầu vào có sẵn. README mô tả forecasting_features trên HDFS của thành viên khác, nhưng bộ đó không có trong file nén; không giả định truy cập được HDFS ấy. Số dòng, schema và chất lượng sẽ kiểm tra từ dữ liệu thực tế, không lấy chữ PASS trong report làm bằng chứng đã chạy trên máy này.

## Phần source bổ sung và đầu ra
1. Kiểm tra dữ liệu, môi trường và xuất báo cáo kiểm tra đầu vào.
2. Spark tổng hợp doanh số, số lượng bán theo ngày, nhóm sản phẩm và cửa hàng; hỗ trợ đường dẫn Parquet local hoặc HDFS. Đường dẫn HDFS phải được kiểm thử riêng khi có dịch vụ.
3. Demo dự báo số lượng bán cho 20 cặp sản phẩm–cửa hàng thuộc một cửa hàng. Chọn các chuỗi bằng dữ liệu tập huấn luyện; lưu danh sách lựa chọn. So sánh một dự báo đơn giản lặp tuần trước với một mô hình hồi quy Random Forest dùng lịch sử bán hàng và lịch ngày.
4. Tách huấn luyện/validation/test theo ngày, hai khoảng cuối mỗi khoảng 28 ngày. Đánh giá MAE, RMSE; xuất dự báo, số thực tế và bảng so sánh. Dự báo nhiều ngày chỉ dùng lịch sử đã biết và dự báo trước đó, không dùng lượng bán thật trong tương lai để tạo đặc trưng.
5. Demo trực quan có lựa chọn sản phẩm/cửa hàng, biểu đồ lịch sử, doanh thu, thực tế so với dự báo và bảng sai số. Xuất dữ liệu tổng hợp nhỏ để giao diện không đọc toàn bộ dữ liệu lớn.
6. Có lệnh chạy, phiên bản môi trường, kiểm tra nhỏ cho logic mới và thông tin nguồn dữ liệu bàn giao.

## Giả định để tiến hành ngay
Đề tài đã được nhóm/giảng viên chấp thuận. Ưu tiên demo đúng trên một phạm vi dự báo nhỏ; Spark vẫn đọc và tổng hợp toàn bộ đầu vào. Không đặt ngưỡng chính xác tùy ý hoặc cam kết mô hình học máy luôn thắng baseline. Doanh thu được tính từ demand × sell_price; công bố mức bao phủ giá, không thay giá thiếu thành 0 hay tự điền bằng giá tương lai. Không làm Word, PPT, triển khai cloud hoặc giao diện quản trị trong phạm vi này.

## Tiêu chí hoàn thành
Chạy được từ hướng dẫn trên môi trường đã ghi; tạo dữ liệu tổng hợp, dự báo 28 ngày, bảng MAE/RMSE của hai mô hình và demo biểu đồ. Có kiểm tra tránh dùng dữ liệu tương lai; ghi rõ local/HDFS đã kiểm chứng ở đâu, phạm vi dữ liệu và thời gian chạy. Phần chưa chạy thành công không được đánh dấu hoàn thành.

Đây là spec v1 dựa trên yêu cầu cho phép tự nêu giả định và bắt đầu bước đầu tiên; các giả định vẫn có thể được người dùng điều chỉnh.
