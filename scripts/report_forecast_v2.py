"""Render V2_RESULTS and CSV evidence from the completed frozen experiment, without fitting."""

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
import numpy as np
import forecast_v2 as v2
from run_forecast_v2 import PANELS, MODELS, VARIANTS, apply_variant, variant_metrics, read, verify_frozen, dump

METRICS = ("mae", "rmse", "bias_pct", "bias_units", "B_SN", "delta_bias", "normalized_rmse")


def aggregate(actual, prediction, known, baseline):
    # Arrays: folds, items, days. Normalize each item using its own pre-origin scale.
    scale = np.maximum(known.mean(axis=2), 1.)
    result = v2.v1.scores(actual, prediction)
    b_sn = float(np.sum(baseline) - np.sum(actual))
    result.update(B_SN=b_sn, delta_bias=result["bias_units"]-b_sn,
                  normalized_rmse=float(np.sqrt(np.mean(((prediction-actual)/scale[:, :, None])**2))))
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/forecast_v2")
    parser.add_argument("--docs", type=Path, default=ROOT / "docs/review")
    args = parser.parse_args()
    assert (args.output / "test_complete.json").is_file(), "Single final test pass not complete"
    frozen = verify_frozen(args.output)
    lines, summaries, seeds, horizons, origin_rows, panels = [], [], [], [], [], []

    def add(s=""):
        lines.append(s)

    def fmt(value):
        return "—" if value is None else f"{value:.4f}"

    def table(headers, rows):
        add("| " + " | ".join(headers) + " |")
        add("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            add("| " + " | ".join(map(str, row)) + " |")
        add()

    for store in ("CA_1", "CA_2"):
        for panel in PANELS:
            path = args.output / store / panel
            panel_meta = read(path / "panel.json")
            panels.append(panel_meta)
            with np.load(path / "validation_predictions.npz", allow_pickle=False) as archive:
                data = {name: archive[name] for name in archive.files}
            forecast = {name: data[name] for name in MODELS}
            if frozen["step2_permitted"]:
                for name in VARIANTS:
                    forecast[name] = apply_variant(data, name, frozen["panels"][panel]["k_by_seed"])
            forecast["v2_frozen"] = forecast[frozen["panels"][panel]["choice"]]
            for name, predictions in forecast.items():
                rows = variant_metrics(data, predictions, name)
                origin_rows.extend({"store": store, "panel": panel, **r} for r in rows)
            val_flags = np.asarray(data["flags"])
            groups = [("all", np.arange(13))] + [(str(g), np.arange(g, 13, 4)) for g in range(4)]
            if frozen["step2_permitted"]:
                groups.append(("exclude_zero_runs", np.flatnonzero(~val_flags)))
            for group, folds in groups:
                if not len(folds):
                    continue
                for name, predictions in forecast.items():
                    metric_rows = []
                    for s, seed in enumerate(v2.SEEDS):
                        metric = aggregate(data["actual"][folds], predictions[folds, s], data["known"][folds],
                                           forecast["seasonal_naive"][folds, s])
                        row = {"store": store, "panel": panel, "split": "validation", "group": group,
                               "origins": len(folds), "model": name, "seed": seed, **metric}
                        seeds.append(row)
                        metric_rows.append(row)
                        for h in range(28):
                            b = float(np.sum(predictions[folds, s, :, h] - data["actual"][folds, :, h]))
                            b_sn = float(np.sum(forecast["seasonal_naive"][folds, s, :, h] - data["actual"][folds, :, h]))
                            horizons.append({"store": store, "panel": panel, "split": "validation", "group": group,
                                "origins": len(folds), "seed": seed, "model": name, "horizon": h+1,
                                "bias_units": b, "bias_mean": b/(20*len(folds)), "B_SN": b_sn, "delta_bias": b-b_sn})
                    summaries.append({"store": store, "panel": panel, "split": "validation", "group": group,
                        "origins": len(folds), "model": name,
                        **{m: float(np.mean([r[m] for r in metric_rows])) if metric_rows[0][m] is not None else None
                           for m in METRICS}})
            with np.load(path / "test_predictions.npz", allow_pickle=False) as archive:
                test = {name: archive[name] for name in archive.files}
            for name in (n for n in test if n not in ("actual", "known")):
                metric_rows = []
                for s, seed in enumerate(v2.SEEDS):
                    metric = v2.metrics(test["actual"], test[name][s], test["known"], test["seasonal_naive"][s])
                    row = {"store": store, "panel": panel, "split": "test", "group": "all", "origins": 1,
                           "model": name, "seed": seed, **metric}
                    seeds.append(row)
                    metric_rows.append(row)
                    for h in range(28):
                        b = float(np.sum(test[name][s, :, h] - test["actual"][:, h]))
                        b_sn = float(np.sum(test["seasonal_naive"][s, :, h] - test["actual"][:, h]))
                        horizons.append({"store": store, "panel": panel, "split": "test", "group": "all",
                            "origins": 1, "seed": seed, "model": name, "horizon": h+1,
                            "bias_units": b, "bias_mean": b/20, "B_SN": b_sn, "delta_bias": b-b_sn})
                summaries.append({"store": store, "panel": panel, "split": "test", "group": "all", "origins": 1,
                    "model": name, **{m: float(np.mean([r[m] for r in metric_rows])) if metric_rows[0][m] is not None else None
                                      for m in METRICS}})

    add("# Kết quả thí nghiệm V2")
    add()
    add("Thiết kế đã xem trước: panel recent được gợi ý từ chẩn đoán hồi cứu trên CA_1 có test đã xem. "
        "CA_1 test là đối chiếu hồi cứu; CA_2 dùng nguyên cấu hình và quyết định đóng băng từ CA_1, "
        "không chọn lại bằng validation/test CA_2. Chỉ CA_2 test được xem là test tươi trong công việc này. "
        "Đã chạy một lượt test cuối cho cả hai cửa hàng, hai panel và ba seed; "
        "không chỉnh tham số/ngưỡng/feature sau khi xem test.")
    add()
    add("## Kết luận mô tả")
    add()
    def summary(store, panel, split, model):
        return next(r for r in summaries if r["store"]==store and r["panel"]==panel and
                    r["split"]==split and r["group"]=="all" and r["model"]==model)
    baseline_wins=sum(summary(s,p,t,"weekday_mean4")["mae"] < summary(s,p,t,"seasonal_naive")["mae"]
                      for s in ("CA_1","CA_2") for p in PANELS for t in ("validation","test"))
    test_wins=sum(summary(s,p,"test","direct_poisson")["mae"] < summary(s,p,"test","random_forest")["mae"]
                  for s in ("CA_1","CA_2") for p in PANELS)
    add(f"- Baseline mới có MAE thấp hơn seasonal_naive cũ ở {baseline_wins}/8 tổ hợp "
        "store/panel/split. Đây là đối chiếu cùng sản phẩm/ngày; bảng dưới ghi rõ mức thay đổi từng tổ hợp.")
    add(f"- Raw direct có MAE thấp hơn RF ở {test_wins}/4 tổ hợp test. Kết quả test này không được dùng "
        "để đảo quyết định validation; cổng chung đã trượt ở panel legacy CA_1 nên V2 frozen vẫn là RF.")
    rf=summary("CA_2","recent","test","random_forest")
    direct=summary("CA_2","recent","test","direct_poisson")
    add(f"- Trên test tươi CA_2/recent, raw direct MAE {fmt(direct['mae'])} so với RF {fmt(rf['mae'])} "
        f"({fmt(100*(direct['mae']/rf['mae']-1))}%), nhưng bias_pct là {fmt(direct['bias_pct'])}% "
        f"so với RF {fmt(rf['bias_pct'])}%. Giảm Δ có dấu không bảo đảm giảm |bias|.")
    add("- Đổi panel không cải thiện đồng đều: xem riêng metric recent và legacy dưới cùng RF. "
        "Hai tập sản phẩm khác nhau nên không diễn giải chênh lệch đó là tác động nhân quả của cách chọn.")
    add()
    add("## Cổng quyết định và cấu hình giữ lại")
    add()
    table(["Panel CA_1", "Origin Δ_direct < Δ_RF", "Điểm MAE RF", "Điểm MAE direct", "Tỷ số MAE", "Qua cổng"],
          [[panel, f"{g['wins']}/13", fmt(g["rf_score"]), fmt(g["direct_score"]), fmt(g["mae_ratio"]),
            "có" if g["passed"] else "không"] for panel, g in frozen["gates"].items()])
    add("Điểm chọn = trung vị origin trong từng nhóm sau trung bình metric ba seed, "
        "rồi trung vị bốn nhóm; Δ là chênh bias có dấu so với seasonal_naive. "
        "Cổng yêu cầu ít nhất 9/13 origin và tỷ số MAE ≤1.03 trên **cả hai** panel CA_1.")
    add()
    if frozen["step2_permitted"]:
        add("**Cổng đạt: đã thực hiện Bước 2.** Các k chỉ fit từ validation CA_1, "
            "mang nguyên sang panel cùng tên của CA_2. Điểm validation của k là in-sample đối với k, "
            "không phải kiểm tra độc lập và có thể lạc quan. Fallback không nhân k.")
        add()
        table(["Panel", "Lựa chọn đóng băng", "k seed42", "k seed43", "k seed44"],
            [[p, x["choice"]]+[fmt(k) for k in x["k_by_seed"]] for p,x in frozen["panels"].items()])
        for panel, x in frozen["panels"].items():
            add(f"Điểm chọn candidate Bước 2 — {panel}:")
            add()
            table(["Candidate", "Nhóm 0", "Nhóm 1", "Nhóm 2", "Nhóm 3", "Trung vị nhóm"],
                  [[name]+[fmt(s) for s in val["groups"]]+[fmt(val["score"])]
                   for name,val in x["candidate_scores"].items()])
    else:
        add("**Cổng không đạt: không thực hiện Bước 2.** Không fit k, không chọn sparse fallback, "
            "không đổi sang direct. `v2_frozen` giữ `random_forest` trên cả hai panel; "
            "raw direct vẫn được báo cáo như đối chứng, kể cả khi kém hơn. "
            "Do Bước 2 bị khóa, phân tích loại fold chuỗi 0 và các candidate hiệu chỉnh/fallback "
            "được ghi là không thực hiện, không ghi bằng số 0 hoặc coi là không có tác động.")
    add()
    add("Pipeline/dashboard mặc định vẫn là V1 và giữ nguyên CSV/JSON tại `outputs/forecast`; "
        "kết quả V2 nằm riêng trong `outputs/forecast_v2`. V1 trong các bảng là **RF hiện hành** "
        "window=180, depth=12, leaf=5, 100 cây; không phải RF cũ hơn `reference_test` "
        "và không phải toàn bộ chiến lược V1 chọn model theo sản phẩm. "
        "Không rerun grid search V1 để tạo một đối chứng khác. "
        "Bản đầy đủ V1 được bảo tồn ở `code/13_forecasting_v1.py`.")
    add()
    add("## Panel và giới hạn so sánh")
    add()
    table(["Cửa hàng", "Panel", "20 sản phẩm"],
          [[p["store"],p["panel"],", ".join(x["item_id"] for x in p["selected"])] for p in panels])
    for store in ("CA_1", "CA_2"):
        old = next(p for p in panels if p["store"]==store and p["panel"]=="legacy")
        new = next(p for p in panels if p["store"]==store and p["panel"]=="recent")
        overlap = len({x["item_id"] for x in old["selected"]} & {x["item_id"] for x in new["selected"]})
        add(f"- {store}: giao hai panel = {overlap}/20. Khác biệt metric giữa panel còn do khác "
            "thành phần sản phẩm, không được quy toàn bộ cho cải thiện thuật toán.")
    add()
    add("## So sánh V1 RF và phương án V2 đóng băng")
    add()
    add("Các metric là trung bình metric tính riêng cho seed 42,43,44; không phải metric của "
        "dự báo ensemble. Validation gộp 13 origin đếm lặp nhãn giữa các nhóm. "
        "Normalized RMSE dùng scale max(mean_28 trước mỗi origin,1) cho từng sản phẩm.")
    add()
    headline = [r for r in summaries if r["group"]=="all" and r["model"] in ("random_forest","v2_frozen")]
    table(["Store", "Panel", "Split", "Mô hình", "MAE", "RMSE", "Bias %", "B_SN", "Δ", "nRMSE"],
          [[r["store"],r["panel"],r["split"],"V1 RF" if r["model"]=="random_forest" else "V2 frozen"]+
           [fmt(r[m]) for m in ("mae","rmse","bias_pct","B_SN","delta_bias","normalized_rmse")] for r in headline])
    add("## Toàn bộ đối chứng trên validation gộp và test")
    add()
    table(["Store", "Panel", "Split", "Mô hình", "MAE", "RMSE", "Bias %", "B_SN", "Δ", "nRMSE"],
          [[r["store"],r["panel"],r["split"],r["model"]]+
           [fmt(r[m]) for m in ("mae","rmse","bias_pct","B_SN","delta_bias","normalized_rmse")]
           for r in summaries if r["group"]=="all" and r["model"]!="v2_frozen"])
    add("## Từng thay đổi giúp hoặc không giúp bao nhiêu")
    add()
    add("Chênh MAE = MAE mô hình − MAE RF cùng store/panel/split; âm là tốt hơn. "
        "Chênh bias = bias mô hình − bias RF, có dấu nên thấp hơn có thể thành dự báo thiếu. "
        "Các số test chỉ dùng mô tả hồi cứu, không quay lại chọn candidate.")
    add()
    effects = []
    for r in summaries:
        if r["group"]!="all" or r["model"] in ("random_forest","v2_frozen"):
            continue
        ref = next(x for x in summaries if all(x[k]==r[k] for k in ("store","panel","split","group"))
                   and x["model"]=="random_forest")
        effects.append([r["store"],r["panel"],r["split"],r["model"],fmt(r["mae"]-ref["mae"]),
                        fmt(100*(r["mae"]/ref["mae"]-1)),fmt(r["bias_units"]-ref["bias_units"])])
    table(["Store", "Panel", "Split", "Đối chứng", "Chênh MAE", "Chênh MAE %", "Chênh bias đơn vị"], effects)
    add("Riêng thay baseline: weekday_mean4 so với seasonal_naive cũ trên cùng sản phẩm/ngày:")
    add()
    baseline_effects=[]
    for store in ("CA_1","CA_2"):
        for panel in PANELS:
            for split in ("validation","test"):
                refs={m:next(r for r in summaries if r["store"]==store and r["panel"]==panel and
                    r["split"]==split and r["group"]=="all" and r["model"]==m)
                    for m in ("seasonal_naive","weekday_mean4")}
                old,new=refs["seasonal_naive"],refs["weekday_mean4"]
                baseline_effects.append([store,panel,split,fmt(new["mae"]-old["mae"]),
                    fmt(100*(new["mae"]/old["mae"]-1)),fmt(new["rmse"]-old["rmse"])])
    table(["Store","Panel","Split","Chênh MAE mới−cũ","Chênh MAE %","Chênh RMSE mới−cũ"],baseline_effects)
    add("Tác động thay panel được mô tả riêng dưới cùng RF (hai tập sản phẩm khác nhau, không phải "
        "thí nghiệm ghép cặp trên cùng nhãn):")
    add()
    panel_effects=[]
    for store in ("CA_1","CA_2"):
        for split in ("validation","test"):
            refs={p:next(r for r in summaries if r["store"]==store and r["split"]==split and
                         r["panel"]==p and r["group"]=="all" and r["model"]=="random_forest") for p in PANELS}
            panel_effects.append([store,split,fmt(refs["legacy"]["mae"]),fmt(refs["recent"]["mae"]),
                fmt(refs["recent"]["mae"]-refs["legacy"]["mae"]),
                fmt(refs["legacy"]["bias_pct"]),fmt(refs["recent"]["bias_pct"])])
    table(["Store","Split","RF legacy MAE","RF recent MAE","Chênh recent−legacy","Legacy bias %","Recent bias %"],panel_effects)
    add("## Kết quả theo bốn nhóm validation và phần gộp")
    add()
    add("Nhóm 0/1/2/3 có lần lượt 4/3/3/3 origin, trong nhóm nhãn không chồng. "
        "Các nhóm chồng lấp nhau: 13 origin không độc lập; không tính CI coi chúng độc lập. "
        "Bảng nhóm là metric gộp các điểm dự báo trong nhóm, khác điểm chọn trung vị nhóm đã ghi ở trên.")
    add()
    for store in ("CA_1","CA_2"):
        for panel in PANELS:
            add(f"### {store} / {panel}")
            add()
            table(["Nhóm","Mô hình","MAE","RMSE","Bias %","B_SN","Δ","nRMSE"],
                [[r["group"],r["model"]]+[fmt(r[m]) for m in ("mae","rmse","bias_pct","B_SN","delta_bias","normalized_rmse")]
                 for r in summaries if r["store"]==store and r["panel"]==panel and r["split"]=="validation"])
    if frozen["step2_permitted"]:
        add("## Độ nhạy với fold chứa chuỗi bán 0 ≥14 ngày")
        add()
        add("Chỉ gắn cờ dựa trên actual validation của top 10 theo tổng bán 26 tuần trước ngày chốt, "
            "không sử dụng sell_price, không gọi đây là hết hàng. Không thay train/predict hay cổng. "
            "Metric all và exclude_zero_runs của mọi candidate được báo cáo ở các bảng nhóm và CSV. "
            "Nếu không còn fold, metric bị bỏ trống thay vì tự điền 0.")
        add()
        flags=[]
        for store in ("CA_1","CA_2"):
            for panel in PANELS:
                with np.load(args.output/store/panel/"validation_predictions.npz",allow_pickle=False) as data:
                    ids=np.flatnonzero(data["flags"]).tolist()
                flags.append([store,panel,len(ids),", ".join(str(v2.origins()[i]) for i in ids) or "không có"])
        table(["Store","Panel","Số origin bị cờ","Origin"],flags)
    add("## Bằng chứng chi tiết và tái lập")
    add()
    add("- [V2_METRICS.csv](V2_METRICS.csv): metric trung bình ba seed theo store/panel/split/nhóm.")
    add("- [V2_SEED_METRICS.csv](V2_SEED_METRICS.csv): metric của từng seed (bao gồm normalized RMSE).")
    add("- [V2_ORIGIN_METRICS.csv](V2_ORIGIN_METRICS.csv): từng origin, seed, model; hỗ trợ đối chiếu cổng và trung vị.")
    add("- [V2_BIAS_BY_H.csv](V2_BIAS_BY_H.csv): đủ h=1..28, từng nhóm/gộp, store/panel/seed/model; "
        "bias_units là tổng có dấu, bias_mean chia cho số origin ×20, không phải bias lũy kế.")
    add("- [V2_FROZEN.json](V2_FROZEN.json): quyết định, k nếu được phép, cấu hình, hashes code và validation trước test.")
    add("- [V2_PANELS.json](V2_PANELS.json): danh sách rank/train_units/recent_units/last28_units của hai panel hai store.")
    add()
    add("Lệnh đã dùng theo thứ tự; test chỉ gọi một lần cuối, không chạy lại để chọn cấu hình:")
    add()
    add("```powershell\n.\\.venv\\Scripts\\python.exe scripts/run_forecast_v2.py prepare\n"
        ".\\.venv\\Scripts\\python.exe scripts/run_forecast_v2.py validate --store CA_1\n"
        ".\\.venv\\Scripts\\python.exe scripts/run_forecast_v2.py freeze\n"
        ".\\.venv\\Scripts\\python.exe scripts/run_forecast_v2.py validate --store CA_2\n"
        ".\\.venv\\Scripts\\python.exe scripts/run_forecast_v2.py test\n"
        ".\\.venv\\Scripts\\python.exe scripts/report_forecast_v2.py\n```")
    add()
    add("Không tự chạy lại trên output cũ: prepare/validation/freeze/test có guard tránh thay evidence; "
        "test_started.json được tạo trước đọc nhãn, test_complete.json chỉ có khi hoàn tất. "
        "Các forecast test được tạo từ history trước khi mở nhãn test. CA_2 validation chạy sau freeze, "
        "không dùng chỉnh quyết định. Thời điểm/hashes được lưu trong manifest và marker ở outputs. "
        "Dữ liệu/model lớn không đưa vào Git; cần nguồn Parquet và môi trường theo README để tái lập "
        "vào output mới, nhưng lượt CA_2 test sau đó không còn là test tươi.")
    add()
    add("Giới hạn: không kết luận nguyên nhân bán 0 hoặc suy bias giảm là sửa được nhu cầu tiềm ẩn. "
        "Đổi panel sau chẩn đoán là thiết kế đã xem trước. Chênh metric giữa panel chịu ảnh hưởng "
        "quy mô/thành phần; so thuật toán phải dùng cùng panel. Không phát biểu nhân quả từ các đối chứng này.")
    add()
    add("## Kiểm tra bàn giao")
    add()
    add("Bộ `python -m unittest discover -s tests -v` hiện có 24 test, gồm leakage mutation 1e9, "
        "đối chiếu selector Spark, nhãn train direct, cổng/nhóm, guard freeze/test một lần, "
        "schema và metric báo cáo, cùng các test dashboard/V1 cũ. Chạy trước và sau từng commit; "
        "không commit khi test đỏ. [V2_AUDIT.json](V2_AUDIT.json) lưu mốc freeze/test và kết quả "
        "đối chiếu 10080 dòng bias horizon với 360 seed summaries; cả 780 dòng metric từng origin "
        "được lưu để tính lại cổng. Artifact dashboard gốc được so hash trước/sau và không thay đổi. "
        "Bước 2 không chạy do cổng; các k=1 trong manifest là giá trị identity mặc định không fit/không áp dụng.")
    args.docs.mkdir(parents=True, exist_ok=True)
    for name, rows in (("V2_METRICS.csv",summaries),("V2_SEED_METRICS.csv",seeds),
                       ("V2_ORIGIN_METRICS.csv",origin_rows),("V2_BIAS_BY_H.csv",horizons)):
        v2.v1.write_csv(args.docs/name,rows)
    dump(args.docs/"V2_FROZEN.json",frozen)
    dump(args.docs/"V2_PANELS.json",panels)
    (args.docs/"V2_RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("Wrote V2_RESULTS.md and six evidence files",flush=True)


if __name__ == "__main__":
    main()
