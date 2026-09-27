import os
import streamlit as st
import duckdb
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Modern Data Stack Health",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# MotherDuck connection
@st.cache_resource
def get_connection():
    token = os.getenv("MOTHERDUCK_TOKEN")
    if not token:
        st.error("MOTHERDUCK_TOKEN not found. Set it in .env or Streamlit secrets.")
        st.stop()
    return duckdb.connect(f"md:mds_health_db?motherduck_token={token}")

# Title
st.title("🏥 Health of the Modern Data Stack")
st.markdown("""
Tracking the **real health** of open-source tools in the modern data stack — 
beyond vanity metrics like GitHub stars. We analyze contribution velocity, 
issue resolution time, and contributor retention for the tools you use every day.
""")

# Connect and show summary
conn = get_connection()

# KPIs
try:
    summary = conn.execute("""
        SELECT 
            COUNT(DISTINCT tool_name) as tools_tracked,
            MAX(week_start) as latest_week,
            SUM(issues_opened) as total_issues_opened,
            SUM(prs_merged) as total_prs_merged
        FROM mds_health_db.main.fct_tool_weekly_snapshot
    """).df()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tools Tracked", summary['tools_tracked'].iloc[0])
    col2.metric("Latest Week", summary['latest_week'].iloc[0].strftime('%Y-%m-%d'))
    col3.metric("Total Issues Opened", f"{summary['total_issues_opened'].iloc[0]:,}")
    col4.metric("Total PRs Merged", f"{summary['total_prs_merged'].iloc[0]:,}")
    
    st.divider()
    
    # Tools list
    tools = conn.execute("""
        SELECT DISTINCT tool_name 
        FROM mds_health_db.main.fct_tool_weekly_snapshot 
        ORDER BY tool_name
    """).df()
    
    st.subheader("🛠️ Tools Being Tracked")
    st.write(", ".join(tools['tool_name'].tolist()))
    
    st.divider()
    st.info("👈 Use the sidebar to explore tool comparisons and contributor analysis.")
    
except Exception as e:
    st.error(f"Error connecting to MotherDuck: {e}")
    st.info("Make sure MOTHERDUCK_TOKEN is set and the database has data.")