"""CSV-only M5 dashboard. Run with streamlit run code/14_dashboard.py."""

import json
import hashlib
import math
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["Tổng quan bán hàng", "Dự báo sản phẩm", "Kiểm tra độ tin cậy"]
LABELS = {"selected_forecast": "Dự báo cuối", "blend": "Dự báo cuối",
          "random_forest": "Random Forest (RF)", "weekday_mean4": "Trung bình 4 tuần cùng thứ",
          "seasonal_naive": "Lặp tuần trước", "rf_calibrated": "RF nhân hệ số"}
COLORS = {"Lịch sử": "#64748b", "Dự báo cuối": "#7057f5", "Thực tế": "#d97706",
          "Random Forest (RF)": "#30bda0", "Trung bình 4 tuần cùng thứ": "#e9ad38",
          "Lặp tuần trước": "#3b82f6"}


def load_data(folder):
    folder = Path(folder)
    reports = [json.loads((folder / path).read_text(encoding="utf-8")) for path in
               ("analysis/analysis_report.json", "forecast/forecast_report.json")]
    if any(report.get("status") != "success" for report in reports):
        raise ValueError("Kết quả chưa hoàn tất. Cần bộ kết quả đã xuất thành công.")
    if reports[0]["input"] != reports[1]["input"]:
        raise ValueError("Hai bước dùng nguồn khác nhau. Cần bộ kết quả cùng đầu vào.")
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


def previous_period(summary, start, end):
    """Only compare complete calendar periods, including zero-sales days."""
    length = (end - start).days + 1
    previous_start = start - pd.Timedelta(days=length)
    previous_end = start - pd.Timedelta(days=1)
    selected = summary[summary.date.between(start, end)]
    previous = summary[summary.date.between(previous_start, previous_end)]
    complete = (len(selected) == length and len(previous) == length)
    return previous if complete else None


