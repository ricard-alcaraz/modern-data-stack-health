import pandas as pd
import plotly.express as px
import streamlit as st
from db import get_connection

st.set_page_config(page_title="Data Quality", page_icon="✅", layout="wide")
st.title("✅ Data Quality Monitoring")
st.caption("Powered by Elementary — observability data stored in MotherDuck")

conn = get_connection()

# Check if Elementary tables exist
try:
    test = conn.execute("""
        SELECT COUNT(*) 
        FROM elementary_test_results
    """).fetchone()[0]
except Exception as e:
    st.error(
        "Elementary tables not found. Run `make ingest` and `make dbt-run` first to populate observability data."
    )
    st.code(str(e))
    st.stop()

# --- KPIs ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_tests = conn.execute("""
        SELECT COUNT(DISTINCT test_unique_id) 
        FROM elementary_test_results
    """).fetchone()[0]
    st.metric("Total Tests", total_tests)

with col2:
    passed_tests = conn.execute("""
        SELECT COUNT(DISTINCT test_unique_id) 
        FROM elementary_test_results
        WHERE status = 'pass'
    """).fetchone()[0]
    st.metric("Passed Tests", passed_tests)

with col3:
    recent_runs = conn.execute("""
        SELECT COUNT(DISTINCT invocation_id) 
        FROM dbt_invocations
        WHERE (generated_at)::TIMESTAMP >= (CURRENT_DATE - INTERVAL 7 DAY)::TIMESTAMP
    """).fetchone()[0]
    st.metric("Runs (7 days)", recent_runs)

with col4:
    failed_tests = conn.execute("""
        SELECT COUNT(*) 
        FROM elementary_test_results
        WHERE status = 'fail'
    """).fetchone()[0]
    st.metric("Failed Tests (All Time)", failed_tests)

st.divider()

# --- Test Results Over Time ---
st.subheader("📊 Test Results Over Time")

test_results = conn.execute("""
    SELECT 
        DATE(detected_at) as test_date,
        status,
        COUNT(*) as count
    FROM elementary_test_results
    WHERE (detected_at)::TIMESTAMP >= (CURRENT_DATE - INTERVAL 30 DAY)::TIMESTAMP
    GROUP BY 1, 2
    ORDER BY 1
""").df()

if not test_results.empty:
    fig = px.bar(
        test_results,
        x="test_date",
        y="count",
        color="status",
        barmode="stack",
        title="Daily Test Results (Last 30 Days)",
        labels={"test_date": "Date", "count": "Number of Tests"},
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No test results in the last 30 days. Run your pipeline to generate data.")

st.divider()

# --- Recent Test Failures ---
st.subheader("🚨 Recent Test Failures")

recent_failures = conn.execute("""
    SELECT 
        test_name,
        test_sub_type,
        status,
        detected_at,
        failures
    FROM elementary_test_results
    WHERE status = 'fail'
    ORDER BY detected_at DESC
    LIMIT 10
""").df()

if not recent_failures.empty:
    recent_failures["detected_at"] = recent_failures["detected_at"].dt.strftime(
        "%Y-%m-%d %H:%M"
    )
    st.dataframe(recent_failures, use_container_width=True)
else:
    st.success("No test failures in the recent history! 🎉")

st.divider()

# --- Source Freshness ---
st.subheader("⏰ Source Freshness")

freshness = conn.execute("""
    WITH ranked AS (
        SELECT 
            unique_id,
            max_loaded_at,
            generated_at,
            status,
            ROW_NUMBER() OVER (
                PARTITION BY unique_id
                ORDER BY generated_at DESC
            ) as rn
        FROM dbt_source_freshness_results
        WHERE max_loaded_at IS NOT NULL
    )
    SELECT 
        unique_id,
        max_loaded_at,
        CASE 
            WHEN status = 'error' THEN 'Stale'
            WHEN status = 'warn' THEN 'Warning'
            ELSE 'Fresh'
        END as display_status
    FROM ranked
    WHERE rn = 1
    ORDER BY max_loaded_at ASC
""").df()

if not freshness.empty:
    freshness["max_loaded_at"] = pd.to_datetime(freshness["max_loaded_at"]).dt.strftime(
        "%Y-%m-%d %H:%M"
    )

    def color_status(val):
        if val == "Stale":
            return "color: red"
        elif val == "Warning":
            return "color: orange"
        else:
            return "color: green"

    st.dataframe(
        freshness.style.map(color_status, subset=["display_status"]),
        use_container_width=True,
    )
else:
    st.info("No freshness data yet.")

st.divider()

# --- Run History ---
st.subheader("📅 Recent dbt Runs")

runs = conn.execute("""
    SELECT 
        invocation_id,
        generated_at,
        command,
        target_name,
        run_started_at,
        run_completed_at
    FROM dbt_invocations
    ORDER BY generated_at DESC
    LIMIT 20
""").df()

if not runs.empty:
    runs["generated_at"] = pd.to_datetime(runs["generated_at"]).dt.strftime(
        "%Y-%m-%d %H:%M"
    )
    runs["elapsed_time"] = (
        (
            pd.to_datetime(runs["run_completed_at"])
            - pd.to_datetime(runs["run_started_at"])
        )
        .dt.total_seconds()
        .round(2)
    )
    st.dataframe(runs, use_container_width=True)

    # Run duration chart
    fig2 = px.line(
        runs.sort_values("generated_at"),
        x="generated_at",
        y="elapsed_time",
        title="dbt Run Duration Over Time",
        labels={"generated_at": "Run Time", "elapsed_time": "Duration (seconds)"},
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("No run history yet.")
