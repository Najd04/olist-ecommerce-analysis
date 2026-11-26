from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Olist E-Commerce Dashboard", page_icon="📦", layout="wide")

BASE = Path(__file__).parent


@st.cache_data
def load_orders():
    df = pd.read_csv(BASE / "dashboard_data.csv.gz", parse_dates=["order_purchase_timestamp"])
    df["month"] = df["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    return df


@st.cache_data
def load_rfm():
    return pd.read_csv(BASE / "rfm_summary.csv")


df = load_orders()
rfm = load_rfm()

st.title("📦 Olist E-Commerce Dashboard")
st.caption("Late deliveries, customer satisfaction and customer segments (delivered orders, 2016–2018).")

# ---------- Sidebar filters ----------
st.sidebar.header("Filters")

min_date = df["order_purchase_timestamp"].min().date()
max_date = df["order_purchase_timestamp"].max().date()
date_range = st.sidebar.date_input(
    "Order date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
)
if len(date_range) != 2:
    st.info("Pick both a start and an end date.")
    st.stop()
start, end = date_range

all_states = sorted(df["customer_state"].dropna().unique())
selected_states = st.sidebar.multiselect("State (leave empty for all)", all_states)

mask = (df["order_purchase_timestamp"].dt.date >= start) & (df["order_purchase_timestamp"].dt.date <= end)
if selected_states:
    mask &= df["customer_state"].isin(selected_states)
f = df[mask]

if f.empty:
    st.warning("No orders match these filters.")
    st.stop()

# ---------- KPIs ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Orders", f"{len(f):,}")
c2.metric("Revenue (item prices)", f"R$ {f['price'].sum():,.0f}")
c3.metric("Avg review score", f"{f['review_score'].mean():.2f}")
c4.metric("Late deliveries", f"{f['is_late'].mean() * 100:.1f}%")

# ---------- Tabs ----------
tab_trend, tab_delivery, tab_state, tab_rfm = st.tabs(
    ["Trends", "Delivery vs Reviews", "By State", "RFM Segments"]
)

with tab_trend:
    monthly = f.groupby("month").agg(
        orders=("price", "size"),
        late_pct=("is_late", lambda x: x.mean() * 100),
        avg_score=("review_score", "mean"),
    )
    st.subheader("Orders per month")
    st.line_chart(monthly["orders"])
    st.subheader("Late delivery % per month")
    st.line_chart(monthly["late_pct"])

with tab_delivery:
    st.subheader("Average review score: on time vs late")
    by_late = f.groupby("is_late")["review_score"].mean()
    by_late.index = by_late.index.map({False: "1 - On time", True: "2 - Late"})
    st.bar_chart(by_late)

    st.subheader("Share of each review score (%)")
    dist = (
        f.dropna(subset=["review_score"])
        .groupby("is_late")["review_score"]
        .value_counts(normalize=True)
        .unstack()
        * 100
    ).round(1)
    dist.index = dist.index.map({False: "On time", True: "Late"})
    st.dataframe(dist, use_container_width=True)
    st.caption("Late orders get far more 1-star reviews. This is a strong association, not proof of cause.")

with tab_state:
    min_orders = st.slider("Minimum orders per state", 0, 2000, 500, step=50)
    state = (
        f.groupby("customer_state")
        .agg(
            orders=("price", "size"),
            late_pct=("is_late", lambda x: x.mean() * 100),
            avg_days=("delivery_days", "mean"),
            avg_score=("review_score", "mean"),
        )
        .round(1)
    )
    state = state[state["orders"] >= min_orders].sort_values("late_pct", ascending=False)

    if state.empty:
        st.info("No state has that many orders with the current filters. Lower the minimum.")
    else:
        st.subheader("Late delivery % by state")
        st.bar_chart(state["late_pct"])
        st.dataframe(state, use_container_width=True)

with tab_rfm:
    st.subheader("Revenue share by RFM segment (%)")
    st.caption("This tab uses the full dataset and is not affected by the sidebar filters.")
    seg = rfm.set_index("segment").sort_values("revenue_share_%", ascending=False)
    st.bar_chart(seg["revenue_share_%"])
    st.dataframe(seg, use_container_width=True)
    st.caption(
        "Segments come from rules on Recency and Monetary scores, so they are an approximate prioritization."
    )