def forecast_tables(predictions):
    comparison = predictions.pivot(index="date", columns="model", values="prediction").sort_index()
    comparison["actual"] = predictions.groupby("date").actual.first()
    weekly = comparison[["selected_forecast"]].copy()
    weekly["Tuần"] = ((weekly.index - weekly.index.min()).days // 7) + 1
    weekly = weekly.reset_index().groupby("Tuần").agg(
        start=("date", "min"), end=("date", "max"), forecast=("selected_forecast", "sum"))
    weekly["Khoảng ngày"] = weekly.start.dt.strftime("%d/%m/%Y") + " – " + weekly.end.dt.strftime("%d/%m/%Y")
    return comparison, weekly[["Khoảng ngày", "forecast"]].rename(columns={"forecast": "Dự báo cuối"})


def evaluation_tables(predictions):
    """Use exported predictions for both V1 and V2, without fitting or selecting."""
    rows = predictions.copy()
    rows["error"] = rows.prediction - rows.actual
    rows["absolute"] = rows.error.abs()
    rows["squared"] = rows.error ** 2
    summary = rows.groupby("model").agg(mae=("absolute", "mean"), mse=("squared", "mean"),
                                        actual=("actual", "sum"), predicted=("prediction", "sum"))
    summary["rmse"] = summary.pop("mse") ** .5
    summary["bias"] = summary.predicted - summary.actual
    summary["bias_pct"] = summary.bias / summary.actual.replace(0, float("nan")) * 100
    items = rows[rows.model == "selected_forecast"].groupby("item_id").agg(
        actual=("actual", "sum"), predicted=("prediction", "sum"), mae=("absolute", "mean"))
    items["bias"] = items.predicted - items.actual
    return summary, items


def number(value, digits=0):
    if pd.isna(value):
        return "Chưa biết"
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def supply_gap(forecast, usable_stock, confirmed_incoming):
    values = (forecast, usable_stock, confirmed_incoming)
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Lượng dự báo, tồn dùng được và hàng về phải là số không âm.")
    return max(0., forecast - usable_stock - confirmed_incoming)


def planning_scenario(comparison, scope):
    if st.session_state.get("planning_scope") != scope:
        for key in ("planning_enabled", "planning_stock", "planning_incoming"):
            st.session_state.pop(key, None)
        st.session_state["planning_scope"] = scope
    with st.expander("Tham khảo kế hoạch hàng hóa trong 28 ngày"):
        st.write("Dùng tổng dự báo và bảng bốn tuần để kiểm tra lượng hàng có thể đáp ứng. "
                 "Đây là tình huống mô phỏng tại ngày lập dự báo trong quá khứ.")
        st.caption("Bộ dữ liệu không có tồn kho. Nếu có số giả định phù hợp với mốc mô phỏng, bạn có thể nhập để xem chênh lệch.")
        complete = (len(comparison) == 28 and
                    comparison.index.max() - comparison.index.min() == pd.Timedelta(days=27))
        if not complete:
            st.info("Chưa đủ 28 ngày liên tiếp để lập tình huống hàng hóa.")
            return
        if st.checkbox("Nhập số giả định để tính thử", key="planning_enabled"):
            left, right = st.columns(2)
            stock = left.number_input("Tồn kho có thể dùng tại ngày lập dự báo", min_value=0., step=1., key="planning_stock")
            incoming = right.number_input("Hàng chắc chắn về trong 28 ngày", min_value=0., step=1., key="planning_incoming")
            total = float(comparison.selected_forecast.sum())
            gap = supply_gap(total, stock, incoming)
            st.metric("Lượng còn thiếu so với tổng dự báo", number(gap, 1), help="Tối đa của 0 và tổng dự báo trừ tồn dùng được trừ hàng chắc chắn về.")
            st.caption(f"Tính thử: {number(total, 1)} dự báo − {number(stock, 1)} tồn − {number(incoming, 1)} hàng về; lấy 0 nếu kết quả âm.")
            st.write("Chênh lệch này chưa phải lượng cần đặt hàng. Chưa xét ngày hàng về, thời gian giao hàng, "
                     "tồn an toàn, hạn dùng, quy cách đóng gói hoặc chi phí. Hàng về muộn vẫn có thể không đáp ứng kịp từng ngày.")


def hdfs_verification(folder):
    path = Path(folder) / "analysis_hdfs"
    try:
        proof = json.loads((path / "verification.json").read_text(encoding="utf-8"))
        report_bytes = (path / "analysis_report.json").read_bytes()
        report = json.loads(report_bytes)
        if (proof.get("status") == "verified" and report.get("status") == "success"
                and report.get("input_mode") == "hdfs"
                and proof.get("report_sha256") == hashlib.sha256(report_bytes).hexdigest()):
            return proof
    except (OSError, ValueError):
        pass
    return None


def chart_data(frame):
    # Inline values avoid stale Arrow dataset references when changing pages or series.
    return alt.Data(values=json.loads(frame.to_json(orient="records", date_format="iso")))


def overview(daily):
    st.header(PAGES[0])
    st.caption("Theo dõi lượng bán, doanh thu có giá và cơ cấu nhóm hàng trong khoảng đang chọn.")
    with st.container(border=True, key="filters"):
        a, b, c = st.columns([1, 1, 1.5])
        store = a.selectbox("Cửa hàng bán hàng", sorted(daily.store_id.unique()), key="sales_store")
        categories = sorted(daily.loc[daily.store_id == store, "cat_id"].unique())
        category = b.selectbox("Nhóm hàng", ["Tất cả", *categories])
        summary = sales_summary(daily, store, category)
        date_min, date_max = summary.date.min().date(), summary.date.max().date()
        dates = c.date_input("Khoảng ngày bán hàng", (date_min, date_max),
                             min_value=date_min, max_value=date_max, format="DD/MM/YYYY")
    if len(dates) != 2:
        st.info("Chọn đủ ngày bắt đầu và kết thúc.")
        return
    start, end = map(pd.Timestamp, dates)
    selected = summary[summary.date.between(start, end)]
    if selected.empty:
        st.info("Không có dữ liệu trong khoảng đang chọn.")
        return
    totals = selected.drop(columns="date").sum(min_count=1)
    previous = previous_period(summary, start, end)
    delta = None if previous is None else f"{number(totals['units'] - previous.units.sum())} đơn vị so với kỳ trước"
    coverage = totals.priced_rows / totals.rows if totals.rows else float("nan")
    unit_coverage = totals.priced_units / totals.units if totals.units else float("nan")
    with st.container(key="kpis"):
        left, middle, right = st.columns(3)
        left.metric("Tổng lượng bán", number(totals.units), delta, delta_color="off")
        middle.metric("Doanh thu biết giá", number(totals.revenue_known, 2))
        right.metric("Tỷ lệ dòng có giá", "Chưa biết" if pd.isna(coverage) else f"{number(coverage * 100, 2)}%")
    st.caption(f"{store} · {category} · {start:%d/%m/%Y} – {end:%d/%m/%Y} · "
               f"Bao phủ giá theo lượng bán: {number(unit_coverage * 100, 2)}%. Doanh thu theo đơn vị giá nguồn; giá thiếu không điền 0.")
    weekly = selected.set_index("date").resample("W-SUN", label="left", closed="right").units.sum().rename("Lượng bán")
    # W-SUN left labels are Sundays; shift to the Monday starting each bucket.
    weekly.index += pd.Timedelta(days=1)
    groups = daily[(daily.store_id == store) & daily.date.between(start, end)]
    if category != "Tất cả":
        groups = groups[groups.cat_id == category]
    ranking = groups.groupby("cat_id").units.sum().sort_values(ascending=False)
    chart_col, mix_col = st.columns([2, 1], gap="medium")
    with chart_col, st.container(border=True, key="sales_trend"):
        st.subheader("Xu hướng lượng bán")
        st.caption("Tổng theo tuần · Thứ Hai đến Chủ nhật · Tuần ở hai đầu có thể chưa đủ ngày.")
        base = alt.Chart(chart_data(weekly.reset_index())).encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%m/%Y", tickCount=6, labelAngle=0)),
            y=alt.Y("Lượng bán:Q", title="Đơn vị"),
            tooltip=[alt.Tooltip("date:T", title="Tuần bắt đầu", format="%d/%m/%Y"), "Lượng bán:Q"])
        chart = base.mark_area(color="#7057f5", opacity=.12) + base.mark_line(color="#7057f5", strokeWidth=2)
        st.altair_chart(chart.properties(height=290), use_container_width=True, key="sales_chart")
    with mix_col, st.container(border=True, key="sales_mix"):
        st.subheader("Cơ cấu lượng bán")
        st.caption("Tỷ trọng nhóm hàng trong phạm vi đang chọn.")
        rank_table = ranking.rename_axis("Nhóm hàng").rename("Lượng bán").reset_index()
        if totals.units > 0:
            donut = alt.Chart(chart_data(rank_table)).mark_arc(innerRadius=58, outerRadius=85).encode(
                theta="Lượng bán:Q", color=alt.Color("Nhóm hàng:N", title=None,
                    scale=alt.Scale(range=["#7057f5", "#30bda0", "#f5b94c"]),
                    legend=alt.Legend(orient="bottom", direction="horizontal")),
                tooltip=["Nhóm hàng:N", "Lượng bán:Q"])
            st.altair_chart(donut.properties(height=240), use_container_width=True, key="category_mix")
        else:
            st.info("Không có lượng bán để tính tỷ trọng.")
        st.dataframe(rank_table, hide_index=True, width="stretch", column_config={
            "Nhóm hàng": st.column_config.TextColumn(width=110),
            "Lượng bán": st.column_config.NumberColumn(width=110, format="%d")})
        share = f"{number(ranking.iloc[0] / totals.units * 100, 1)}%" if totals.units else "chưa xác định tỷ trọng"
        st.caption(f"{ranking.index[0]} bán {number(ranking.iloc[0])} đơn vị, chiếm {share} lượng bán đang xem. "
                   "Chưa có xếp hạng từng sản phẩm toàn cửa hàng trong dữ liệu tổng hợp.")
    with st.container(border=True, key="period_comparison"):
        st.subheader("So với kỳ trước")
        if previous is None:
            st.info("Chưa đủ dữ liệu cho hai khoảng liên tiếp có cùng số ngày để so sánh.")
        else:
            old = previous.drop(columns="date").sum(min_count=1)
            st.write(f"{previous.date.min():%d/%m/%Y} – {previous.date.max():%d/%m/%Y}: "
                     f"lượng bán {number(old.units)} → {number(totals.units)} đơn vị; "
                     f"doanh thu biết giá {number(old.revenue_known, 2)} → {number(totals.revenue_known, 2)}.")
            st.caption(f"Tỷ lệ dòng có giá: {number(old.priced_rows / old.rows * 100, 2) if old.rows else 'chưa biết'}% → "
                       f"{number(coverage * 100, 2)}%. Hai số doanh thu có thể có mức bao phủ giá khác nhau.")


