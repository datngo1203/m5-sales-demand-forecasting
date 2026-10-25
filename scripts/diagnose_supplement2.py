"""Read existing CSV only and print the Markdown appendix; no training or file writes.

Run: .venv/Scripts/python.exe scripts/diagnose_supplement2.py
The selection-period analysis receives only rows dated <= 2015-12-06.
"""

import csv
from datetime import date, timedelta
import hashlib
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPARSE = {f"FOODS_3_{suffix}" for suffix in ("541", "635", "319", "808", "318")}
TEST_ORIGIN = date(2016, 3, 27)
FIRST_ORIGIN = date(2015, 12, 6)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def week_totals(lookup, items, origin, count):
    assert origin.weekday() == 6
    weeks = []
    for i in range(count):
        end = origin - timedelta(weeks=count - 1 - i)
        start = end - timedelta(days=6)
        total = sum(lookup[item, start + timedelta(days=d)] for item in items for d in range(7))
        weeks.append((start, end, total))
    return weeks


def slope(values):
    return float(np.polyfit(np.arange(len(values)), values, 1)[0])


def ratio_summary(lookup, items, origin):
    # Disjoint periods: the latest four weeks vs the 26 weeks immediately preceding them.
    result = []
    for item in items:
        weeks = week_totals(lookup, [item], origin, 30)
        earlier = float(np.mean([w[2] for w in weeks[:26]]))
        recent = float(np.mean([w[2] for w in weeks[26:]]))
        result.append((item, earlier, recent, recent / earlier if earlier else None))
    return result


