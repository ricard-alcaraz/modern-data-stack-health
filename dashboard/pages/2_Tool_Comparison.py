import os
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from db import get_connection

load_dotenv()
st.set_page_config(page_title="Tool Comparison", page_icon="⚖️", layout="wide")
st.title("⚖️ Tool Comparison")

conn = get_connection()

# Aggregate metrics per tool
metrics = conn.execute("""
    SELECT 
        tool_name,
        SUM(issues_opened) as total_issues_opened,
        SUM(issues_closed) as total_issues_closed,
        ROUND(AVG(avg_issue_close_time_days), 2) as avg_close_time,
        SUM(prs_opened) as total_prs_opened,
        SUM(prs_merged) as total_prs_merged,
        COUNT(DISTINCT week_start) as weeks_tracked
    FROM main.fct_tool_weekly_snapshot
    GROUP BY tool_name
    ORDER BY tool_name
""").df()

if metrics.empty:
    st.warning("No data available.")
    st.stop()

# Display metrics as cards
st.subheader("📊 Key Metrics by Tool")
cols = st.columns(len(metrics))
for i, row in metrics.iterrows():
    with cols[i % len(cols)]:
        st.metric(
            label=row['tool_name'],
            value=f"{row['total_prs_merged']} PRs merged",
            delta=f"{row['total_issues_closed']} issues closed"
        )

st.divider()

# Bar chart comparisons
col1, col2 = st.columns(2)

with col1:
    st.subheader("Total PRs Merged")
    fig1 = px.bar(
        metrics,
        x='tool_name',
        y='total_prs_merged',
        color='tool_name',
        title="Which tool has the most merged PRs?"
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Average Issue Close Time (days)")
    fig2 = px.bar(
        metrics,
        x='tool_name',
        y='avg_close_time',
        color='tool_name',
        title="Which tool resolves issues fastest?"
    )
    st.plotly_chart(fig2, use_container_width=True)

# Full comparison table
st.subheader("📋 Full Comparison Table")
st.dataframe(metrics, use_container_width=True)