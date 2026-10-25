"""Read V2 arrays and source demand; print Bổ sung 3, never train or modify inputs."""
import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import sys

import numpy as np
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
import forecast_v2 as v2


def max_zero_run(values):
    longest = run = 0
    for value in values:
        run = run + 1 if value == 0 else 0
        longest = max(longest, run)
    return longest


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reveal-after-test", action="store_true")
    args = parser.parse_args()
    if args.reveal_after_test and not (ROOT / "outputs/forecast_v3/test_complete.json").is_file():
        raise ValueError("New-store post-origin totals stay sealed until the single fresh test completes")
    lines = ["## Bổ sung 3", "", "Chẩn đoán chỉ đọc; tái dùng toàn bộ dự báo V2, không fit/predict lại. "
        "CA_1 và CA_2 test đều đã xem. Trung bình/tổng dự báo dưới đây đã lấy trung bình ba seed để "
        "tổng actual không bị đếm ba lần; contribution AE/SSE/NSSE lấy trung bình loss ba seed. "
        "Origin validation chồng giữa các nhóm; mọi tổng qua 13 origin là tổng lượt đánh giá, không phải "
        "tổng ngày duy nhất. Không kết luận nguyên nhân hoặc điều chỉnh cấu hình từ các bảng này.", ""]

    def add(s=""):
        lines.append(s)

    def f(x):
        return "—" if x is None else f"{x:.4f}"

    def table(headers, rows):
        add("| " + " | ".join(headers) + " |")
        add("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            add("| " + " | ".join(map(str, row)) + " |")
        add()

    def load(store, panel, split):
        folder = ROOT / "outputs/forecast_v2" / store / panel
        meta = json.loads((folder / "panel.json").read_text(encoding="utf-8"))
        with np.load(folder / f"{split}_predictions.npz", allow_pickle=False) as data:
            result = {k: data[k] for k in data.files}
        if split == "test":
            result = {k: x[None, ...] for k, x in result.items()}
        return [r["item_id"] for r in meta["selected"]], result

    add("### 3.1. Direct Poisson trên CA_2 legacy validation")
    add()
    items, data = load("CA_2", "legacy", "validation")
    actual, known = data["actual"], data["known"]
    direct, rf = data["direct_poisson"], data["random_forest"]
    ae = np.mean(np.abs(direct - actual[:, None]), axis=1).sum(axis=2)
    sse = np.mean((direct - actual[:, None])**2, axis=1).sum(axis=2)
    rf_ae = np.mean(np.abs(rf - actual[:, None]), axis=1).sum(axis=2)
    scales = np.maximum(known.mean(axis=2), 1.)
    add("Sản phẩm xếp theo SSE direct (không theo nhãn test mới):")
    add()
    top = np.argsort(sse.sum(axis=0))[::-1][:8]
    table(["Item", "% AE direct", "% SSE direct", "Chênh AE direct−RF", "Scale min..max", "Origin scale=1"],
        [[items[i], f(100*ae[:,i].sum()/ae.sum()), f(100*sse[:,i].sum()/sse.sum()),
          f((ae[:,i]-rf_ae[:,i]).sum()), f"{f(scales[:,i].min())}..{f(scales[:,i].max())}",
          int(np.sum(scales[:,i]==1))] for i in top])
    add("Mười cặp item/origin gây SSE lớn nhất:")
    add()
    pairs = [np.unravel_index(i, sse.shape) for i in np.argsort(sse.ravel())[::-1][:10]]
    table(["Item", "Origin", "Scale", "Ngày 0 trước origin", "Run 0 trước", "Tổng actual", "Tổng direct", "% SSE"],
        [[items[i], v2.origins()[o], f(scales[o,i]), int(np.sum(known[o,i]==0)), max_zero_run(known[o,i]),
          f(actual[o,i].sum()), f(direct[o,:,i].mean(axis=0).sum()), f(100*sse[o,i]/sse.sum())] for o,i in pairs])
    low = scales <= 1
    long = np.array([[max_zero_run(row)>=14 for row in origin] for origin in known])
    add(f"**Bằng chứng:** scale=1 ở {int(low.sum())}/260 cặp item/origin, chiếm "
        f"{f(100*sse[low].sum()/sse.sum())}% SSE direct; run 0 trước origin ≥14 ngày ở "
        f"{int(long.sum())}/260 cặp, chiếm {f(100*sse[long].sum()/sse.sum())}% SSE. "
        "Hai nhóm có thể giao nhau, không cộng tỷ lệ. Scale thấp và chuỗi 0 đi cùng một số sai số lớn "
        "là liên hệ mô tả; không đủ chứng minh chuẩn hóa hoặc hết hàng gây lỗi. "
        "Loss Poisson/feature/model có thể cùng tác động; không chạy ablation hay train lại để quy nguyên nhân.")
    add()
    add("### 3.2. Năm đóng góp lớn nhất vào normalized SSE của RF, panel recent")
    add()
    for store in ("CA_1", "CA_2"):
        for split in ("validation", "test"):
            items, data = load(store, "recent", split)
            scale = np.maximum(data["known"].mean(axis=2), 1.)
            nsse = np.mean(((data["random_forest"]-data["actual"][:,None]) / scale[:,None,:,None])**2,
                           axis=1).sum(axis=2)
            add(f"#### {store} / {split}")
            add()
            top = np.argsort(nsse.sum(axis=0))[::-1][:5]
            table(["Item", "% NSSE RF", "Scale min", "Scale median", "Scale max", "Tổng RF", "Tổng actual"],
                [[items[i],f(100*nsse[:,i].sum()/nsse.sum()),f(scale[:,i].min()),f(np.median(scale[:,i])),
                  f(scale[:,i].max()),f(data["random_forest"][:,:,i].mean(axis=1).sum()),
                  f(data["actual"][:,i].sum())] for i in top])
    add("NSSE là bình phương sai số sau chia scale, có thể cộng để tính tỷ trọng. nRMSE là căn MSE chuẩn hóa, "
        "không cộng tỷ trọng trực tiếp. Scale=1 khiến cùng sai số đơn vị có trọng số lớn hơn so với sản phẩm "
        "có mức bán quá khứ cao; đây là tính chất công thức, không tự chứng minh dự báo của item đó kém nhất "
        "theo MAE đơn vị hoặc nguyên nhân bán thấp.")
    add()
    add("### 3.3. Tập trung bias RF trên validation")
    add()
    for store in ("CA_1", "CA_2"):
        for panel in ("recent", "legacy"):
            items, data = load(store, panel, "validation")
            bias = (data["random_forest"].mean(axis=1)-data["actual"]).sum(axis=2)
            by_item = bias.sum(axis=0)
            total = float(by_item.sum())
            positive = float(np.maximum(by_item,0).sum())
            top = np.argsort(by_item)[::-1][:3]
            add(f"#### {store} / {panel}: bias tổng {f(total)}; tổng phần dư dương theo item {f(positive)}")
            add()
            table(["Item", "Bias", "% bias tổng có dấu", "% tổng phần dư dương"],
                  [[items[i],f(by_item[i]),f(100*by_item[i]/total) if total else "—",
                    f(100*by_item[i]/positive) if positive else "—"] for i in top])
            last28 = data["known"].sum(axis=2)
            low, zero = last28 <= 28, last28 == 0
            add(f"Top 3 cộng: {f(by_item[top].sum())} = {f(100*by_item[top].sum()/total)}% bias tổng. "
                f"Cặp item/origin last28_units≤28: {int(low.sum())}/260, bias {f(bias[low].sum())} "
                f"({f(100*bias[low].sum()/total)}% tổng); riêng last28=0: {int(zero.sum())}/260, "
                f"bias {f(bias[zero].sum())} ({f(100*bias[zero].sum()/total)}%). "
                "Nhóm đúng 0 nằm trong nhóm ≤28. Bias có dấu có thể bù trừ; tỷ trọng không phải phần MAE. "
                "Ngưỡng ≤28 chỉ mô tả, không dùng chọn rule hoặc tham số.")
            add()
    add("### 3.4. Tổng tuần cùng giỏ 20 item quanh 27/03/2016")
    add()
    add("Giỏ cố định = 20 item CA_1 legacy, dùng ở mọi store; không phải toàn store hoặc panel riêng của store. "
        "Tuần Thứ hai–Chủ nhật, t=−3..0: 29/02–27/03; t=1..4: 28/03–24/04/2016. "
        "Bốn tuần sau tại store chưa dùng được giữ kín đến khi lượt test V3 hoàn tất.")
    add()
    source = ds.dataset(str(ROOT / "GuiDat/data/processed_m5"), format="parquet", exclude_invalid_files=True)
    basket = json.loads((ROOT / "outputs/forecast_v2/CA_1/legacy/panel.json").read_text())["selected"]
    basket = [r["item_id"] for r in basket]
    start, origin, end = date(2016,2,29), v2.TEST_ORIGIN, date(2016,4,24)
    condition = ds.field("item_id").isin(basket) & (ds.field("date") >= start) & (ds.field("date") <= end)
    if not args.reveal_after_test:
        condition = condition & ((ds.field("date") <= origin) | ds.field("store_id").isin(["CA_1","CA_2"]))
    rows = source.to_table(columns=["store_id","item_id","date","demand"],filter=condition).to_pylist()
    stores = sorted({r["store_id"] for r in rows})
    totals = {}
    counts = {}
    for row in rows:
        week = (row["date"]-start).days//7-3
        key = row["store_id"], week
        totals[key] = totals.get(key,0) + row["demand"]
        counts[key] = counts.get(key,0) + 1
    assert all(count==140 for count in counts.values()), "Basket daily coverage missing/duplicated"
    table(["Store"]+[f"t={t}" for t in range(-3,5)],
          [[store]+[totals.get((store,t),"giữ kín") for t in range(-3,5)] for store in stores])
    if args.reveal_after_test:
        add("Bốn tuần sau của các store chưa dùng chỉ được đọc cho bảng này **sau** test_complete V3. "
            "Đây là mô tả sau đánh giá; không dùng thay ứng viên/thủ tục/cổng. "
            "Cùng biến động giữa store có thể là bối cảnh chung, nhưng không đủ kết luận nhân quả "
            "về lễ, giá, tồn kho hoặc nhu cầu tiềm ẩn.")
    else:
        add("**Chưa công bố bốn tuần sau tại store mới** để bảo vệ test tươi; bổ sung sau test_complete. "
            "Các tổng không có danh tính khách hàng hay dữ liệu tồn kho; không dùng chúng quy nguyên nhân.")
    add()
    add("Tái lập: `.venv/Scripts/python.exe scripts/diagnose_supplement3.py`; "
        "thêm `--reveal-after-test` chỉ sau khi guard V3 báo hoàn tất. Script chỉ đọc và in stdout. "
        "Không train lại V2; không sử dụng sell_price hoặc mask bán 0.")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
