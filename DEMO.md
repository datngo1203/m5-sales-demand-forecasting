# Kịch bản thuyết trình và demo M5

Thời lượng gợi ý 6–8 phút cho cả nhóm. Các số dưới đây đối chiếu từ kết quả local ngày 25/10/2026. Chạy lại dữ liệu hoặc đổi cửa hàng có thể làm kết quả khác đi; khi đó dùng report mới.

## Chuẩn bị trước giờ trình bày

Mở PowerShell tại thư mục dự án. Nếu chưa có kết quả, chạy ` .\run_pipeline.ps1 -SkipInstall` sau khi chuẩn bị môi trường và dữ liệu theo README. Khi pipeline thành công, mở demo:

```powershell
.\.venv\Scripts\python.exe -m streamlit run code\14_dashboard.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Mở `http://127.0.0.1:8501`. Giữ terminal server chạy. Không chạy lại pipeline khi đang trình diễn vì nó thay các file mà dashboard đọc. Với máy đã chuẩn bị đủ môi trường và kết quả, demo không cần tải dữ liệu từ Internet.

Chuẩn bị sẵn ba nơi: dashboard, `outputs/forecast/forecast_report.json`, thư mục `code/`. Mở trước để tránh mất thời gian tìm file. Trước buổi trình bày, tự chụp màn hình dashboard và bảng sai số làm phương án dự phòng; ảnh chỉ là minh họa nếu ứng dụng không chạy được, cần nói rõ khi dùng.

## Phân chia hai người

Người làm phần bàn giao trình bày bài toán, dữ liệu và pipeline xử lý ban đầu trong 2 phút. Người làm phần bổ sung trình bày dự báo, thao tác dashboard, đánh giá và giới hạn trong 4–6 phút. Điều chỉnh theo đóng góp thực tế; đây là gợi ý trình bày, không xác nhận tác giả của từng dòng mã.

## 1. Bài toán và dữ liệu — khoảng 1 phút

Lời nói gợi ý:

> Nhóm em thực hiện đề tài phân tích bán hàng và dự báo nhu cầu sản phẩm. Mục tiêu là xem lượng bán, doanh thu thay đổi thế nào và thử dự báo lượng bán trong 28 ngày để hỗ trợ tham khảo kế hoạch nhập hàng. Đầu vào là dữ liệu M5 đã được thành viên trong nhóm xử lý và bàn giao.
>
> Dữ liệu local có 58.327.370 dòng, 22 cột, 10 cửa hàng và 3 nhóm sản phẩm, từ ngày 29/01/2011 đến 24/04/2016. Mỗi quan sát mô tả lượng bán của một sản phẩm tại một cửa hàng trong một ngày. Đây là dữ liệu lịch sử; khoảng 319 MB là dung lượng Parquet đã nén, không phải dung lượng CSV thô.

Chỉ vào `outputs/input_inventory.json` nếu cần chứng minh số dòng/schema và SHA-256. Không đọc hết các cột hoặc toàn bộ báo cáo.

## 2. Luồng xử lý và vai trò Big Data — khoảng 1 phút

Minh họa bằng lời theo thứ tự: CSV bán hàng + lịch + giá → PySpark xử lý → Parquet → Spark tổng hợp/chọn chuỗi → mô hình → CSV nhỏ → dashboard.

> Phần đầu dùng PySpark để chuyển dữ liệu ngày từ dạng nhiều cột sang từng dòng, kết hợp lịch và giá, rồi lưu Parquet. Phần bổ sung dùng Spark đọc toàn bộ dữ liệu để kiểm tra, tổng hợp và chọn các chuỗi bán hàng cần dự báo. Sau đó chỉ panel 20 sản phẩm được chuyển sang Python để huấn luyện Random Forest. Giao diện chỉ đọc khoảng 6,11 MB CSV kết quả nên không phải quét lại 58 triệu dòng khi đổi bộ lọc.
>
> Lần demo này Spark chạy local với 2 luồng, không phải cụm nhiều máy. Phần bàn giao có mã thao tác HDFS; nhóm cần có bằng chứng chạy trên máy của thành viên làm phần đó nếu trình bày HDFS đã vận hành. Trên máy demo hiện tại, em mới kiểm chứng pipeline local.

Nếu mở mã, chỉ cần chỉ tên `12_spark_analysis.py`, `13_forecasting.py`, `14_dashboard.py`; không giải thích từng dòng.

## 3. Thao tác phân tích bán hàng — khoảng 1 phút

