"""Shared MotherDuck connection helpers for all Streamlit pages."""
import os

import duckdb
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource
def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Cached MotherDuck connection. Use read_only=True for query-only pages."""
    token = os.getenv("MOTHERDUCK_TOKEN")
    if not token:
        st.error("MOTHERDUCK_TOKEN not found. Set it in .env or Streamlit secrets.")
        st.stop()
    database = os.getenv("MOTHERDUCK_DATABASE", "mds_health_db")
    return duckdb.connect(
        f"md:{database}?motherduck_token={token}",
        read_only=read_only,
    )