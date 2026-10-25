# Nguồn dữ liệu và phạm vi tái lập

Đầu vào trực tiếp là bộ Parquet M5 do thành viên cùng nhóm bàn giao tại
`GuiDat/data/processed_m5/`. Tài liệu bàn giao là
`GuiDat/README_M5_Data_Engineering.md`; mã gốc nằm trong `GuiDat/code/01` đến `10`.
Các file này được giữ nguyên trong phần source bổ sung.

Theo `GuiDat/code/04_spark_preprocessing.py`, dữ liệu được tạo từ
`sales_train_validation.csv`, `calendar.csv`, `sell_prices.csv`: chuyển lượng bán
từ cột ngày sang dòng rồi kết hợp lịch và giá. Đường dẫn máy người bàn giao
`D:\BigData\DoAn\data` chỉ là thông tin nguồn trong mã, không phải đầu vào của
lệnh chạy hiện tại. Bộ CSV gốc, URL tải và thông tin phiên bản tải không có
trong gói dữ liệu đang dùng; chưa đối chiếu Parquet với bản phát hành gốc.
Không coi kết quả kiểm tra trong reports bàn giao là bằng chứng chạy trên máy này.

Bản local được kiểm tra ngày 25/10/2026 có 32 file Parquet, `_SUCCESS`,
318.838.151 byte, 58.327.370 dòng và 22 cột; ngày bán từ 29/01/2011 đến
24/04/2016 theo tổng hợp Spark. Danh sách cột và kiểu thực tế nằm
trong `outputs/input_inventory.json`.

Chạy `code/11_inspect_input.py` tạo lại inventory có tên, kích thước và SHA-256
từng file. So sánh trường `files` giữa hai inventory để nhận biết bản dữ liệu
khác nhau; SHA-256 xác định nội dung file, không chứng minh xuất xứ hoặc chất
lượng dữ liệu. Script đọc toàn bộ byte theo luồng để băm nhưng chỉ đọc footer
và 5 dòng mẫu để kiểm tra cấu trúc, không nạp toàn bộ dữ liệu vào RAM.
Không thay dữ liệu trong lúc pipeline đang chạy.

`code/12_spark_analysis.py` tổng hợp toàn bộ dữ liệu; `code/13_forecasting.py`
chọn 20 sản phẩm của CA_1 bằng lượng bán trước mốc validation đầu tiên, giữ
panel cố định qua bốn cửa sổ validation 28 ngày và một cửa sổ test 28 ngày.
Thử lịch sử train toàn bộ, 365 và 180 ngày; chọn cấu hình RF và chọn giữa RF
với baseline bằng validation. Dashboard dùng CSV nhỏ đã xuất. Doanh thu là
lượng bán × giá, giữ riêng mức bao phủ giá; không tự điền giá thiếu.

Để tái lập sau khi clone, nhận đúng bộ Parquet từ thành viên bàn giao và đặt
vào đường dẫn trên, chuẩn bị Python/JDK theo README rồi chạy `run_pipeline.ps1`.
Git không chứa dữ liệu, môi trường hay kết quả. Thư mục `forecasting_features`
và HDFS được nhắc trong bàn giao không có sẵn để kiểm chứng; pipeline local
không phụ thuộc chúng. Chưa kiểm chứng HDFS. Tài liệu giải thích hiện có trong
`docs/Giai_thich_chuc_nang_va_quy_trinh_M5.docx`; chưa làm PPT.