def forecast_scope(predictions, choose_item=False):
    available = predictions[predictions.model == "selected_forecast"]
    if available.empty:
        st.info("Bộ kết quả chưa có dự báo cuối để hiển thị.")
        return available
    with st.container(border=True, key="filters"):
        columns = st.columns(3 if choose_item else 2)
        store = columns[0].selectbox("Cửa hàng có dự báo", sorted(available.store_id.unique()))
        splits = sorted(available.loc[available.store_id == store, "split"].unique(), key=lambda x: x != "test")
        split = columns[1].selectbox("Khoảng đánh giá cố định", splits,
                                     format_func=lambda x: {"test": "Kiểm tra cuối (test)",
                                                            "validation": "Phát triển (validation)"}.get(x, x))
        series = available[(available.store_id == store) & (available.split == split)]
        selected = predictions[(predictions.store_id == store) & (predictions.split == split) &
                               predictions.item_id.isin(series.item_id)]
        if choose_item:
            item = columns[2].selectbox("Sản phẩm có dự báo", sorted(series.item_id.unique()))
            selected = selected[selected.item_id == item]
    return selected


def period_caption(selected):
    origin = selected.origin_date.min()
    start, end = selected.date.min(), selected.date.max()
    st.info(f"Mô phỏng dự báo trong quá khứ · Ngày lập dự báo: {origin:%d/%m/%Y} · "
            f"Khoảng dự báo: {start:%d/%m/%Y} – {end:%d/%m/%Y}.")
    if selected.split.iloc[0] == "validation":
        st.caption("Validation là dữ liệu dùng khi phát triển. Cửa sổ hiển thị là lần cuối, đã tham gia lựa chọn; không phải kiểm tra độc lập.")


