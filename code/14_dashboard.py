"""Small CSV-only M5 demo. Run with streamlit run code/14_dashboard.py."""

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]


def load_data(folder):
    folder = Path(folder)
    reports = [json.loads((folder / path).read_text(encoding="utf-8")) for path in
               ("analysis/analysis_report.json", "forecast/forecast_report.json")]
    if any(report.get("status") != "success" for report in reports):
        raise ValueError("Kết quả chưa hoàn tất. Chạy lại bước 2 và 3.")
    if reports[0]["input"] != reports[1]["input"]:
        raise ValueError("Hai bước dùng nguồn khác nhau. Chạy lại với cùng đầu vào.")
    daily = pd.read_csv(folder / "analysis/daily_category_store.csv", parse_dates=["date"])
    history = pd.read_csv(folder / "forecast/history.csv", parse_dates=["date"])
    predictions = pd.read_csv(folder / "forecast/predictions.csv", parse_dates=["date", "origin_date"])
    metrics = pd.read_csv(folder / "forecast/metrics.csv")
    return daily, history, predictions, metrics, reports


def sales_summary(daily, store, category):
    selected = daily[daily.store_id == store]
    if category != "Tất cả":
        selected = selected[selected.cat_id == category]
    # min_count preserves unknown revenue, including days with no valid prices.
    return selected.groupby("date", as_index=False)[
        ["units", "rows", "priced_rows", "priced_units", "revenue_known"]].sum(min_count=1)


