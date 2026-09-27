"""Shared MotherDuck connection helpers for all Streamlit pages."""
import os

import duckdb
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """One cached, strictly read-only MotherDuck connection for the whole dashboard.

    DuckDB forbids opening the same database twice in one process with
    different configurations (read-only vs read-write). Every dashboard page
    only ever runs SELECTs, so we open a single read-only connection and
    share it everywhere.
    """
    token = os.getenv("MOTHERDUCK_TOKEN")
    if not token:
        st.error("MOTHERDUCK_TOKEN not found. Set it in .env or Streamlit secrets.")
        st.stop()
    database = os.getenv("MOTHERDUCK_DATABASE", "mds_health_db")
    return duckdb.connect(
        f"md:{database}?motherduck_token={token}",
        read_only=True,
    )