1. Chọn cửa hàng **CA_1**, nhóm **Tất cả**, giữ toàn khoảng ngày ban đầu.
2. Chỉ vào lượng bán, doanh thu biết giá, tỷ lệ bao phủ và hai biểu đồ đầu.
3. Đổi khoảng ngày sang **01/03/2016–31/03/2016**. Lượng bán CA_1 trong tháng này là **136.557** nếu dùng đúng bản dữ liệu hiện tại.
4. Chọn nhóm **FOODS** để minh họa lọc doanh thu. Đổi lại **Tất cả** trước khi chuyển phần tiếp theo.

> Các bộ lọc cho phép xem lượng bán và phần doanh thu tính được theo cửa hàng, nhóm sản phẩm và thời gian. Doanh thu được tính bằng lượng bán nhân giá. Giá thiếu không tự thay bằng 0. Vì vậy giao diện kèm tỷ lệ bao phủ để người xem biết con số đang đầy đủ đến đâu.

Nếu cần minh họa cửa hàng khác, chọn CA_2 rồi quay lại CA_1. CA_2 xem được bán hàng nhưng không có dự báo trong bộ kết quả này. Bộ lọc nhóm chỉ thay phần doanh thu; nó không chọn lại danh sách sản phẩm dự báo.

## 4. Thao tác dự báo — khoảng 1,5 phút

1. Chọn **CA_1**, sản phẩm **FOODS_3_090**, tập **test**.
2. Đặt khoảng ngày lịch sử **01/01/2016–24/04/2016** để xem đoạn gần cửa sổ đánh giá.
3. Cuộn xuống biểu đồ lịch sử và biểu đồ so sánh thực tế/dự báo.
4. Giải thích ba đường bằng tên: `actual` là thực tế; `seasonal_naive` là lặp tuần trước; `random_forest` là mô hình hồi quy. Không dựa vào màu vì giao diện có thể đổi màu.
5. Chỉ bảng 28 ngày và nút **Tải CSV thực tế và dự báo**.

> Nhóm chọn 20 sản phẩm bán nhiều tại CA_1 chỉ bằng dữ liệu huấn luyện, không nhìn lượng bán của giai đoạn đánh giá để chọn sản phẩm. Mô hình dùng lượng bán các ngày trước, trung bình gần đây, lịch ngày và mã sản phẩm.
>
> Đường lặp tuần trước là mốc so sánh đơn giản: lấy mẫu 7 ngày cuối đã biết rồi lặp lại. Random Forest học từ nhiều cây hồi quy. Với cả hai cách, khi dự báo liên tiếp 28 ngày, ngày chưa biết được tính từ lịch sử và các dự báo đã tạo trước đó, không dùng lượng bán thật trong cửa sổ dự báo.
>
> Ở đây em đang giả lập đứng tại ngày 27/03/2016 để dự báo 28/03–24/04/2016. Vì dữ liệu giai đoạn đó đã có, em đối chiếu được dự báo với thực tế. Đây là kiểm chứng trên lịch sử, chưa phải dự báo 28 ngày sau ngày cuối bộ dữ liệu.

Bộ lọc ngày chỉ thay biểu đồ doanh thu và lịch sử, không thay cửa sổ test hay tính lại sai số. Nếu chuyển sang validation, mốc dự báo sẽ là 28/02/2016 và cửa sổ là 29/02–27/03/2016.

## 5. Đánh giá — khoảng 1 phút

Chỉ các dòng **ALL**, **test** trong bảng, không lấy số của một sản phẩm để nói về toàn bộ 20 sản phẩm:

| Mô hình | MAE | RMSE |
|---|---:|---:|
| Lặp tuần trước | 8,0625 | 12,4043 |
| Random Forest | 7,0504 | 10,4685 |

> MAE là sai lệch tuyệt đối trung bình. MAE khoảng 7,05 nghĩa là trung bình mô hình lệch khoảng 7,05 đơn vị bán cho mỗi sản phẩm trong mỗi ngày trên tập test này. RMSE nhấn mạnh hơn vào những lần sai số lớn. Hai độ đo càng nhỏ càng tốt.
>
> Random Forest giảm khoảng 12,6% MAE và 15,6% RMSE so với lặp tuần trước. Mô hình có MAE thấp hơn ở 16 trong 20 sản phẩm; 4 sản phẩm còn lại baseline tốt hơn. Vì thế nhóm không kết luận Random Forest luôn tốt hơn trên mọi sản phẩm.

Với riêng FOODS_3_090: baseline test MAE **18,0357**, RF **14,9455**. Đó là số của một sản phẩm, khác dòng ALL có 560 quan sát = 20 sản phẩm × 28 ngày. Giảm MAE 12,6% không có nghĩa “độ chính xác 87,4%”.