def selection_period(history, selected):
    # This function cannot access later history, predictions, or test labels.
    assert history and max(r["date"] for r in history) <= FIRST_ORIGIN
    items = sorted(r["item_id"] for r in selected)
    lookup = {(r["item_id"], r["date"]): r["units"] for r in history}
    for r in selected:
        total = sum(h["units"] for h in history if h["item_id"] == r["item_id"])
        assert total == float(r["train_units"])
    weeks = week_totals(lookup, items, FIRST_ORIGIN, 52)
    return weeks, ratio_summary(lookup, items, FIRST_ORIGIN), len(history)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    assert np.isclose(slope([2, 4, 6]), 2)
    folder = ROOT / "outputs/forecast"
    paths = [folder / name for name in ("history.csv", "predictions.csv", "selected_series.csv")]
    missing = [str(p.relative_to(ROOT)) for p in paths if not p.is_file()]
    if missing:
        print("## Bổ sung 2\n\nChưa đủ dữ liệu. Thiếu: " + ", ".join(missing))
        print("\nKhôi phục nguồn theo DATA_SOURCE.md rồi dùng `./run_pipeline.ps1 -SkipInstall` "
              "để tái tạo outputs khi được phép train lại. Không chạy pipeline trong chẩn đoán này.")
        return
    selected = read_csv(paths[2])
    items = sorted(r["item_id"] for r in selected)
    assert len(set(items)) == 20 and SPARSE <= set(items)
    assert {r["store_id"] for r in selected} == {"CA_1"}
    history = read_csv(paths[0])
    for r in history:
        r["date"] = date.fromisoformat(r["date"])
        r["units"] = float(r["units"])
    lookup = {(r["item_id"], r["date"]): r["units"] for r in history}
    assert len(lookup) == len(history) == 20 * 1913
    assert {r["item_id"] for r in history} == set(items)
    assert {r["store_id"] for r in history} == {"CA_1"}
    predictions = read_csv(paths[1])
    assert len(predictions) == 3360
    assert len({(r["split"], r["model"], r["item_id"], r["date"]) for r in predictions}) == 3360
    for r in predictions:
        assert float(r["actual"]) == lookup[r["item_id"], date.fromisoformat(r["date"])]
        if r["model"] == "seasonal_naive":
            source_day = date.fromisoformat(r["origin_date"]) - timedelta(days=6) + timedelta(
                days=(int(r["horizon"]) - 1) % 7)
            assert float(r["prediction"]) == lookup[r["item_id"], source_day]
    before_selection = [r for r in history if r["date"] <= FIRST_ORIGIN]
    pre_weeks, pre_ratios, pre_rows = selection_period(before_selection, selected)
    assert all(late == 0 for item, _, late, _ in pre_ratios if item in SPARSE)
    lines = []

    def add(s=""):
        lines.append(s)

    def fmt(x):
        return "không xác định" if x is None else f"{x:.4f}"

    def table(headers, rows):
        add("| " + " | ".join(headers) + " |")
        add("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            add("| " + " | ".join(map(str, row)) + " |")
        add()

    def trend_text(weeks, label):
        values = [w[2] for w in weeks]
        add(f"- {label}: slope OLS = **{fmt(slope(values))} đơn vị/tuần mỗi bước tuần**; "
            f"trung bình = {fmt(float(np.mean(values)))} đơn vị/tuần; "
            f"số bước giảm = {sum(b < a for a, b in zip(values, values[1:]))}/{len(values)-1}.")

    add("## Bổ sung 2")
    add()
    add("Phạm vi giữ nguyên: phân tích CSV đã có, không sửa `code/`, `tests/`, không train/suy luận lại, "
        "không dùng nhãn test đề xuất cấu hình. Mọi bias dưới đây là tổng có dấu, prediction − actual, "
        "không phải MAE hoặc tổng trị tuyệt đối sai số. Các tỷ lệ đóng góp có mẫu số ghi rõ; "
        "số âm là bù trừ, không phải đóng góp lỗi tuyệt đối.")
    add()
    add("### 2.1. Phân rã bias RF theo sản phẩm và nhóm")
    add()
    add("Đặt B_SN = Σ(seasonal_naive − actual), B_RF = Σ(RF − actual), "
        "Δ = B_RF − B_SN = Σ(RF − seasonal_naive). Khi đó **B_RF = B_SN + Δ**. "
        "Đây là đồng nhất thức số học trên cùng 28 ngày, không phải phân rã nguyên nhân. "
        "Δ không thể được gọi là phần lỗi chỉ do đệ quy, vì hai mô hình còn khác mức dự báo và cách học.")
    add()
    add("Nhóm 5 sản phẩm thưa được cố định đúng theo yêu cầu: FOODS_3_541, FOODS_3_635, "
        "FOODS_3_319, FOODS_3_808, FOODS_3_318. Tên nhóm không hàm ý cả năm đều thưa ở mọi cửa sổ; "
        "15 sản phẩm còn lại là phần bù của panel.")
    add()
    for split, period, origin in (
        ("validation", "29/02–27/03/2016", date(2016, 2, 28)),
        ("test", "28/03–24/04/2016", TEST_ORIGIN),
    ):
        values = []
        for item in items:
            totals = {}
            actuals = {}
            for model in ("seasonal_naive", "random_forest"):
                rows = [r for r in predictions if r["split"] == split and r["model"] == model
                        and r["item_id"] == item]
                assert len(rows) == 28
                assert {int(r["horizon"]) for r in rows} == set(range(1, 29))
                assert {r["origin_date"] for r in rows} == {origin.isoformat()}
                actuals[model] = {r["date"]: float(r["actual"]) for r in rows}
                totals[model] = sum(float(r["prediction"]) - float(r["actual"]) for r in rows)
            assert actuals["seasonal_naive"] == actuals["random_forest"]
            sn, rf = totals["seasonal_naive"], totals["random_forest"]
            values.append((item, sum(actuals["random_forest"].values()), sn, rf - sn, rf))
        add(f"#### {split}: {period}, origin {origin.isoformat()}")
        add()
        table(["Sản phẩm", "Nhóm", "Tổng actual", "B_SN", "Δ = B_RF − B_SN", "B_RF"],
              [[item, "5 thưa" if item in SPARSE else "15 còn lại", fmt(a), fmt(sn), fmt(delta), fmt(rf)]
               for item, a, sn, delta, rf in values])
        groups = []
        for name, group in (("5 thưa", SPARSE), ("15 còn lại", set(items) - SPARSE), ("ALL", set(items))):
            sums = [sum(row[i] for row in values if row[0] in group) for i in range(1, 5)]
            assert np.isclose(sums[1] + sums[2], sums[3])
            groups.append((name, *sums))
        table(["Nhóm", "Tổng actual", "B_SN", "Δ", "B_RF"],
              [[name] + [fmt(x) for x in nums] for name, *nums in groups])
        total = groups[-1]
        table(["Nhóm", "% B_SN toàn panel", "% Δ toàn panel", "% B_RF toàn panel"],
              [[row[0]] + [fmt(100 * row[i] / total[i]) if total[i] else "không xác định"
                           for i in (2, 3, 4)] for row in groups[:2]])
        add(f"**Bằng chứng:** toàn panel {fmt(total[4])} = {fmt(total[2])} + {fmt(total[3])}. "
            f"Trong bias RF tổng, thành phần B_SN chiếm {fmt(100*total[2]/total[4])}% "
            f"và Δ chiếm {fmt(100*total[3]/total[4])}%. "
            "Tỷ trọng theo nhóm ở bảng trên dùng tổng của từng cột làm mẫu số; "
            "có thể vượt 100% khi nhóm kia có bias âm.")
        add()

    add("### 2.2. Tổng tuần trước origin test và bốn tuần test")
    add()
    add("Origin ở mục này là **27/03/2016**. 52 tuần trước origin được định nghĩa là 52 tuần đầy đủ "
        "Thứ hai–Chủ nhật kết thúc đúng ngày origin (30/03/2015–27/03/2016); tuần cuối chứa ngày origin, "
        "đều đã quan sát khi lập dự báo. Bốn tuần test là 28/03–24/04/2016. "
        "Đánh số t=−51..0 cho 52 tuần lịch sử, t=1..4 cho test.")
    add()
    weeks = week_totals(lookup, items, TEST_ORIGIN, 52)
    future = week_totals(lookup, items, TEST_ORIGIN + timedelta(weeks=4), 4)
    assert sum(w[2] for w in future) == sum(float(r["actual"]) for r in predictions
        if r["split"] == "test" and r["model"] == "random_forest")
    table(["t", "Cửa sổ", "Từ ngày", "Đến ngày", "Tổng 20 sản phẩm"],
          [[i-51, "trước/đến origin", start, end, fmt(total)] for i, (start, end, total) in enumerate(weeks)]
          + [[i+1, "test", start, end, fmt(total)] for i, (start, end, total) in enumerate(future)])
    add("Bằng chứng mô tả xu hướng (OLS có intercept, không kiểm định ý nghĩa/nhân quả):")
    add()
    trend_text(weeks, "52 tuần trước/đến origin")
    trend_text(future, "4 tuần test")
    trend_text(weeks + future, "Toàn bộ 56 tuần, đối chiếu hồi cứu")
    first26 = float(np.mean([w[2] for w in weeks[:26]]))
    last26 = float(np.mean([w[2] for w in weeks[26:]]))
    recent4 = float(np.mean([w[2] for w in weeks[-4:]]))
    earlier26 = float(np.mean([w[2] for w in weeks[-30:-4]]))
    test4 = float(np.mean([w[2] for w in future]))
    add(f"- Hai nửa năm trước origin: 26 tuần đầu {fmt(first26)} → 26 tuần sau {fmt(last26)} "
        f"đơn vị/tuần ({fmt(100*(last26/first26-1))}%).")
    add(f"- Bốn tuần cuối trước origin {fmt(recent4)} → bốn tuần test {fmt(test4)} "
        f"đơn vị/tuần ({fmt(100*(test4/recent4-1))}%).")
    add()
    add("**Kết luận:** " + ("xác nhận" if slope([w[2] for w in weeks]) < 0 else "bác bỏ")
        + " xu hướng giảm tuyến tính trên 52 tuần lịch sử theo dấu slope; "
        + ("xác nhận" if slope([w[2] for w in future]) < 0 else "bác bỏ")
        + " xu hướng giảm tuyến tính trong bốn tuần test. Xu hướng trung bình không đồng nghĩa giảm "
        "đơn điệu. So sánh trung bình bốn tuần test với bốn tuần cuối lịch sử được nêu riêng, "
        "không đồng nhất với slope trong từng cửa sổ.")
    add()
    add("#### Tỷ số cho từng sản phẩm tại origin test")
    add()
    add("Mẫu số là trung bình tuần của **26 tuần ngay trước bốn tuần cuối**, không chồng lấp: "
        "31/08/2015–28/02/2016. Tử số là trung bình tuần của bốn tuần cuối: 29/02–27/03/2016. "
        "Trung bình ngày cho cùng khoảng cho đúng tỷ số này. Tỷ số <1 là mức bán gần origin thấp hơn "
        "khoảng đối chiếu, không tự chứng minh xu hướng đơn điệu.")
    add()
    ratios = ratio_summary(lookup, items, TEST_ORIGIN)
    table(["Sản phẩm", "TB tuần 26 tuần trước đó", "TB tuần 4 tuần cuối", "Tỷ số 4/26"],
          [[item, fmt(early), fmt(late), fmt(ratio)] for item, early, late, ratio in ratios])
    add(f"**Bằng chứng:** {sum(x[3] is not None and x[3] < 1 for x in ratios)}/20 sản phẩm có tỷ số <1. "
        f"Tỷ số của tổng panel = {fmt(recent4/earlier26)} "
        f"({fmt(recent4)} / {fmt(earlier26)}); đây không phải trung bình các tỷ số sản phẩm.")
    add()

    add("### 2.3. Panel chọn bằng tổng bán: chỉ dùng dữ liệu đến origin đầu tiên")
    add()
    add("**Giới hạn nhận diện:** thời điểm chốt panel là cuối 06/12/2015; code chọn bằng tổng bán "
        "trước 07/12/2015. Yêu cầu chỉ dùng dữ liệu trước/đến mốc này không cho phép quan sát mức bán "
        "sau khi chọn. Vì vậy **chưa đủ dữ liệu trong phạm vi mục 2.3 để xác nhận/bác bỏ bán giảm sau "
        "thời điểm chọn**. Không dùng số liệu test/validation của mục 2.1–2.2 để lấp khoảng trống này. "
        "Phần có thể kiểm tra là dấu hiệu giảm đã xuất hiện trước lúc chốt panel hay chưa. "
        "Ngày 06/12 được tính vào lịch sử vì là ngày origin, quan sát đã biết trước dự báo 07/12.")
    add()
    add(f"Hàm `selection_period` chỉ nhận {pre_rows} dòng history có date ≤ 2015-12-06, "
        "assert không có dòng sau mốc, và assert tổng bán từng sản phẩm khớp `train_units` "
        "trong selected_series.csv. Không tái chọn sản phẩm từ nhãn tương lai. "
        "Đây là đối chiếu panel đã lưu; không tự xác minh thứ hạng top 20 so với toàn bộ sản phẩm "
        "CA_1 vì history chỉ chứa panel đã chọn.")
    add()
    add("Bối cảnh hoàn toàn trước lúc chọn: 52 tuần 08/12/2014–06/12/2015.")
    add()
    trend_text(pre_weeks, "52 tuần trước/đến origin đầu tiên")
    pre_first26 = float(np.mean([w[2] for w in pre_weeks[:26]]))
    pre_last26 = float(np.mean([w[2] for w in pre_weeks[26:]]))
    pre_late4 = sum(x[2] for x in pre_ratios)
    pre_early26 = sum(x[1] for x in pre_ratios)
    add(f"- TB 26 tuần đầu {fmt(pre_first26)} → 26 tuần sau {fmt(pre_last26)} đơn vị/tuần "
        f"({fmt(100*(pre_last26/pre_first26-1))}%).")
    add(f"- TB bốn tuần cuối {fmt(pre_late4)} / TB 26 tuần ngay trước đó {fmt(pre_early26)} "
        f"= {fmt(pre_late4/pre_early26)}.")
    add()
    add("Chi tiết tỷ số chỉ dùng lịch sử trước chọn: tử số 09/11–06/12/2015; "
        "mẫu số 11/05–08/11/2015 (26 tuần liền trước, không chồng lấp).")
    add()
    table(["Sản phẩm", "TB tuần 26 tuần trước đó", "TB tuần 4 tuần cuối trước chọn", "Tỷ số 4/26"],
          [[item, fmt(early), fmt(late), fmt(ratio)] for item, early, late, ratio in pre_ratios])
    add(f"**Bằng chứng:** {sum(x[3] is not None and x[3] < 1 for x in pre_ratios)}/20 sản phẩm "
        "có mức bán bốn tuần sát ngày chọn thấp hơn 26 tuần đối chiếu. "
        "Cả 5 sản phẩm thuộc nhóm thưa đều có tổng bán bằng 0 trong bốn tuần sát ngày chọn "
        "(09/11–06/12/2015), dù tổng bán tích lũy vẫn đủ để nằm trong panel đã lưu. "
        "Slope cả năm gần 0 (-0.1768), trong khi trung bình nửa năm sau còn cao hơn nửa năm đầu "
        "6.0317%; vì vậy không mô tả cả năm trước chọn là một đợt giảm nhất quán. "
        "Các con số này chỉ mô tả mức giảm trước ngày chọn và sự khác biệt giữa sản phẩm. "
        "Tổng bán tích lũy cao không đồng nghĩa mức bán gần ngày chọn vẫn cao. "
        "**Suy đoán chưa được chứng minh:** chọn theo tổng lịch sử có thể giữ lại sản phẩm từng bán "
        "mạnh nhưng gần đây bán ít; chưa thể nói chính cách chọn gây giảm bán sau đó, "
        "hoặc quy giảm bán cho hết hàng, vòng đời, giá hay mùa vụ.")
    add()
    add("### 2.4. Tái lập và kiểm tra của phần bổ sung")
    add()
    add("Script [diagnose_supplement2.py](../../scripts/diagnose_supplement2.py) chỉ đọc ba CSV đầu vào, "
        "dùng thư viện chuẩn và numpy trong requirements, rồi in toàn bộ mục Bổ sung 2 ra stdout. "
        "Không ghi file từ trong script, không import code huấn luyện. Lệnh đã dùng:")
    add()
    add("```powershell\n.\\.venv\\Scripts\\python.exe scripts\\diagnose_supplement2.py > .runtime/supplement2.md\n```")
    add()
    add("Sau đó nối nội dung UTF-8 của `.runtime/supplement2.md` vào cuối `docs/review/DIAGNOSIS.md` "
        "một lần. Script có assert tính slope, khóa panel, actual khớp history, đủ 28 h cho từng "
        "sản phẩm/mô hình/split, origin đúng, seasonal naive khớp lặp tuần origin, "
        "đồng nhất thức bias ở mỗi nhóm và tổng test khớp bốn tuần. "
        "Không chạy unittest có fit/train; không dùng phân tích này để chọn cấu hình mới.")
    add()
    add("SHA-256 đầu vào phần bổ sung:")
    add()
    for path in paths:
        add(f"- `{path.relative_to(ROOT).as_posix()}`: `{hashlib.sha256(path.read_bytes()).hexdigest()}`")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
