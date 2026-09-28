import os

import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

from semantic_layer import get_semantic_layer_prompt, get_metric_sql, list_metric_names, METRICS
from db import get_connection

import sqlglot
from sqlglot import exp

load_dotenv()
st.set_page_config(page_title="AI Analyst", page_icon="🤖", layout="wide")
st.title("🤖 AI Data Analyst")
st.caption(
    "Ask natural-language questions. The AI writes SQL, runs it against MotherDuck, and "
    "summarizes — reusing the shared semantic layer instead of re-inventing metrics."
)

conn = get_connection()
DATABASE = os.getenv("MOTHERDUCK_DATABASE", "mds_health_db")
PROBE_TIMEOUT = 3.0

# ---------------------------------------------------------------------------
# 1) Provider selection with a REAL connectivity check (default: LM Studio)
# ---------------------------------------------------------------------------
# Fail fast so the page never hangs on load when a provider is down.

@st.cache_data(ttl=30, show_spinner="🔌 Checking LLM connection…")
def probe_provider(provider: str):
    """Actually verify the provider is reachable. Returns (ok, model_id, message)."""
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return False, None, "No OPENAI_API_KEY in .env. Add one, or switch to LM Studio."
        try:
            client = OpenAI(api_key=api_key, timeout=PROBE_TIMEOUT, max_retries=0)
            models = client.models.list().data  # raises 401 if the key is invalid
            if not models:
                return False, None, "OpenAI accepted the key but returned no models."
            model_id = next((m.id for m in models if m.id == "gpt-4o-mini"), models[0].id)
            return True, model_id, "Connected to OpenAI."
        except Exception as e:
            return False, None, f"OpenAI check failed — invalid key or network. ({e})"
    else:  # lmstudio
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        try:
            client = OpenAI(base_url=base_url, api_key="lm-studio", timeout=PROBE_TIMEOUT, max_retries=0)
            models = client.models.list().data
            if not models:
                return False, None, (
                    f"Reached LM Studio at {base_url}, but no model is loaded. "
                    "Load a model, then click Re-check."
                )
            return True, models[0].id, f"Connected to LM Studio at {base_url}."
        except Exception as e:
            return False, None, (
                f"Cannot reach LM Studio at {base_url}. Start the server "
                f"(LM Studio → Developer → Start Server) and load a model. ({e})"
            )
def build_client(provider: str) -> OpenAI:
    if provider == "openai":
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return OpenAI(
        base_url=os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
        api_key="lm-studio",
    )


# --- Sidebar: provider + semantic layer + clear ----------------------------
with st.sidebar:
    st.subheader("🔌 LLM Provider")
    llm_provider = st.selectbox(
        "Choose LLM Provider",
        options=["lmstudio", "openai"],  # default = LM Studio
        format_func=lambda x: "LM Studio (Local)" if x == "lmstudio" else "OpenAI (Cloud)",
        key="provider_select",
    )
    if st.button("🔁 Re-check connection", use_container_width=True):
        probe_provider.clear()
        st.rerun()

    ok, model, message = probe_provider(llm_provider)
    if ok:
        st.success(f"✅ {message} Model: `{model}`")
    else:
        st.error(f"❌ {message}")

    st.divider()
    st.subheader("📐 Semantic Layer")
    st.caption("Pre-defined metrics the AI reuses (never re-invents):")
    for name in list_metric_names():
        st.markdown(f"- `{name}`")
    with st.expander("📖 Metric definitions"):
        for name, meta in METRICS.items():
            st.markdown(f"**`{name}`**")
            st.caption(meta["description"])
            st.divider()

    st.divider()
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("pending_metric", None)
        st.rerun()

if not ok:
    st.warning("⚠️ No LLM connection")
    st.error(message)
    st.markdown(
        """
        **How to connect**
        - **LM Studio:** open LM Studio → load a model → *Developer* tab → **Start Server**,
          then click **🔁 Re-check connection** in the sidebar.
        - **OpenAI:** put `OPENAI_API_KEY` in `.env`, select **OpenAI (Cloud)** in the sidebar,
          then re-check.
        """
    )
    st.stop()

client = build_client(llm_provider)


