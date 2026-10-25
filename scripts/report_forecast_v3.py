"""Publish concise V3 evidence from cached results; no training or test re-evaluation."""
import csv
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"code"),str(ROOT/"scripts")]
import numpy as np
import forecast_v3 as v3
from run_forecast_v2 import read,dump,fingerprint


def main():
    out=ROOT/"outputs/forecast_v3"
    frozen=read(out/"frozen.json")
    selection=read(out/"selection.json")
    complete=read(out/"test_complete.json")
    started=read(out/"test_started.json")
    decision=read(out/"integration.json")
    assert frozen["created_at_utc"]<started["started_at_utc"]<complete["completed_at_utc"]
    assert started["frozen_sha256"]==complete["frozen_sha256"]==fingerprint([out/"frozen.json"])
    with (out/"test_metrics.csv").open() as stream:
        rows=list(csv.DictReader(stream))
    numeric=[{**r,**{k:float(r[k]) for k in ("mae","rmse","bias_pct","normalized_rmse","delta_bias")}} for r in rows]
    assert v3.integration_gate(numeric,frozen["choice"],frozen["stores"])==decision
    lines=[]
    def add(s=""): lines.append(s)
    def f(x): return f"{float(x):.4f}"
    def table(headers,data):
        add("| "+" | ".join(headers)+" |")
        add("| "+" | ".join(["---"]*len(headers))+" |")
        for row in data: add("| "+" | ".join(map(str,row))+" |")
        add()
    add("# Kết quả V3")
    add()
    add(f"Ứng viên đã chọn trước test: **{frozen['choice']}**. "
        f"Cổng tích hợp: **{decision['passed_stores']}/3 cửa hàng** đạt đồng thời MAE và |bias_pct| "
        f"trên cả recent và legacy; yêu cầu ít nhất 2/3. "
        +("Quyết định: đưa thủ tục V2 đã chọn làm mặc định; giữ V1 qua cờ." if decision["integrate"] else
          "Quyết định: giữ V1 mặc định; không đổi ứng viên theo kết quả test."))
    add()
    add("CA_1 và CA_2, kể cả test, đều đã xem. V3 chỉ chọn bằng validation của hai store này, "
        "tái dùng nguyên output V2, không train lại RF/direct. CA_3, TX_1, WI_1 là ba store chưa dùng "
        "trước lượt test này; cấu hình/thủ tục đóng băng trước validation mới. Giờ các test đó cũng "
        "đã được xem; không gọi chúng là test tươi cho lần phát triển kế tiếp.")
    add()
    add("## Chọn bằng validation đã có")
    add()
    table(["Ứng viên","Điểm MAE / RF","Thay đổi %","TB trị tuyệt đối bias_pct","Đủ điều kiện bias"],
        [[m,f(x["score"]),f(100*(x["score"]-1)),f(x["mean_abs_bias_pct"]),x["eligible"]]
         for m,x in selection["decision"]["candidates"].items()])
    add("Điểm = trung bình bốn tỷ số điểm MAE qua CA_1/CA_2 × hai panel. "
        "Điểm mỗi bộ = trung vị origin trong nhóm rồi trung vị bốn nhóm, sau trung bình metric ba seed. "
        "Metric gộp dưới đây khác điểm chọn. RF×k có bias validation gần 0 theo định nghĩa vì fit k "
        "và đánh giá trên cùng nhãn; không coi đó là bằng chứng độc lập về hiệu chỉnh. "
        "Hệ số k không bị đóng băng chung: mỗi store/panel dùng validation của chính nó.")
    add()
    table(["Store","Panel","Ứng viên","Điểm MAE nhóm","MAE gộp","RMSE","Bias %"],
        [[s["store"],s["panel"],m,f(x["score"]),f(x["metrics"]["mae"]),f(x["metrics"]["rmse"]),f(x["metrics"]["bias_pct"])]
         for s in selection["sets"] for m,x in s["summary"].items() if m!="seasonal_naive"])
    add("## Lượt test cuối duy nhất tại ba store mới")
    add()
    add("Trung bình metric seed42/43/44, không phải metric của ensemble. nRMSE chia sai số từng item "
        "cho max(mean_28 trước origin,1), rồi căn trung bình bình phương. Δ = bias model − bias seasonal_naive, "
        "có dấu; Δ thấp hơn không bảo đảm |bias| thấp hơn.")
    add()
    table(["Store","Panel","Mô hình","MAE","RMSE","Bias %","nRMSE","Δ đơn vị"],
          [[r["store"],r["panel"],r["model"]]+[f(r[k]) for k in
            ("mae","rmse","bias_pct","normalized_rmse","delta_bias")] for r in rows])
    add("## Thay đổi giúp hoặc không giúp bao nhiêu")
    add()
    effects=[]
    for store in frozen["stores"]:
        for panel in frozen["panels"]:
            base=next(r for r in numeric if r["store"]==store and r["panel"]==panel and r["model"]=="random_forest")
            for model in dict.fromkeys((frozen["choice"],"weekday_mean4","seasonal_naive")):
                candidate=next(r for r in numeric if r["store"]==store and r["panel"]==panel and r["model"]==model)
                effects.append([store,panel,model,f(candidate["mae"]-base["mae"]),
                    f(100*(candidate["mae"]/base["mae"]-1)),
                    f(abs(candidate["bias_pct"])-abs(base["bias_pct"])),
                    f(candidate["rmse"]-base["rmse"]),f(candidate["normalized_rmse"]-base["normalized_rmse"])])
    table(["Store","Panel","Đối chứng","Chênh MAE với RF","Chênh MAE %","Chênh độ lớn bias (điểm %)","Chênh RMSE","Chênh nRMSE"],effects)
    add("Giảm là tốt hơn cho cả hai cột chênh MAE và chênh |bias|. "
        "Giữ cả hàng kém hơn RF. Không chọn lại weekday_mean4 hoặc RF×k bằng test. "
        "Không thử direct nữa vì Pha 1 chỉ chẩn đoán model đã có.")
    add("Blend không cải thiện mọi metric: bảng giữ cả RMSE CA_3/recent và nRMSE TX_1/legacy "
        "kém RF. Cổng đã đăng ký chỉ kiểm MAE và độ lớn bias; không thay điều kiện sau khi thấy "
        "các metric này. Weekday_mean4 cũng không luôn giảm MAE so với RF, dù tốt hơn seasonal_naive.")
    add()
    add("## Cổng tích hợp đã đăng ký trước")
    add()
    table(["Store","Recent đạt","Legacy đạt","Store đạt"],
        [[s,x["panels"]["recent"],x["panels"]["legacy"],x["passed"]] for s,x in decision["stores"].items()])
    add("Một store chỉ đạt khi cả hai panel đồng thời có MAE candidate≤RF và |bias_pct candidate|≤|bias_pct RF|. "
        "Không gộp hai panel để che panel kém. Cổng test chỉ accept/reject thủ tục đã chọn, "
        "không được đổi candidate hoặc tham số sau khi biết test.")
    add()
    add("## Bằng chứng và tái lập")
    add()
    add("- [Kế hoạch](V3_PLAN.md), [lựa chọn từ validation](V3_SELECTION.json), [manifest đóng băng](V3_FROZEN.json).")
    add("- [V3_TEST_METRICS.csv](V3_TEST_METRICS.csv), [V3_SEED_METRICS.csv](V3_SEED_METRICS.csv), "
        "[V3_BIAS_BY_H.csv](V3_BIAS_BY_H.csv), [V3_AUDIT.json](V3_AUDIT.json).")
    add("- [Chẩn đoán Bổ sung 3](DIAGNOSIS.md): cặp item/origin lỗi direct, top NSSE RF, bias tập trung, "
        "và tổng tuần cùng giỏ 20 item mọi store; bốn tuần sau ở store mới chỉ công bố sau test_complete.")
    add()
    add("```powershell\n.\\.venv\\Scripts\\python.exe scripts/diagnose_supplement3.py\n"
        ".\\.venv\\Scripts\\python.exe scripts/select_forecast_v3.py\n"
        ".\\.venv\\Scripts\\python.exe scripts/run_forecast_v3.py prepare\n"
        ".\\.venv\\Scripts\\python.exe scripts/run_forecast_v3.py test\n"
        ".\\.venv\\Scripts\\python.exe scripts/diagnose_supplement3.py --reveal-after-test\n"
        ".\\.venv\\Scripts\\python.exe scripts/report_forecast_v3.py\n```")
    add()
    add("Không lặp lệnh test trên output đã tiêu thụ: test_started tạo độc quyền và chặn trước đọc nhãn; "
        "test_complete chỉ ghi khi đủ cả ba store/hai panel. Cache validation và dự báo/model RF ở origin "
        "test được dùng lại, không train lại kết quả đã có. Các lệnh chẩn đoán/report chỉ đọc; "
        "chạy lại report không phải chạy lại test. Bản tích hợp cuối và kết quả unittest ghi ở mục bàn giao bên dưới.")
    add()
    add("## Giới hạn")
    add()
    add("Thiết kế đã chịu ảnh hưởng chẩn đoán hồi cứu. Validation 13 origin chồng giữa nhóm nên không phải "
        "13 mẫu độc lập; không tính CI giả định độc lập. Ba seed không thay thế ba dataset độc lập. "
        "RF×k in-sample validation có lạc quan, không được kết luận hiệu chỉnh tốt trên test khi không được "
        "chọn để đánh giá. Tổng tuần giỏ CA_1 legacy không đại diện toàn store hoặc panel riêng. "
        "Bảng tuần sau test làm lộ thêm tổng gộp của các store khác; không gọi những tổng này là dữ liệu "
        "chưa xem cho thí nghiệm sau. Không suy ra stockout hoặc nhân quả từ scale thấp, chuỗi 0 hay lễ. "
        "Ba store dùng cùng khoảng lịch test trong cùng dataset, không phải thử trên một giai đoạn tương lai "
        "độc lập; kết quả có thể cùng chịu bối cảnh chung. Hai panel không cùng tập sản phẩm; "
        "không diễn giải đổi panel là tác động nhân quả. "
        "Không thêm thư viện hoặc tìm siêu tham số mới.")
    docs=ROOT/"docs/review"
    (docs/"V3_RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    for src,dest in (("test_metrics.csv","V3_TEST_METRICS.csv"),("test_seed_metrics.csv","V3_SEED_METRICS.csv"),
                     ("test_bias_by_h.csv","V3_BIAS_BY_H.csv")):
        (docs/dest).write_bytes((out/src).read_bytes())
    dump(docs/"V3_INTEGRATION.json",decision)
    dump(docs/"V3_AUDIT.json",{"test_started":started,"test_complete":complete,
        "development_reused":True,"test_single_pass":True,
        "frozen_procedure_current":fingerprint([ROOT/p for p in frozen["procedure_hashes"]])==frozen["procedure_hashes"]})
    print("Published V3 results from cached metrics")


if __name__=="__main__": main()