def product_forecast(history, predictions, report):
    st.header(PAGES[1])
    st.caption("Ước lượng lượng bán của một sản phẩm trong 28 ngày và phân bổ theo từng tuần.")
    selected = forecast_scope(predictions, choose_item=True)
    if selected.empty:
        return
    item = selected.item_id.iloc[0]
    period_caption(selected)
    comparison, weekly = forecast_tables(selected)
    origin = selected.origin_date.min()
    past = history[(history.store_id == selected.store_id.iloc[0]) & (history.item_id == item) & (history.date <= origin)]
    last28 = past[past.date > origin - pd.Timedelta(days=28)]
    complete = len(last28.date.unique()) == 28
    total = comparison.selected_forecast.sum()
    with st.container(key="kpis"):
        a, b, c = st.columns(3)
        a.metric("Tổng dự báo 28 ngày", number(total, 1))
        b.metric("Trung bình mỗi ngày", number(total / len(comparison), 1))
        c.metric("Lượng bán 28 ngày trước", number(last28.units.sum()) if complete else "Chưa đủ dữ liệu",
                 f"{number(total - last28.units.sum(), 1)} đơn vị dự báo so với kỳ trước" if complete else None, delta_color="off")
    if len(comparison) != 28:
        st.warning(f"Bộ kết quả chỉ có {len(comparison)} ngày; các tổng ở đây chỉ bao gồm số ngày có sẵn.")
    chart_col, week_col = st.columns([2, 1], gap="medium")
    with chart_col, st.container(border=True, key="forecast_trend"):
        st.subheader(f"Lịch sử và dự báo · {item}")
        st.caption("56 ngày lịch sử · Vùng nền tím là khoảng dự báo · Đơn vị bán / ngày")
        actual = st.checkbox("Xem thực tế để đối chiếu", value=False)
        st.caption("Tích phương pháp muốn hiện ngay trên biểu đồ này. Tổng và bảng tuần vẫn dùng Dự báo cuối.")
        models = [model for model in ("selected_forecast", "random_forest", "weekday_mean4", "seasonal_naive")
                  if model in comparison.columns]
        options = st.columns(2)
        shown = [model for index, model in enumerate(models)
                 if options[index % 2].checkbox(LABELS[model], value=model == "selected_forecast",
                                               key=f"compare_{model}")]
        recent = past[past.date > origin - pd.Timedelta(days=56)]
        plot = recent[["date", "units"]].rename(columns={"units": "Lượng bán"}).assign(Loại="Lịch sử")
        for model in shown:
            forecast = comparison[[model]].rename(columns={model: "Lượng bán"}).reset_index().assign(Loại=LABELS[model])
            if not recent.empty:
                bridge = pd.DataFrame({"date": [recent.date.max()], "Lượng bán": [recent.units.iloc[-1]], "Loại": [LABELS[model]]})
                forecast = pd.concat([bridge, forecast])
            plot = pd.concat([plot, forecast])
        if actual:
            plot = pd.concat([plot, comparison[["actual"]].rename(columns={"actual": "Lượng bán"}).reset_index().assign(Loại="Thực tế")])
        if not shown and not actual:
            st.info("Tích ít nhất một phương pháp hoặc bật thực tế để xem trong vùng dự báo. Lịch sử vẫn được giữ lại.")
        series = ["Lịch sử", *[LABELS[model] for model in shown], *(["Thực tế"] if actual else [])]
        shade = alt.Chart(alt.Data(values=[{"start": comparison.index.min().isoformat(), "end": (comparison.index.max() + pd.Timedelta(days=1)).isoformat()}])).mark_rect(color="#7057f5", opacity=.08).encode(x="start:T", x2="end:T")
        line = alt.Chart(chart_data(plot)).mark_line(strokeWidth=2.5).encode(
            x=alt.X("date:T", title="Ngày", axis=alt.Axis(format="%d/%m", tickCount=8, labelAngle=0)), y=alt.Y("Lượng bán:Q", title="Đơn vị", scale=alt.Scale(zero=True)),
            color=alt.Color("Loại:N", scale=alt.Scale(domain=series, range=[COLORS[name] for name in series]), title=None, legend=alt.Legend(orient="bottom", direction="horizontal")),
            tooltip=[alt.Tooltip("date:T", title="Ngày", format="%d/%m/%Y"), "Loại:N", alt.Tooltip("Lượng bán:Q", format=".1f")])
        st.altair_chart((shade + line).properties(height=310), use_container_width=True,
                        key=f"forecast_{selected.store_id.iloc[0]}_{item}_{selected.split.iloc[0]}_{actual}")
        if recent.empty:
            st.caption("Không có lịch sử trước mốc dự báo trong bộ kết quả này.")
    with week_col, st.container(border=True, key="forecast_weeks"):
        st.subheader("Phân bổ theo tuần")
        st.caption("Mỗi tuần là 7 ngày, tính từ ngày đầu dự báo.")
        weeks_plot = weekly.reset_index()
        weeks_plot["Nhãn tuần"] = "Tuần " + weeks_plot["Tuần"].astype(str)
        bars = alt.Chart(chart_data(weeks_plot)).mark_bar(color="#7057f5", cornerRadiusEnd=4, size=18).encode(
            y=alt.Y("Nhãn tuần:N", title=None, sort=None),
            x=alt.X("Dự báo cuối:Q", title="Đơn vị"),
            tooltip=["Nhãn tuần:N", "Khoảng ngày:N", alt.Tooltip("Dự báo cuối:Q", format=".1f")])
        st.altair_chart(bars.properties(height=210), use_container_width=True, key="weekly_forecast")
        display_weeks = weekly.reset_index().round(1)
        display_weeks["Khoảng ngày"] = display_weeks["Khoảng ngày"].str.replace(r"/\d{4}", "", regex=True)
        st.dataframe(display_weeks, hide_index=True, width="stretch", column_config={
            "Tuần": st.column_config.NumberColumn(width=40),
            "Khoảng ngày": st.column_config.TextColumn(width=115),
            "Dự báo cuối": st.column_config.NumberColumn(width=90, format="%.1f")})
        export = comparison.rename(columns={**LABELS, "actual": "Thực tế"}).rename_axis("Ngày")
        st.download_button("Tải CSV dự báo và đối chiếu", export.to_csv().encode("utf-8-sig"),
                           file_name=f"{selected.store_id.iloc[0]}_{item}_{selected.split.iloc[0]}.csv", mime="text/csv", width="stretch")
        st.caption("CSV gồm thực tế và các cách đối chứng, kể cả đường đang ẩn.")
    with st.container(border=True, key="forecast_explainer"):
        if report.get("selected_candidate") == "blend":
            st.write("Dự báo cuối lấy 50% từ Random Forest (RF, mô hình học từ lịch sử) và 50% từ trung bình 4 tuần cùng thứ. "
                     "Ví dụ RF đoán 14, cách cùng thứ đoán 10 thì kết quả cuối là 12. Đây là ví dụ giải thích, không phải số của sản phẩm đang chọn.")
        else:
            choice = report.get("selected_models", {}).get(item, report.get("selected_candidate", ""))
            st.write(f"Dự báo cuối dùng {LABELS.get(choice, choice) or 'cách đã chọn trong bộ kết quả'}. Lựa chọn được giữ nguyên từ bước phát triển.")
    planning_scenario(comparison, (selected.store_id.iloc[0], item, selected.split.iloc[0], str(origin)))


