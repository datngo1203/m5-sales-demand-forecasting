# Giải thích đồ án bán hàng và dự báo lượng bán

## Mục đích

Đề tài 12 dùng dữ liệu bán hàng theo sản phẩm/cửa hàng/ngày, Spark và HDFS,
mô hình dự báo, cùng dashboard để tham khảo kế hoạch hàng hóa.
Sản phẩm trả lời ba câu hỏi: đã bán thế nào, 28 ngày tới tại mốc mô phỏng có
thể bán bao nhiêu, và dự báo lệch thực tế bao nhiêu.

## Kiến trúc

```text
GuiDat/data/processed_m5 (Parquet đã xử lý)
    ├─ code/11_inspect_input.py → kiểm tra schema, footer và SHA256
    ├─ code/12_spark_analysis.py → Spark tổng hợp toàn bộ dữ liệu
    │       └─ outputs/analysis/*.csv
    └─ code/15_forecasting_v3.py → chọn nhóm 20 sản phẩm, dựng lịch sử
            └─ scikit-learn → outputs/forecast/*.csv và report JSON
                    └─ code/14_dashboard.py đọc CSV nhỏ

Luồng HDFS riêng:
Parquet nguồn → HDFS Docker → Spark đọc HDFS → outputs/analysis_hdfs
    └─ scripts/verify_hdfs.py đối chiếu bốn bảng với kết quả local
```

Spark xử lý phần dữ liệu lớn; scikit-learn học trên nhóm nhỏ. Dashboard không
đọc hàng chục triệu dòng hay huấn luyện khi đổi bộ lọc. Spark hiện chạy
local[2], HDFS gồm hai dịch vụ trên cùng máy Docker; chưa chứng minh chạy
cụm nhiều máy hoặc huấn luyện phân tán.

## Phần nào của thành viên được kế thừa

`GuiDat/code/01` đến `10` là mã khảo sát, tiền xử lý, EDA, chất lượng và tạo
đặc trưng của thành viên. Toàn bộ thư mục GuiDat được giữ nguyên, gồm code,
README, log/report gốc và dữ liệu local. Pipeline dùng bộ Parquet do thành viên cung
cấp; không tự chạy lại 04 để ghi đè dữ liệu.

README gốc có mô tả `/m5/forecasting_features`, nhưng bộ đó không nằm trong
gói bàn giao đang dùng. Dự báo hiện tạo đặc trưng từ lịch sử trước từng origin.
Origin là ngày lập dự báo. Không đưa lượng bán thật sau origin vào đầu vào
để đoán các ngày sau. Giữ code gốc không đồng nghĩa đã chạy lại tất cả code gốc.

## Dự báo hiện tại

RF là Random Forest: nhiều cây hồi quy cùng học từ lượng bán cũ, các giá trị
trễ, mức bán gần đây và thông tin ngày tháng. RF dự báo lần lượt; khi chưa biết
ngày tiếp theo, nó dùng số đã dự báo ở các ngày trước trong cửa sổ 28 ngày.

Trung bình 4 tuần cùng thứ lấy mức bán trung bình của cùng thứ trong bốn tuần
trước ngày lập dự báo. Lặp tuần trước lặp lại bảy ngày gần nhất.

**Dự báo cuối = 50% RF + 50% trung bình 4 tuần cùng thứ.** Ví dụ minh họa:
RF đoán 14 và cách cùng thứ đoán 10 thì dự báo cuối là 12. Đây là phép phối hợp,
không phải một mô hình RF mới. Tỷ trọng không được chọn lại từ bảng test.

V1 là bản đầu; V2 thử cải thiện; V3 chốt thủ tục và kiểm tra để tích hợp.
Repository giữ V1 qua `-V1`; mặc định dùng phương án phối hợp đã chốt ở V3.
Cấu hình runtime ở `config/forecast.json`; không phải bộ bằng chứng kết quả.

## Phạm vi và thời gian

Nhóm recent chọn 20 sản phẩm theo 26 tuần lịch sử đến 06/12/2015 và bỏ sản
phẩm bán 0 trong 28 ngày cuối; legacy chọn theo tổng lịch sử đến cùng mốc.
Các so sánh phương pháp phải dùng cùng nhóm và khoảng ngày.

