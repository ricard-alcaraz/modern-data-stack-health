import os
import streamlit as st
import duckdb
import re

import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from semantic_layer import get_semantic_layer_prompt, get_metric_sql, list_metric_names, METRICS
from db import get_connection
import sqlglot
from sqlglot import exp

load_dotenv()
st.set_page_config(page_title="AI Analyst", page_icon="🤖", layout="wide")

st.title("🤖 AI Data Analyst")
st.markdown("""
Ask natural language questions about the health of the modern data stack. 
The AI will generate the SQL, query MotherDuck, and summarize the findings.
""")

# --- 1. Configuration & Connections ---

def get_llm_client(provider="openai"):
    """Get LLM client based on provider selection."""
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None, None, "No API key configured"
        return OpenAI(api_key=api_key), "gpt-4o-mini", None
    
    elif provider == "lmstudio":
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        try:
            client = OpenAI(base_url=base_url, api_key="lm-studio")
            models = client.models.list().data
            if not models:
                return None, None, "No models loaded in LM Studio. Load a model and start the server."
            model_id = models[0].id
            return client, model_id, None
        except Exception as e:
            return None, None, f"Cannot connect to LM Studio at {base_url}. Is the server running? Error: {e}"
    
    return None, None, "Unknown provider"

def validate_readonly_sql(sql_query: str) -> bool:
    """
    Defense-in-depth: Validates that the generated SQL is strictly a read-only query
    using sqlglot to parse the AST.
    """
    try:
        # Strip markdown and trailing semicolons
        sql_clean = sql_query.strip()
        if sql_clean.lower().startswith("```sql"): sql_clean = sql_clean[6:]
        if sql_clean.endswith("```"): sql_clean = sql_clean[:-3]
        sql_clean = sql_clean.strip().rstrip(';')
        
        if not sql_clean: return False

        parsed = sqlglot.parse(sql_clean, read="duckdb")
        
        # Must be exactly one statement
        if len(parsed) != 1 or parsed[0] is None: return False
            
        stmt = parsed[0]
        
        # Must be a SELECT statement (includes WITH clauses)
        if not isinstance(stmt, exp.Select): return False

        # 1. Block dangerous functions (exfiltration vectors)
        DANGEROUS_FUNCS = {
            'read_csv', 'read_csv_auto', 'read_parquet', 'read_json', 
            'read_json_auto', 'glob', 'read_text', 'httpfs', 'md_scan',
            'current_setting' # Prevents leaking MOTHERDUCK_TOKEN
        }
        
        for node in stmt.walk():
            if isinstance(node, exp.Anonymous) and node.name.lower() in DANGEROUS_FUNCS:
                return False
            if isinstance(node, exp.CurrentSetting):
                return False
            if isinstance(node, exp.Table):
                if node.name.lower() in DANGEROUS_FUNCS: return False
                # Table functions are parsed as Table(this=Func/Anonymous)
                if node.this and isinstance(node.this, (exp.Func, exp.Anonymous)):
                    return False

        # 2. Enforce strict table allowlist
        cte_names = set()
        with_node = stmt.args.get("with")
        if with_node:
            for cte in with_node.expressions:
                if cte.alias_or_name: cte_names.add(cte.alias_or_name.lower())
        
        for table in stmt.find_all(exp.Table):
            if table.this and isinstance(table.this, (exp.Func, exp.Anonymous)):
                continue # Skip table functions
            
            table_name = table.name.lower().strip('"')
            schema_name = table.db.lower().strip('"') if table.db else None
            
            if schema_name == 'information_schema': continue
            if table_name in cte_names: continue
            if schema_name == 'raw': continue # Allow ingestion schema
            if table_name.startswith('fct_') or table_name.startswith('stg_'): continue
                
            return False # Forbidden table
            
        return True
        
    except Exception:
        return False

conn = get_connection()

# --- 2. Dynamic Schema Extraction ---
def get_schema_from_motherduck(conn):
    """Dynamically extract schema from MotherDuck's information_schema."""
    tables = conn.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'main' 
        AND table_type = 'BASE TABLE'
    """).df()['table_name'].tolist()
    
    schema_info = []
    
    for table in tables:
        columns = conn.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_schema = 'main' 
            AND table_name = '{table}'
            ORDER BY ordinal_position
        """).df()
        
        col_descriptions = []
        for _, row in columns.iterrows():
            nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
            col_descriptions.append(f"  - `{row['column_name']}` ({row['data_type']}, {nullable})")
        
        schema_info.append(f"\n**{table}**\n" + "\n".join(col_descriptions))
    
    return "\n".join(schema_info)