def research_results():
    st.subheader("Kết quả nghiên cứu tại ba cửa hàng")
    st.caption("Bảng riêng này là trung bình chỉ số của ba lần chạy, khác số demo một lần chạy ở trên. Hai nhóm sản phẩm được chọn theo lịch sử gần đây và theo cách cũ.")
    path = ROOT / "resources/v3_test_metrics.csv"
    try:
        research = pd.read_csv(path)
        table = research[["store", "panel", "model", "mae", "rmse", "bias_pct", "normalized_rmse"]].copy()
    except (OSError, ValueError, KeyError, pd.errors.ParserError):
        st.info("Chưa đọc được bảng nghiên cứu ba cửa hàng. Số demo ở trên vẫn dùng được.")
        return
    table["model"] = table.model.map(LABELS).fillna(table.model)
    table["panel"] = table.panel.replace({"recent": "Lịch sử gần đây", "legacy": "Cách chọn cũ"})
    st.dataframe(table.rename(columns={"store": "Cửa hàng", "panel": "Nhóm sản phẩm", "model": "Cách dự báo",
                                     "mae": "Sai lệch trung bình", "rmse": "RMSE", "bias_pct": "Dư/thiếu (%)",
                                     "normalized_rmse": "Sai số theo mức bán"}).round(4), hide_index=True, width="stretch", height=460)
    st.write("Cả ba cửa hàng đạt điều kiện đã đặt trước: dự báo cuối không tăng sai lệch trung bình và độ lớn dư/thiếu so với RF ở cả hai nhóm sản phẩm. Điều kiện chấp nhận yêu cầu ít nhất hai trong ba cửa hàng đạt.")
    st.write("Vẫn có kết quả kém RF: RMSE tại CA_3, nhóm lịch sử gần đây, tăng 16,9674 → 17,0023. "
             "Sai số theo mức bán tại TX_1, nhóm cách chọn cũ, tăng 1,8865 → 1,9206. Chỉ số sau chia sai số theo mức bán gần đây từng sản phẩm; không phải phần trăm chính xác.")