Quy trình V2 dùng 13 origin cách nhau một tuần. Các cửa sổ 28 ngày có chồng
lấp, không phải 13 mẫu độc lập. Ngày lập test cuối là 27/03/2016, khoảng dự
báo 28/03–24/04/2016. Đây là backtest, nghĩa là mô phỏng dự báo trên quá khứ,
không phải dự báo tại ngày người xem đang mở ứng dụng.

Các test và các khoảng phát triển từng được xem. Không gọi chạy lại cùng
dữ liệu là đánh giá độc lập hoặc chọn tham số/phương pháp theo kết quả test.
Demo công bố seed42; seed là mốc ngẫu nhiên khi học. Git không có cache; máy mới
cần huấn luyện/tạo output trước khi hiển thị được các số thật trên dashboard.

## Đọc sai số đúng

- **MAE:** trung bình lệch bao nhiêu đơn vị mỗi sản phẩm mỗi ngày. MAE8 là
  lệch 8 đơn vị, không có nghĩa chính xác 92%.
- **RMSE:** cũng đo sai số lượng bán, nhấn mạnh hơn những lần lệch nhiều.
- **Dư/thiếu:** tổng dự báo trừ tổng thực tế; dương là dư, âm là thiếu.
  Phần trăm dư/thiếu chia cho tổng thực tế, không phải phần trăm chính xác.

Dư ở sản phẩm này có thể bù thiếu ở sản phẩm khác, nên cần xem cả từng sản
phẩm. Không kết luận một phương pháp tối ưu nhất hoặc luôn thắng đối chứng.

## Doanh thu và giá thiếu

Doanh thu biết giá là tổng lượng bán × giá của những dòng có giá hữu hạn,
không âm. Giá thiếu/không hợp lệ giữ ở trạng thái chưa biết, không điền 0 hoặc
lấy giá tương lai. Tỷ lệ bao phủ giá được hiển thị để người xem biết phạm vi.
Không suy ra nguyên nhân biến động hoặc hết hàng chỉ từ đồ thị lượng bán.

## Dùng để tham khảo hàng hóa

Tổng 28 ngày và bảng bốn tuần giúp hình dung lượng bán dự kiến. Người xem
có thể nhập tồn dùng được và hàng chắc chắn về trong cùng mốc mô phỏng để
tính `max(0, dự báo − tồn − hàng về)`. Đây là số giả định, không phải tồn kho
thật trong M5; đổi bộ dự báo sẽ xóa số giả định để tránh dùng nhầm.

Chênh lệch chưa phải lượng đặt hàng. Còn thiếu ngày nhận, thời gian giao,
tồn an toàn, hạn dùng, quy cách và chi phí; hàng về muộn có thể vẫn không đủ
đáp ứng từng ngày. Chưa đủ cơ sở tự động nhập hàng.

## Kết quả được giữ để giải thích lựa chọn

`resources/v3_test_metrics.csv` giữ nguyên 24 dòng tổng hợp V3: ba cửa hàng,
hai nhóm sản phẩm, bốn phương pháp. Đây là trung bình chỉ số seed42/43/44,
không phải chỉ số của ensemble ba model. Bảng này cần cho trang độ tin cậy;
không phải dữ liệu huấn luyện hoặc cache dùng để chọn lại phương pháp.

V3 chọn phối hợp bằng validation CA_1/CA_2 trước khi kiểm tra ba cửa hàng.
Điều kiện chấp nhận đặt trước yêu cầu ít nhất hai cửa hàng đồng thời không
tăng MAE và độ lớn bias trên cả hai nhóm so với RF. Khi đó cả ba cửa hàng đạt.
Tất cả test này hiện đã được xem; không dùng lại để chỉnh rồi gọi là test mới.

Vẫn có điểm kém RF: RMSE CA_3/recent tăng 16,9674 → 17,0023; sai số theo mức
bán TX_1/legacy tăng 1,8865 → 1,9206. Không thay điều kiện chấp nhận sau khi thấy
hai chỉ số này và không kết luận phương pháp tốt nhất trong mọi trường hợp.

