import os
import streamlit as st
import duckdb
import re

import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from semantic_layer import get_semantic_layer_prompt, get_metric_sql, list_metric_names, METRICS
from db import get_connection

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
    Defense-in-depth: Validates that the generated SQL is strictly a read-only query.
    Rejects DML, DDL, and multiple statements.
    """
    # 1. Strip SQL comments to prevent bypass tricks (e.g., hiding a DROP in a multi-line comment)
    sql_clean = re.sub(r'--.*$', '', sql_query, flags=re.MULTILINE)
    sql_clean = re.sub(r'/\*.*?\*/', '', sql_clean, flags=re.DOTALL)
    sql_clean = re.sub(r'\s+', ' ', sql_clean).strip()
    
    # 2. Block multiple statements (DuckDB can execute chained statements separated by ';')
    if ';' in sql_clean:
        return False
        
    # 3. Block dangerous keywords using word boundaries (\b)
    dangerous_keywords = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 
        'ATTACH', 'DETACH', 'COPY', 'EXECUTE', 'CALL', 'PREPARE', 
        'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK', 'MERGE', 'TRUNCATE',
        'EXPORT', 'IMPORT', 'INSTALL', 'LOAD' # Prevent loading extensions
    ]
    
    for kw in dangerous_keywords:
        if re.search(rf'\b{kw}\b', sql_clean, re.IGNORECASE):
            return False
    # 4. Ensure it starts with safe read-only commands
    if not re.match(r'^(SELECT|WITH|EXPLAIN|SUMMARIZE)\b', sql_clean, re.IGNORECASE):
        return False
        
    return True

conn = get_connection(read_only=True)

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

for i, metric_name in enumerate(quick_metrics):
    with cols[i % 3]:
        if st.button(f"📊 {metric_name.replace('_', ' ').title()}", use_container_width=True):
            st.session_state["user_question"] = f"Show me the {metric_name.replace('_', ' ')}"

# --- 7. Query Interface ---
user_question = st.text_input(
    "Ask a question about the data:",
    placeholder="e.g., What is the total number of merged PRs for dbt-core?",
    value=st.session_state.get("user_question", ""),
    key="question_input"
)

if user_question:
    # Clear the session state after use
    if "user_question" in st.session_state:
        del st.session_state["user_question"]
    
    with st.spinner("🧠 AI is generating the SQL query..."):
        try:
            # Step A: Generate SQL
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SCHEMA_CONTEXT},
                    {"role": "user", "content": f"Write a DuckDB SQL query to answer this question: {user_question}"}
                ],
                temperature=0.0
            )
            
            sql_query = response.choices[0].message.content.strip()
            sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            
            st.code(sql_query, language="sql")
            
            # Step B: Validate & Execute the query
            if not validate_readonly_sql(sql_query):
                st.error("🛡️ **Security Guardrail Triggered:** The AI generated a query that attempted to modify data or execute multiple statements. It was blocked to protect the production database.")
            else:
                with st.spinner("🗄️ Executing query against MotherDuck..."):
                    df = conn.execute(sql_query).df()
                    
                    if df.empty:
                        st.info("The query ran successfully, but returned no results.")
                    else:
                        st.success("Query executed successfully!")
                        st.dataframe(df, use_container_width=True)
                        
                        # Step C: AI Summary
                        with st.spinner("📝 AI is summarizing the results..."):
                            summary_prompt = f"""
                            The user asked: "{user_question}"
                            The SQL query returned this data: {df.head(10).to_markdown()}
                            Provide a concise, 2-3 sentence business summary of these findings.
                            """
                            summary_response = client.chat.completions.create(
                                model=model,
                                messages=[{"role": "user", "content": summary_prompt}],
                                temperature=0.3
                            )
                            st.markdown("### 💡 AI Summary")
                            st.info(summary_response.choices[0].message.content)
                        
        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.markdown("*Tip: Try rephrasing your question to be more specific.*")