def reliability(predictions):
    st.header(PAGES[2])
    st.caption("Đối chiếu dự báo với thực tế, kiểm tra sai lệch và những sản phẩm dư hoặc thiếu nhiều.")
    selected = forecast_scope(predictions)
    if selected.empty:
        return
    period_caption(selected)
    summary, items = evaluation_tables(selected)
    final = summary.loc["selected_forecast"]
    with st.container(key="kpis"):
        a, b = st.columns(2)
        a.metric("Sai lệch trung bình · Dự báo cuối", number(final.mae, 2), help="Đơn vị / sản phẩm / ngày")
        b.metric("Tổng dự báo dư/thiếu", number(final.bias, 1), help="Tổng dự báo trừ tổng thực tế. Dương: dư; âm: thiếu.")
    compare_col, chart_col = st.columns([1.6, 1], gap="medium")
    table = summary.reindex([m for m in LABELS if m in summary.index]).rename(index=LABELS)
    with compare_col, st.container(border=True, key="reliability_table"):
        st.subheader("So sánh các cách dự báo")
        st.caption("Cùng bộ sản phẩm · Cùng khoảng đánh giá · Số của một lần chạy")
        st.dataframe(table[["mae", "rmse", "bias", "bias_pct"]].rename_axis("Cách dự báo").reset_index().rename(
            columns={"mae": "Sai lệch trung bình", "rmse": "RMSE", "bias": "Dư/thiếu (đơn vị)", "bias_pct": "Dư/thiếu (%)"}).round(2), hide_index=True, width="stretch")
        st.caption("MAE là trung bình lệch bao nhiêu đơn vị mỗi sản phẩm mỗi ngày. MAE = 8 là lệch 8 đơn vị, không phải chính xác 92%. RMSE phạt nặng những lần lệch nhiều.")
        st.caption("Dư/thiếu = tổng dự báo trừ thực tế; dương là dư, âm là thiếu. % chia cho tổng thực tế, để trống khi tổng bằng 0. Sản phẩm dư có thể bù sản phẩm thiếu.")
    with chart_col, st.container(border=True, key="reliability_chart"):
        st.subheader("Sai lệch trung bình")
        st.caption("Thanh ngắn hơn nghĩa là lệch ít hơn · Đơn vị / sản phẩm / ngày")
        mae_table = table.reset_index().rename(columns={"model": "Cách dự báo", "mae": "Sai lệch"})
        bars = alt.Chart(chart_data(mae_table)).mark_bar(cornerRadiusEnd=4, size=22).encode(
            y=alt.Y("Cách dự báo:N", sort=None, title=None, axis=alt.Axis(labelLimit=190)),
            x=alt.X("Sai lệch:Q", title=None),
            color=alt.condition(alt.datum["Cách dự báo"] == "Dự báo cuối", alt.value("#7057f5"), alt.value("#c5bafc")),
            tooltip=["Cách dự báo:N", alt.Tooltip("Sai lệch:Q", format=".2f")])
        st.altair_chart(bars.properties(height=250), use_container_width=True, key="mae_comparison")
    item_columns = st.columns(2, gap="medium")
    for column, title, subset in [(item_columns[0], "Dự báo dư", items[items.bias > 0].nlargest(5, "bias")),
                                  (item_columns[1], "Dự báo thiếu", items[items.bias < 0].nsmallest(5, "bias"))]:
        with column, st.container(border=True, key=f"item_bias_{title}"):
            st.subheader(title)
            st.caption("Tối đa 5 sản phẩm · Xếp theo tổng đơn vị chênh lệch trong cả khoảng")
            if subset.empty:
                st.info(f"Không có sản phẩm {title.lower()} trong bộ đang chọn.")
            else:
                st.dataframe(subset.rename_axis("Sản phẩm").reset_index().rename(columns={"actual": "Thực tế", "predicted": "Dự báo cuối", "mae": "Sai lệch trung bình", "bias": "Dư/thiếu (đơn vị)"}).round(1), hide_index=True, width="stretch")
    with st.container(border=True, key="research_results"):
        research_results()
    st.caption("Đánh giá hồi cứu trên quá khứ. Chưa đủ cơ sở tự động nhập hàng.")
    with st.expander("Phạm vi có thể kết luận"):
        st.write("Đây là đối chiếu hồi cứu trên lượng bán quan sát. Test của CA_1, CA_2, CA_3, TX_1 và WI_1 đều đã xem. "
                 "Ba cửa hàng nghiên cứu dùng cùng một giai đoạn 28 ngày; chưa chứng minh ổn định ở nhiều giai đoạn mới. "
                 "Các cửa sổ phát triển có chồng lấp và ba lần chạy không phải ba bộ dữ liệu độc lập.")
        st.write("Không kết luận mô hình tối ưu nhất, không suy ra hết hàng hay nguyên nhân biến động. "
                 "Chưa đủ cơ sở để tự động nhập hàng: chưa tính tồn kho, chi phí dư/thiếu và kiểm tra dài hạn.")