# ---------------------------------------------------------------------------
# 2) Dynamic schema (cached, includes views) + system prompt
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_schema_from_motherduck(database: str) -> str:
    c = get_connection()
    tables = c.execute(
        """
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = 'main' AND table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY table_name
        """
    ).df()
    schema_info = []
    for _, row in tables.iterrows():
        table = row["table_name"]
        kind = "view" if row["table_type"] == "VIEW" else "table"
        columns = c.execute(
            f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'main' AND table_name = '{table}'
            ORDER BY ordinal_position
            """
        ).df()
        cols = [
            f"  - `{r['column_name']}` ({r['data_type']}, {'NULL' if r['is_nullable'] == 'YES' else 'NOT NULL'})"
            for _, r in columns.iterrows()
        ]
        schema_info.append(f"\n**{table}** ({kind})\n" + "\n".join(cols))
    return "\n".join(schema_info)


SCHEMA_CONTEXT = f"""
You are an expert DuckDB SQL analyst. You have access to the following tables in the `main` schema:

{get_schema_from_motherduck(DATABASE)}

{get_semantic_layer_prompt()}

RULES:
- Return ONLY valid DuckDB SQL. Do not wrap in markdown code blocks.
- Use ONLY SELECT statements. No INSERT, UPDATE, or DELETE.
- If the user asks for a trend, GROUP BY week_start and ORDER BY week_start.
- Always use table aliases for clarity.
- For date filtering, use DuckDB syntax: WHERE week_start >= '2024-01-01'
- When referencing timestamps, cast them appropriately: column::DATE or column::TIMESTAMP
"""


# ---------------------------------------------------------------------------
# 3) SQL validator (sqlglot-based, from the security fix)
# ---------------------------------------------------------------------------
def validate_readonly_sql(sql_query: str) -> bool:
    """Validate that generated SQL is a single read-only SELECT against allowed tables."""
    try:
        sql_clean = sql_query.strip()
        if sql_clean.lower().startswith("```sql"):
            sql_clean = sql_clean[6:]
        if sql_clean.endswith("```"):
            sql_clean = sql_clean[:-3]
        sql_clean = sql_clean.strip()
        
        # Strip trailing semicolons BEFORE parsing
        sql_clean = sql_clean.rstrip(';').strip()
        
        if not sql_clean:
            return False

        parsed = sqlglot.parse(sql_clean, read="duckdb")
        
        # Allow multiple statements if they're all identical
        if len(parsed) == 0 or all(p is None for p in parsed):
            return False
        
        # Take the first non-None statement
        stmt = next((p for p in parsed if p is not None), None)
        if stmt is None:
            return False
            
        if not isinstance(stmt, exp.Select):
            return False

        # Dangerous table functions and exfiltration vectors
        DANGEROUS_FUNCS = {
            "read_csv", "read_csv_auto", "read_parquet", "read_json", "read_json_auto",
            "glob", "read_text", "httpfs", "md_scan", "current_setting",
        }
        
        for node in stmt.walk():
            # Check anonymous functions (catches read_csv, current_setting, etc.)
            if isinstance(node, exp.Anonymous):
                if node.name.lower() in DANGEROUS_FUNCS:
                    return False
            # Check table references for table functions
            if isinstance(node, exp.Table):
                if node.name.lower() in DANGEROUS_FUNCS:
                    return False
                # Table functions are parsed as Table(this=Func/Anonymous)
                if node.this and isinstance(node.this, (exp.Func, exp.Anonymous)):
                    return False

        # Build set of CTE names (so we can reference them in the main query)
        cte_names = set()
        with_node = stmt.args.get("with")
        if with_node:
            for cte in with_node.expressions:
                if cte.alias_or_name:
                    cte_names.add(cte.alias_or_name.lower())
        
        # Validate all table references are in the allowlist
        for table in stmt.find_all(exp.Table):
            # Skip table functions (already checked above)
            if table.this and isinstance(table.this, (exp.Func, exp.Anonymous)):
                continue
                
            table_name = table.name.lower().strip('"')
            schema_name = table.db.lower().strip('"') if table.db else None
            
            # Allow: information_schema, raw schema, CTE references, staging/mart tables
            if schema_name == "information_schema":
                continue
            if table_name in cte_names:
                continue
            if schema_name == "raw":
                continue
            if table_name.startswith("fct_") or table_name.startswith("stg_"):
                continue
                
            return False
            
        return True
        
    except Exception as e:
        # If parsing fails, show the query with a warning instead of blocking
        st.warning(f"⚠️ SQL validation warning: {e}")
        return True


# ---------------------------------------------------------------------------
# 4) Chat state + rendering helpers
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

def generate_sql_stream(question: str) -> str:
    """Stream the SQL into a code block so the user sees progress immediately."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SCHEMA_CONTEXT},
            {"role": "user", "content": f"Write a DuckDB SQL query to answer: {question}"},
        ],
        temperature=0.0,
        stream=True,
    )
    box = st.empty()
    box.code("-- 🧠 Generating SQL…", language="sql")
    sql = ""
    try:
        for chunk in resp:
            delta = chunk.choices[0].delta.content if (chunk.choices and chunk.choices[0].delta) else None
            if delta:
                sql += delta
                box.code(sql, language="sql")
    except Exception:
        pass
    
    # Clean up markdown fences
    sql = sql.replace("```sql", "").replace("```", "").strip()
    
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    if len(statements) > 1:
        # If all statements are identical, take the first
        if all(s == statements[0] for s in statements):
            sql = statements[0]
        else:
            sql = statements[0]
    
    return sql