def main():
    st.set_page_config(page_title="M5 · Bán hàng và dự báo", layout="wide")
    st.title("Phân tích bán hàng và dự báo M5")
    st.caption("Spark tổng hợp dữ liệu lớn · Demo chỉ đọc các CSV nhỏ đã xuất")
    folder = st.sidebar.text_input("Thư mục kết quả", os.environ.get("M5_OUTPUT_DIR", str(ROOT / "outputs")))
    try:
        daily, history, predictions, metrics, reports = load_data(folder)
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as error:
        st.error(f"Không đọc được kết quả: {error}")
        st.info("Chạy code/12_spark_analysis.py và code/13_forecasting.py trước khi mở demo.")
        st.stop()
    stores = sorted(daily.store_id.unique())
    default_store = reports[1]["store_id"]
    store = st.sidebar.selectbox("Cửa hàng", stores,
                                 index=stores.index(default_store) if default_store in stores else 0)
    category = st.sidebar.selectbox("Nhóm sản phẩm (doanh thu)", ["Tất cả", *sorted(daily.cat_id.unique())])
    date_min, date_max = daily.date.min().date(), daily.date.max().date()
    dates = st.sidebar.date_input("Khoảng ngày doanh thu và lịch sử", (date_min, date_max),
                                  min_value=date_min, max_value=date_max)
    if len(dates) != 2:
        st.info("Chọn đủ ngày bắt đầu và kết thúc để xem biểu đồ.")
        return
    start, end = (pd.Timestamp(day) for day in dates)
    st.subheader(f"Doanh số và doanh thu · {store} · {category}")
    summary = sales_summary(daily, store, category)
    summary = summary[summary.date.between(start, end)]
    st.caption(f"Khoảng đang xem: {start:%d/%m/%Y} – {end:%d/%m/%Y}")
    totals = summary.drop(columns="date").sum(min_count=1)
    left, right = st.columns(2)
    left.metric("Lượng bán trong khoảng chọn", f"{totals['units']:,.0f}")
    revenue = totals["revenue_known"]
    coverage = totals["priced_rows"] / totals["rows"] if totals["rows"] else float("nan")
    right.metric("Bao phủ giá theo dòng", f"{coverage:.2%}")
    st.metric("Doanh thu biết giá", "Chưa biết" if pd.isna(revenue) else f"{revenue:,.2f}")
    unit_coverage = totals["priced_units"] / totals["units"] if totals["units"] else float("nan")
    st.caption(f"Bao phủ giá theo lượng bán: {unit_coverage:.2%}. Doanh thu theo đơn vị giá nguồn; "
               "giá thiếu không điền 0. Biểu đồ doanh thu là tổng phần biết giá, có thể chưa đầy đủ.")
    st.line_chart(summary, x="date", y="units", x_label="Ngày", y_label="Lượng bán")
    st.line_chart(summary, x="date", y="revenue_known", x_label="Ngày", y_label="Doanh thu biết giá")
    st.subheader("Dự báo lượng bán theo sản phẩm")
    items = sorted(history.loc[history.store_id == store, "item_id"].unique())
    if not items:
        st.info(f"Chưa có dự báo cho {store}. Bộ hiện tại có {reports[1]['series_count']} sản phẩm "
                f"của {default_store}. Chạy bước 3 với --store {store} để tạo dự báo cho cửa hàng này.")
        return
    item = st.sidebar.selectbox("Sản phẩm (dự báo)", items)
    split = st.sidebar.selectbox("Tập đánh giá", ["test", "validation"])
    selected_history = history[(history.store_id == store) & (history.item_id == item)]
    selected_history = selected_history[selected_history.date.between(start, end)]
    selected_predictions = predictions[(predictions.store_id == store) &
                                       (predictions.item_id == item) & (predictions.split == split)]
    selected_metrics = metrics[(metrics.store_id == store) & (metrics.split == split) &
                               metrics.item_id.isin([item, "ALL"])]
    st.caption(f"{item} · {split} · Mốc dự báo: {selected_predictions.origin_date.min():%d/%m/%Y} · "
               "28 ngày dự báo đệ quy, không cập nhật lượng bán thật trong cửa sổ.")
    if selected_history.empty:
        st.info("Sản phẩm không có lịch sử trong khoảng ngày đã chọn.")
    st.line_chart(selected_history, x="date", y="units", x_label="Ngày", y_label="Lịch sử lượng bán")
    comparison = selected_predictions.pivot(index="date", columns="model", values="prediction")
    comparison["actual"] = selected_predictions.groupby("date").actual.first()
    st.line_chart(comparison, x_label="Ngày", y_label="Lượng bán thực tế / dự báo")
    st.caption("seasonal_naive: lặp tuần trước · random_forest: hồi quy · actual: thực tế")
    st.dataframe(selected_metrics[["item_id", "model", "observations", "mae", "rmse"]],
                 hide_index=True, width="stretch")
    st.caption(f"ALL là sai số gộp {reports[1]['series_count']} sản phẩm được chọn bằng dữ liệu train; "
               "không phải sai số tổng cửa hàng. Biểu đồ dự báo và bảng sai số dùng đủ 28 ngày "
               "của tập đánh giá, độc lập với bộ lọc ngày doanh thu và lịch sử.")
    st.dataframe(comparison.reset_index(), hide_index=True, width="stretch")
    st.download_button("Tải CSV thực tế và dự báo", comparison.to_csv().encode("utf-8"),
                       file_name=f"{store}_{item}_{split}.csv", mime="text/csv")
    with st.expander("Cách đánh giá và giới hạn"):
        st.json({key: reports[1][key] for key in ("train", "validation", "test", "selected_params")})
        st.write("Chọn tham số bằng MAE validation, huấn luyện lại với train + validation rồi đánh giá test. "
                 "Đây là backtest có thực tế, chưa phải dự báo sau ngày cuối dữ liệu. "
                 "Chỉ dự báo lượng bán quan sát được, không ước lượng nhu cầu bị mất khi hết hàng. "
                 "Doanh thu ở trên thuộc toàn bộ sản phẩm trong nhóm/cửa hàng; dự báo chỉ thuộc panel đã chọn. "
                 "HDFS chưa được kiểm thử.")


if __name__ == "__main__":
    main()