def methodology(folder, report):
    with st.expander("Phương pháp và thông tin đồ án"):
        st.write("Spark tổng hợp bán hàng; scikit-learn dự báo cho nhóm nhỏ. Dashboard chỉ đọc CSV/JSON đã xuất, không huấn luyện khi đổi bộ lọc.")
        st.write("V1: bản đầu, chọn RF hoặc lặp tuần trước. V2: thử cải thiện. V3: đóng băng cách kết hợp 50/50 đã chọn bằng validation CA_1/CA_2, rồi kiểm tra tại CA_3/TX_1/WI_1. Không chọn lại bằng test.")
        st.write(f"Bộ đang đọc: {report.get('pipeline_version', 'v1')} · {report.get('series_count', '?')} sản phẩm · "
                 f"Seed demo: {report.get('published_seed', 42)}. Seed là mốc ngẫu nhiên khi học. Nghiên cứu V3 lấy trung bình chỉ số seed 42/43/44, không phải chỉ số của một mô hình gộp ba lần chạy.")
        st.write("Trong nghiên cứu V3, nhóm recent chọn từ 26 tuần gần mốc 06/12/2015, loại sản phẩm bán 0 trong 28 ngày cuối; legacy dùng tổng lịch sử đến cùng mốc. 13 mốc validation cách nhau bảy ngày, chia bốn nhóm; cửa sổ trên màn hình chỉ là lần cuối.")
        st.write("Cấu hình bộ kết quả: " + json.dumps(report.get("selected_params", {}), ensure_ascii=False))
        st.write(f"Nguồn: {Path(folder)}. Dự báo: forecast/history.csv, predictions.csv, metrics.csv, forecast_report.json. Bán hàng: analysis/daily_category_store.csv.")
        st.write("Giải thích kiến trúc, phương pháp và giới hạn: docs/GIAI_THICH_DU_AN.md. Bảng V3 ba seed: resources/v3_test_metrics.csv. "
                 "Thiết lập mặc định: config/forecast.json. V1 giữ ở code/13_forecasting_v1.py.")
        proof = hdfs_verification(folder)
        if proof:
            st.write(f"Đã kiểm chứng Spark đọc HDFS: {number(proof['quality']['rows'])} dòng, đối chiếu đủ bốn bảng tổng hợp với local. "
                     "HDFS gồm một NameNode và một DataNode trong Docker trên cùng máy; Spark chạy local[2]. Chưa kiểm chứng cụm nhiều máy.")
            st.caption("Bằng chứng: analysis_hdfs/verification.json, analysis_report.json và hdfs_storage.log. Dashboard vẫn đọc bộ CSV đã chọn ở trên.")
        else:
            st.write("Chưa có bằng chứng HDFS hợp lệ trong thư mục kết quả đang chọn. Có thể chạy run_hdfs_demo.ps1 để kiểm chứng riêng.")


