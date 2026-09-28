import streamlit as st
import plotly.express as px

from db import get_connection
from semantic_layer import METRICS

st.set_page_config(page_title="Contributors", page_icon="👥", layout="wide")
st.title("👥 Contributor Analysis")

st.markdown("""
Analyzing **contributor concentration, churn, and top authors** — are the same
people maintaining these tools, or is there healthy turnover? This is a key
signal for long-term project health.

All figures exclude bots (dependabot, github-actions, …) and are served from
the shared semantic layer, so they match the AI Analyst exactly.
""")

conn = get_connection()


@st.cache_data(ttl=300, show_spinner=False)
def load_contributor_data():
    return {
        "top": conn.execute(METRICS["top_contributors"]["sql"]).df(),
        "concentration": conn.execute(METRICS["contributor_concentration"]["sql"]).df(),
        "churn": conn.execute(METRICS["contributor_churn"]["sql"]).df(),
    }


try:
    data = load_contributor_data()
except Exception as e:
    st.error(f"Error loading contributor data: {e}")
    st.stop()

top, concentration, churn = data["top"], data["concentration"], data["churn"]

if top.empty:
    st.warning("No contributor data available.")
    st.stop()

selected_tool = st.selectbox(
    "Select a tool",
    options=sorted(top["tool_name"].unique()),
)

tool_top = top[top["tool_name"] == selected_tool].sort_values("tool_rank")
tool_conc = concentration[concentration["tool_name"] == selected_tool]
tool_churn = churn[churn["tool_name"] == selected_tool]

# --- KPI row ---------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)

if not tool_conc.empty:
    c = tool_conc.iloc[0]
    k1.metric("Unique contributors", f"{int(c['unique_contributors']):,}")
    k2.metric(
        "Concentration (HHI)",
        f"{c['concentration_hhi']:.3f}",
        help="Sum of squared contribution shares. 1.0 = one person does everything; near 0 = evenly spread. High = bus-factor risk.",
    )
    k3.metric("Top-5 share", f"{c['top5_share'] * 100:.1f}%")

if not tool_churn.empty:
    k4.metric(
        "Contributor churn (90d)",
        f"{tool_churn.iloc[0]['churn_rate_pct']:.1f}%",
        help="Share of prior-period contributors who made no contribution in the most recent 90-day window. Lower is better.",
    )
else:
    k4.metric("Contributor churn (90d)", "n/a", help="Needs ~180 days of ingested history. Run the full backfill first.")

st.divider()

# --- Top 10 contributors chart --------------------------------------------
st.subheader(f"Top 10 Contributors — {selected_tool}")

melted = tool_top.melt(
    id_vars=["author_login", "tool_rank", "total_contributions"],
    value_vars=["issues", "pull_requests"],
    var_name="type",
    value_name="count",
)
author_order = tool_top["author_login"].tolist()  # already sorted by tool_rank

fig = px.bar(
    melted,
    x="count",
    y="author_login",
    color="type",
    orientation="h",
    title="Top contributors by total activity (issues + PRs, bots excluded)",
    color_discrete_map={"issues": "#636EFA", "pull_requests": "#00CC96"},
)
# Rank 1 at the top of the horizontal bar chart
fig.update_yaxes(categoryorder="array", categoryarray=author_order[::-1])
st.plotly_chart(fig, use_container_width=True)

# --- Cross-tool tables ------------------------------------------------------
st.subheader("📊 Contributor Concentration (all tools)")
st.caption(
    "concentration_hhi: 1.0 = one person does everything. "
    "top5_share: fraction of all contributions from the five most active authors."
)
st.dataframe(concentration, use_container_width=True)

st.subheader("🔁 Contributor Churn (all tools)")
st.caption(
    "Of the contributors active in the prior 90-day window, the share who made no "
    "contribution in the most recent 90-day window. Lower is healthier."
)
if churn.empty:
    st.info("Not enough history yet — run the one-time backfill, then re-run dbt.")
else:
    st.dataframe(churn, use_container_width=True)