Ba lượt thử tiếp theo không được tích hợp:

| Hướng thử | Kết quả so mốc | Quyết định |
| --- | --- | --- |
| RF90 và đổi tỷ trọng phối hợp | Đối chiếu: điểm MAE tăng 0,91%, chỉ 1/10 bộ không kém | Giữ bản hiện tại |
| RF180 thêm lịch/SNAP và cùng thứ 8/12 tuần | Đối chiếu: tăng 0,58%, 4/10 bộ không kém | Giữ bản hiện tại |
| Học chung 135 chuỗi, dự báo trực tiếp | Phát triển: phối hợp tăng 0,74%, dùng riêng tăng 4,70% | Dừng trước đối chiếu |

Các con số là thay đổi của điểm MAE, không phải phần trăm chính xác. Các lượt
thử là hồi cứu trên khoảng đã xem; không được dùng để khẳng định cải thiện độc lập.

## Đối chiếu đề tài và trạng thái kiểm chứng

| Nội dung | Phần thực hiện |
| --- | --- |
| Sản phẩm, cửa hàng, thời gian | Dữ liệu M5, 32 Parquet, 58.327.370 dòng và 22 cột |
| Lưu trữ HDFS | Một NameNode/một DataNode trong Docker, nguồn được mount chỉ đọc |
| Spark làm sạch/tổng hợp | Từ chối khóa/ngày/lượng bán sai; phân biệt giá hợp lệ; xuất bốn bảng nhỏ |
| Hồi quy/chuỗi thời gian | RF và đối chứng cùng thứ/lặp tuần trước, 28 ngày, chia theo thời gian |
| Trực quan hóa phục vụ kho | Ba trang dashboard, doanh thu có giá, bốn tuần và tình huống hàng hóa |
| Đánh giá và giới hạn | MAE/RMSE/dư-thiếu, giữ cả kết quả kém và phân biệt demo một seed với V3 ba seed |

Lượt HDFS ngày 26/10/2026 đã đọc đủ 58.327.370 dòng, 65.695.409 đơn vị; bốn
bảng khớp local, hash byte nguồn/HDFS khớp, fsck HEALTHY. Tạo lại DataNode vẫn
còn 32 file trong volume. Đây là kiểm chứng trên một máy, không phải benchmark
cụm nhiều máy. Môi trường container: Spark3.5.3/Python3.8.10/Java11; host dùng
Python3.11/JDK17. Bằng chứng chạy lưu local ở `outputs/analysis_hdfs`.

Không tuyên bố đã kiểm tra hoặc xóa toàn bộ trùng khóa trên 58 triệu dòng:
tổng hợp giữ nguyên dữ liệu bàn giao. Nhóm dự báo có kiểm tra trùng/thiếu ngày.
Không coi chữ PASS trong report gốc là bằng chứng đã chạy lại trên máy hiện tại.

## Phạm vi dọn dự án ngày 27/10/2026

Thiết lập mặc định được tách khỏi báo cáo nghiên cứu sang `config/forecast.json`.
Mã dự báo/đặc trưng và schema CSV được giữ, V1 vẫn gọi được. Tài liệu cài/chạy/demo
gộp vào README; giải thích kiến trúc, nguồn, kết quả và giới hạn nằm tại file này.
Chỉ giữ bảng V3 nhỏ mà dashboard sử dụng trong `resources`.

Đã loại khỏi cây source các bản thảo Word/kế hoạch nộp môn, yêu cầu review cũ,
bảng/JSON chẩn đoán lặp lại và code thí nghiệm không thuộc luồng chính. Trước khi
dọn đã lưu bản phục hồi đầy đủ kèm hash tại `.runtime/cleanup_20261027_210323`.
Các file trước đây đã commit vẫn có trong lịch sử Git; dữ liệu và kết quả chạy
local không bị xóa. Bản phục hồi không được đưa lên GitHub.

Đối chiếu với `GuiDat.rar` gốc trước và sau dọn: 48/48 file giống nội dung,
bao gồm 32 Parquet. Git chỉ theo dõi code/report của GuiDat nên hash bản RAR
được dùng bổ sung để kiểm tra cả phần dữ liệu bị gitignore.
