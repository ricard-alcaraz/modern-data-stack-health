import os
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Overview", page_icon="📈", layout="wide")
st.title("📈 Weekly Activity Overview")

@st.cache_resource
def get_connection():
    token = os.getenv("MOTHERDUCK_TOKEN")
    return duckdb.connect(f"md:mds_health_db?motherduck_token={token}")

conn = get_connection()

# Load data
df = conn.execute("""
    SELECT * FROM mds_health_db.main.fct_tool_weekly_snapshot
    ORDER BY week_start DESC
""").df()

if df.empty:
    st.warning("No data available. Run the ingestion pipeline first.")
    st.stop()

# Sidebar filters
st.sidebar.header("Filters")
selected_tools = st.sidebar.multiselect(
    "Select tools",
    options=df['tool_name'].unique(),
    default=df['tool_name'].unique()
)

filtered_df = df[df['tool_name'].isin(selected_tools)]

# Time range filter - convert pandas Timestamp to Python datetime
min_week = filtered_df['week_start'].min().to_pydatetime()
max_week = filtered_df['week_start'].max().to_pydatetime()
date_range = st.sidebar.slider(
    "Week range",
    min_value=min_week,
    max_value=max_week,
    value=(min_week, max_week)
)

# Convert back to pandas Timestamp for filtering
filtered_df = filtered_df[
    (filtered_df['week_start'] >= pd.Timestamp(date_range[0])) & 
    (filtered_df['week_start'] <= pd.Timestamp(date_range[1]))
]

# Charts
col1, col2 = st.columns(2)

with col1:
    st.subheader("Issues Opened per Week")
    fig1 = px.line(
        filtered_df,
        x='week_start',
        y='issues_opened',
        color='tool_name',
        markers=True,
        title="Weekly Issue Creation"
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Pull Requests Merged per Week")
    fig2 = px.line(
        filtered_df,
        x='week_start',
        y='prs_merged',
        color='tool_name',
        markers=True,
        title="Weekly PR Merges"
    )
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Average Issue Close Time (days)")
fig3 = px.line(
    filtered_df,
    x='week_start',
    y='avg_issue_close_time_days',
    color='tool_name',
    markers=True,
    title="How quickly are issues resolved?"
)
st.plotly_chart(fig3, use_container_width=True)

# Raw data table
st.subheader("📊 Raw Weekly Data")
st.dataframe(
    filtered_df.sort_values('week_start', ascending=False),
    use_container_width=True
)