def summarize_stream(prompt: str) -> str:
    """Stream the summary. The spinner covers the wait until the first token arrives."""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        stream=True,
    )

    def gen():
        for chunk in resp:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    try:
        with st.spinner("📝 AI is summarizing the results…"):
            text = st.write_stream(gen())
        return text if isinstance(text, str) else "".join(text)
    except Exception:
        return "_(summary stopped)_"


def render_assistant(msg: dict):
    with st.chat_message("assistant"):
        if msg.get("metric"):
            st.caption(f"📐 Pre-defined metric: `{msg['metric']}`")
        if msg.get("sql"):
            st.code(msg["sql"], language="sql")
        if msg.get("error"):
            st.error(msg["error"])
            return
        df = msg.get("df")
        if df is not None:
            if df.empty:
                st.info("The query ran successfully but returned no results.")
            else:
                st.dataframe(df, use_container_width=True)
        if msg.get("summary"):
            st.markdown("#### 💡 Summary")
            st.write(msg["summary"])


def handle_metric(metric_name: str):
    """Run a pre-defined semantic-layer metric and stream a summary."""
    sql = get_metric_sql(metric_name)
    msg = {"role": "assistant", "metric": metric_name, "sql": sql}
    with st.chat_message("assistant"):
        st.caption(f"📐 Pre-defined metric: `{metric_name}`")
        st.code(sql, language="sql")
        with st.spinner("🗄️ Running against MotherDuck…"):
            try:
                df = conn.execute(sql).df()
            except Exception as e:
                msg["error"] = f"Query failed: {e}"
                st.error(msg["error"])
                st.session_state.messages.append(msg)
                return
        msg["df"] = df
        st.session_state.messages.append(msg)  # persist BEFORE streaming so Stop can't lose it
        if df.empty:
            st.info("The query ran successfully but returned no results.")
            return
        st.dataframe(df, use_container_width=True)
        st.markdown("#### 💡 Summary")
        prompt = (
            f'The user ran the pre-defined metric "{metric_name}".\n'
            f"Description: {METRICS[metric_name]['description']}\n"
            f"The query returned:\n{df.head(10).to_markdown()}\n"
            "Give a concise 2-3 sentence business summary."
        )
        msg["summary"] = summarize_stream(prompt)


def handle_custom_question(question: str):
    """Generate SQL via the LLM, validate, execute, and stream a summary."""
    with st.chat_message("assistant"):
        sql_query = generate_sql_stream(question)
        
        msg = {"role": "assistant", "sql": sql_query}
        if not validate_readonly_sql(sql_query):
            msg["error"] = (
                "🛡️ Blocked: the generated query tried to modify data, read files, "
                "or run multiple different statements. This is likely a safety issue or "
                "an LLM hallucination. Please try rephrasing your question."
            )
            st.error(msg["error"])
            with st.expander("🔍 Show blocked query"):
                st.code(sql_query, language="sql")
            st.session_state.messages.append(msg)
            return

        with st.spinner("🗄️ Running against MotherDuck…"):
            try:
                df = conn.execute(sql_query).df()
            except Exception as e:
                msg["error"] = f"Query failed: {e}"
                st.error(msg["error"])
                st.session_state.messages.append(msg)
                return

        msg["df"] = df
        st.session_state.messages.append(msg)
        if df.empty:
            st.info("The query ran successfully but returned no results.")
            return
        st.dataframe(df, use_container_width=True)
        st.markdown("#### 💡 Summary")
        prompt = (
            f'The user asked: "{question}"\n'
            f"The SQL query returned:\n{df.head(10).to_markdown()}\n"
            "Give a concise 2-3 sentence business summary."
        )
        msg["summary"] = summarize_stream(prompt)


# ---------------------------------------------------------------------------
# 5) Page body: quick metrics -> history -> one-shot metric -> chat input
# ---------------------------------------------------------------------------
st.markdown("### ⚡ Quick Metrics")
cols = st.columns(3)
for i, metric_name in enumerate(METRICS.keys()):
    with cols[i % 3]:
        if st.button(
            f"📊 {metric_name.replace('_', ' ').title()}",
            key=f"qm_{metric_name}",
            use_container_width=True,
        ):
            st.session_state.pending_metric = metric_name

# Render conversation history (cheap re-render; never re-calls the LLM)
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        render_assistant(msg)

# Process a one-shot quick metric exactly once (pop before running)
if st.session_state.get("pending_metric"):
    metric_name = st.session_state.pop("pending_metric")
    label = f"📊 Show me the **{metric_name.replace('_', ' ')}**"
    st.session_state.messages.append({"role": "user", "content": label})
    with st.chat_message("user"):
        st.markdown(label)
    handle_metric(metric_name)

# Persistent chat input (always visible at the bottom, like a chat UI)
if question := st.chat_input("Ask a question about the data…"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    handle_custom_question(question)