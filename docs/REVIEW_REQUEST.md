# Nhờ review phần dự báo M5

Hệ thống dùng Spark tổng hợp khoảng 58 triệu dòng, rồi dùng scikit-learn dự báo
28 ngày cho 20 sản phẩm CA_1. Nhờ đọc source, tìm lỗi và đề xuất cách xử lý nhỏ gọn;
chưa sửa code hay train lại.

## Đã thử

- Bốn cửa sổ validation 28 ngày, chốt sản phẩm trước validation đầu tiên.
- RF dùng toàn bộ/365/180 ngày lịch sử, hai cấu hình cây; thêm đặc trưng ngày bán 0.
- Thử thêm RF dự báo trực tiếp 28 đầu ra. Chọn cấu hình bằng validation,
  rồi chọn baseline hoặc RF cho từng sản phẩm. Không chọn bằng test.
- Kết quả chọn RF đệ quy dùng 180 ngày, độ sâu 12, tối thiểu 5 mẫu mỗi lá.

## Vấn đề còn lại

So sánh trên cùng nhóm sản phẩm:

| Chỉ số test | RF cũ | Cách chọn theo sản phẩm |
|---|---:|---:|
| MAE | 7,5294 | 7,2092 |
| RMSE | 10,6884 | 11,1271 |
| Tổng dự báo dư | 20,10% | 17,24% |

MAE giảm nhưng lỗi lớn và dự báo dư vẫn đáng kể. Baseline chỉ dư 13,11%.
Một số sản phẩm giảm bán mạnh; dự báo đệ quy có thể tự khuếch đại sai lệch.
Chưa biết ngày bán 0 là hết hàng hay không có nhu cầu. Test cũ đã được xem khi
chẩn đoán, nên kết quả là đối chiếu hồi cứu, chưa chứng minh trên dữ liệu mới.

## Nhờ kiểm tra

1. Có rò rỉ dữ liệu hoặc sai cách tạo đặc trưng, nhãn 28 ngày, chia cửa sổ không?
2. Chọn baseline/RF theo sản phẩm có quá khớp validation không?
3. Vì sao MAE giảm nhưng RMSE tăng? Đặc trưng bán 0 có mất ý nghĩa khi dự báo đệ quy sinh số dương nhỏ không?
4. Cách thử RF trực tiếp có đúng không? Nên thay đổi ít nhất điều gì để giảm lỗi lớn và dự báo dư?

Source chính: [forecasting](../code/13_forecasting.py), [dashboard](../code/14_dashboard.py),
[tests](../tests/test_forecasting.py). Số liệu review nằm trong [review](review/).
Đã có 15 kiểm thử đạt và đối chiếu CSV/dashboard bằng dữ liệu thật.
Phân biệt lỗi đã có bằng chứng với giả thuyết; dẫn vị trí code khi báo lỗi.