def main():
    st.set_page_config(page_title="M5 · Bán hàng và dự báo", layout="wide")
    st.html(ROOT / "code/dashboard.css")
    st.html('<div class="app-bar"><span>Không gian phân tích / Bán hàng & dự báo</span>'
            '<span class="app-status">Dữ liệu lịch sử M5</span></div>')
    with st.sidebar:
        st.html('<div class="brand"><span class="brand-mark">m5</span>'
                '<div><strong>M5 Analytics</strong><small>BÁN HÀNG & DỰ BÁO</small></div></div>')
    page = st.sidebar.radio("Chọn trang", PAGES, index=1)
    st.sidebar.divider()
    st.sidebar.caption("Bộ lọc nằm ở đầu mỗi trang. Dự báo dùng khoảng đánh giá cố định, độc lập với ngày bán hàng.")
    with st.sidebar.expander("Nguồn kết quả"):
        folder = st.text_input("Thư mục kết quả", os.environ.get("M5_OUTPUT_DIR", str(ROOT / "outputs")))
    try:
        daily, history, predictions, metrics, reports = load_data(folder)
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as error:
        st.error(f"Không đọc được kết quả: {error}")
        st.info("Chọn thư mục có analysis và forecast đã xuất thành công trong mục Nguồn kết quả.")
        return
    if page == PAGES[0]:
        overview(daily)
    elif page == PAGES[1]:
        product_forecast(history, predictions, reports[1])
    else:
        reliability(predictions)
    methodology(folder, reports[1])


if __name__ == "__main__":
    main()