# --- 3. UI: LLM Provider Selection ---
llm_provider = st.sidebar.selectbox(
    "Choose LLM Provider",
    options=["openai", "lmstudio"],
    format_func=lambda x: "OpenAI (Cloud)" if x == "openai" else "LM Studio (Local)",
    help="OpenAI requires API key, LM Studio runs locally"
)

client, model, error = get_llm_client(llm_provider)

if not client:
    st.error(f"❌ {error}")
    st.stop()

st.info(f"🔌 Connected to **{llm_provider.upper()}** using model: `{model}`")

# --- 4. Semantic Layer Sidebar ---
st.sidebar.divider()
st.sidebar.subheader("📐 Semantic Layer")
st.sidebar.caption("Pre-defined business metrics the AI can use:")
for name in list_metric_names():
    st.sidebar.markdown(f"- `{name}`")

with st.sidebar.expander("📖 Metric Definitions"):
    for name, meta in METRICS.items():
        st.markdown(f"**`{name}`**")
        st.caption(meta["description"])
        st.divider()

# --- 5. Build System Prompt with Dynamic Schema + Semantic Layer ---
dynamic_schema = get_schema_from_motherduck(conn)
semantic_prompt = get_semantic_layer_prompt()

SCHEMA_CONTEXT = f"""
You are an expert DuckDB SQL analyst. You have access to the following tables in the `main` schema:

{dynamic_schema}

{semantic_prompt}

RULES:
- Return ONLY valid DuckDB SQL. Do not wrap in markdown code blocks.
- Use ONLY SELECT statements. No INSERT, UPDATE, or DELETE.
- If the user asks for a trend, GROUP BY week_start and ORDER BY week_start.
- Always use table aliases for clarity.
- For date filtering, use DuckDB syntax: WHERE week_start >= '2024-01-01'
- When referencing timestamps, cast them appropriately: column::DATE or column::TIMESTAMP
"""

# --- 6. Quick Metric Buttons ---
st.markdown("### ⚡ Quick Metrics")
cols = st.columns(3)
quick_metrics = list(METRICS.keys())

if "direct_metric" not in st.session_state:
    st.session_state["direct_metric"] = None

for i, metric_name in enumerate(quick_metrics):
    with cols[i % 3]:
        if st.button(f"📊 {metric_name.replace('_', ' ').title()}", use_container_width=True):
            st.session_state["direct_metric"] = metric_name

# --- 7. Query Interface ---
direct_metric = st.session_state.get("direct_metric")

if direct_metric:
    metric_sql = METRICS[direct_metric]["sql"]
    
    st.markdown(f"### 📈 Executing Pre-defined Metric: `{direct_metric}`")
    st.caption(METRICS[direct_metric]["description"])
    st.code(metric_sql, language="sql")
    
    with st.spinner("🗄️ Executing query against MotherDuck..."):
        try:
            df = conn.execute(metric_sql).df()
            if df.empty:
                st.info("The query ran successfully, but returned no results.")
            else:
                st.success("Query executed successfully!")
                st.dataframe(df, use_container_width=True)
                
                # AI Summary
                with st.spinner("📝 AI is summarizing the results..."):
                    summary_prompt = f"""
                    The user ran the pre-defined metric: "{direct_metric}"
                    The SQL query returned this data: {df.head(10).to_markdown()}
                    Provide a concise, 2-3 sentence business summary of these findings.
                    """
                    summary_response = client.chat.completions.create(
                        model=model, messages=[{"role": "user", "content": summary_prompt}], temperature=0.3
                    )
                    st.markdown("### 💡 AI Summary")
                    st.info(summary_response.choices[0].message.content)
        except Exception as e:
            st.error(f"An error occurred: {e}")
            
    if st.button("❌ Clear Metric & Ask Custom Question"):
        st.session_state["direct_metric"] = None
        st.rerun()

else:
    user_question = st.text_input(
        "Ask a question about the data:",
        placeholder="e.g., What is the total number of merged PRs for dbt-core?",
        value=st.session_state.get("user_question", ""),
        key="question_input"
    )
    
    if user_question:
        if "user_question" in st.session_state:
            del st.session_state["user_question"]