Mở **Cách đánh giá và giới hạn** nếu cần giải thích: train đến 28/02/2016; validation 29/02–27/03; test 28/03–24/04. Thử hai cấu hình RF trên validation, chọn bằng MAE; huấn luyện lại bằng train+validation trước khi đánh giá test.

## 6. Giá trị và giới hạn — khoảng 30–45 giây

> Sản phẩm demo cho phép xem tình hình bán hàng và so sánh dự báo cho từng sản phẩm. Kết quả có thể làm đầu vào tham khảo khi lập kế hoạch kho. Tuy nhiên mô hình mới đánh giá một cửa sổ 28 ngày trên 20 sản phẩm bán nhiều ở CA_1; chưa đại diện toàn bộ sản phẩm hoặc mọi thời điểm. Nhóm chưa mô hình hóa tồn kho, thời gian giao hàng và mức dự trữ an toàn, nên chưa tự động đưa ra số lượng cần nhập.
>
> Hướng tiếp theo là kiểm chứng HDFS trên môi trường vận hành, đánh giá nhiều cửa sổ thời gian và mở rộng sản phẩm/cửa hàng. Mô hình dự báo lượng bán quan sát được; khi hết hàng, lượng bán không phản ánh đầy đủ nhu cầu thực.

## Câu hỏi dễ gặp

| Câu hỏi | Trả lời ngắn |
|---|---|
| Big Data ở đâu khi dữ liệu nén khoảng 319 MB? | Có 58,3 triệu quan sát được Spark xử lý. Dung lượng nén không chứng minh quy mô cụm; thực nghiệm này dùng công nghệ Spark trên một máy, chưa chứng minh tăng tốc phân tán. |
| Vì sao không đưa tất cả dữ liệu vào Random Forest? | Spark xử lý toàn bộ đầu vào; mô hình demo giới hạn panel 20 sản phẩm để hoàn thành và kiểm chứng trong tài nguyên hiện có. Đây là giới hạn phạm vi cần công bố. |
| Tại sao không chia ngẫu nhiên train/test? | Dự báo theo thời gian phải học quá khứ và kiểm tra giai đoạn sau đó. Chia ngẫu nhiên có thể khiến quá trình đánh giá nhìn thấy thông tin của tương lai. |
| Bước 10 của bạn cùng nhóm có được dùng không? | Bộ forecasting_features chỉ được mô tả trên HDFS máy bàn giao và không có trong file nén. Luồng hiện tại tạo đặc trưng từ processed_m5 để chạy độc lập; chưa tích hợp đầu ra bước 10. |
| Tại sao không dùng giá vào mô hình? | Luồng hiện tại chưa định nghĩa cách biết giá tương lai; chỉ dùng lịch sử lượng bán và lịch ngày để tránh giả định thêm. Giá vẫn dùng để phân tích doanh thu quá khứ. |
| Doanh thu thiếu giá có đáng tin không? | 78,91% dòng có giá hợp lệ, nhưng các dòng thiếu giá trong bản hiện tại đều có lượng bán 0, nên bao phủ 100% lượng bán toàn bộ dữ liệu. Không suy rộng điều này sang bộ dữ liệu khác; giao diện vẫn hiện mức bao phủ. |
| Có cần bấm huấn luyện khi đổi sản phẩm? | Không. Dashboard đọc CSV kết quả; đổi bộ lọc không huấn luyện lại. Muốn tạo bộ dự báo khác phải chạy script dự báo. |
| Có dự báo được ngày sau 24/04/2016 không? | Source hiện tại xuất backtest để đánh giá. Chưa có luồng suy luận riêng cho các ngày sau mốc cuối dữ liệu. |
| HDFS đã chạy chưa? | Máy demo này chưa kiểm chứng HDFS. Chỉ trình bày bằng chứng phần HDFS của thành viên còn lại khi có log hoặc demo thực tế tương ứng. |
| Clone GitHub là chạy ngay được chưa? | Cần bổ sung Parquet từ gói bàn giao, Python 3.11, JDK 17 và cài phụ thuộc theo README. Git không chứa dữ liệu, môi trường và kết quả. |

## Nếu giảng viên yêu cầu chạy lại

Chạy ` .\run_pipeline.ps1 -SkipInstall` trong PowerShell từ thư mục dự án. Lệnh này kiểm tra phụ thuộc, inventory, Spark, dự báo rồi unittest; xem các log trong `outputs/`. Khi pipeline xong mới mở dashboard. Thời gian phải lấy từ report của lần chạy hiện tại, không cam kết thời gian cố định trên máy khác.
