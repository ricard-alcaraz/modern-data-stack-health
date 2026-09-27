import os
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from db import get_connection

load_dotenv()
st.set_page_config(page_title="Contributors", page_icon="👥", layout="wide")
st.title("👥 Contributor Analysis")

st.markdown("""
Analyzing **contributor churn** — are the same people maintaining these tools, 
or is there healthy turnover? This is a key signal for long-term project health.
""")

conn = get_connection()

# Top contributors by tool (from staging tables)
try:
    contributors = conn.execute("""
        WITH issue_authors AS (
            SELECT 
                tool_name,
                author_login,
                COUNT(*) as contributions,
                'issues' as type
            FROM mds_health_db.main.stg_github_issues
            WHERE author_login IS NOT NULL
            GROUP BY 1, 2
        ),
        pr_authors AS (
            SELECT 
                tool_name,
                author_login,
                COUNT(*) as contributions,
                'pull_requests' as type
            FROM mds_health_db.main.stg_github_pulls
            WHERE author_login IS NOT NULL
            GROUP BY 1, 2
        )
        SELECT * FROM issue_authors
        UNION ALL
        SELECT * FROM pr_authors
        ORDER BY tool_name, contributions DESC
    """).df()
    
    if contributors.empty:
        st.warning("No contributor data available.")
        st.stop()
    
    # Tool selector
    selected_tool = st.selectbox(
        "Select a tool",
        options=contributors['tool_name'].unique()
    )
    
    tool_contributors = contributors[contributors['tool_name'] == selected_tool]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(f"Top Issue Authors — {selected_tool}")
        issue_authors = tool_contributors[tool_contributors['type'] == 'issues'].head(10)
        fig1 = px.bar(
            issue_authors,
            x='contributions',
            y='author_login',
            orientation='h',
            title="Who's opening the most issues?"
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.subheader(f"Top PR Authors — {selected_tool}")
        pr_authors = tool_contributors[tool_contributors['type'] == 'pull_requests'].head(10)
        fig2 = px.bar(
            pr_authors,
            x='contributions',
            y='author_login',
            orientation='h',
            title="Who's contributing the most code?"
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # Contributor diversity metrics
    st.subheader("📊 Contributor Diversity")
    diversity = tool_contributors.groupby('type').agg({
        'author_login': 'nunique',
        'contributions': 'sum'
    }).reset_index()
    diversity.columns = ['type', 'unique_contributors', 'total_contributions']
    diversity['avg_contributions_per_person'] = (
        diversity['total_contributions'] / diversity['unique_contributors']
    ).round(2)
    
    st.dataframe(diversity, use_container_width=True)
    
except Exception as e:
    st.error(f"Error loading contributor data: {e}")