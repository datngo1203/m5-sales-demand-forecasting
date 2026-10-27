# Chạy HDFS và Spark cho đề tài 12

Yêu cầu: Docker Desktop Linux containers, dữ liệu tại `GuiDat/data/processed_m5`,
môi trường `.venv` theo README và bộ local `outputs/analysis` để đối chiếu.
Image Apache Hadoop3.4.1 và Spark3.5.3-python3 được tải ở lần đầu.
Compose khóa digest đúng hai image đã chạy để tránh tag thay đổi ở lần tải sau.

Từ thư mục gốc dự án:

```powershell
.\run_hdfs_demo.ps1
```

NameNode quản lý tên file tại http://127.0.0.1:9870. Vào Utilities → Browse the file
system, mở `/m5/processed_m5`. Một DataNode lưu 32 file trong volume Docker riêng;
không sửa bản Parquet gốc. Spark trong container đọc `hdfs://namenode:9000/m5/processed_m5`.
Chỉ cổng giao diện NameNode được mở trên loopback Windows; các cổng dữ liệu ở mạng Compose.

Script không ghi đè file HDFS đã tồn tại. Sau nạp, nó so SHA256 của toàn bộ 32 file
theo thứ tự tên với dữ liệu nguồn, chạy fsck, rồi chạy script tổng hợp hiện có.
`scripts/verify_hdfs.py` so từng dòng/khóa của cả bốn CSV với local, cho sai số số thực
rtol1e-10/atol1e-6. Bằng chứng lưu tại:

- `outputs/analysis_hdfs/hdfs_storage.log`: SHA256, số file/byte, DataNode, fsck.
- `outputs/analysis_hdfs/analysis_report.json`: nguồn HDFS, chất lượng, tổng và môi trường.
- `outputs/analysis_hdfs/verification.json`: bốn bảng đã đối chiếu và hash report.
- `outputs/analysis_hdfs/spark.log`: log chạy Spark.

Đã chạy ngày 26/10/2026: 32 file, 318.838.151 byte, 58.327.370 dòng,
65.695.409 đơn vị bán, bốn bảng khớp local và filesystem HEALTHY.
Tạo lại DataNode vẫn thấy đủ 32 file trong volume. Spark tính tổng hợp trong 27,73 giây
(không tính thời gian tải image/nạp HDFS/khởi động). Không phải benchmark nhiều máy.

Xem và dừng dịch vụ, vẫn giữ dữ liệu:

```powershell
docker compose -f infra/hdfs/compose.yaml ps
docker compose -f infra/hdfs/compose.yaml logs --tail 30
docker compose -f infra/hdfs/compose.yaml stop
docker compose -f infra/hdfs/compose.yaml up -d --wait namenode datanode
```

Không dùng `down -v`: lệnh đó xóa volume HDFS. NameNode chỉ format khi volume mới chưa
có VERSION. Nếu dữ liệu đã tồn tại khác nguồn, script dừng thay vì tự xóa/ghi đè.

Phạm vi: HDFS thật với một NameNode/một DataNode trên một máy Docker; Spark local[2].
Không có YARN, Spark cluster nhiều máy, HA hoặc cơ chế phục hồi nhiều bản sao;
replication=1 cho bản demo. Model scikit-learn và các cache cũ được giữ riêng.

Tham khảo image gốc: [Apache Hadoop](https://hub.docker.com/r/apache/hadoop),
[Dockerfile Apache Spark](https://github.com/apache/spark-docker).
