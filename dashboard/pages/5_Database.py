"""
Database Explorer — browse any table, run read-only queries.
"""

import os
import sys
import pandas as pd
import streamlit as st
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

st.set_page_config(page_title="Database", page_icon="🗄️", layout="wide")

from theme import inject
inject()

st.title("Database Explorer")

@st.cache_resource
def get_engine():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return None
    from sqlalchemy import create_engine
    return create_engine(db_url, pool_pre_ping=True)

engine = get_engine()

def run_query(sql: str) -> pd.DataFrame:
    if engine is None:
        return pd.DataFrame()
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn)
    except Exception as e:
        st.error(f"DB: {e}")
        return pd.DataFrame()

if engine is None:
    st.error("DATABASE_URL not set.")
    st.stop()

# ── Table browser ─────────────────────────────────────────────────────────────

ALL_TABLES = [
    "recruiter_prospects", "nurturer_log", "waitlist_signups",
    "intel_log", "scout_replied", "content_topics", "content_log",
    "broadcaster_history", "broadcaster_log",
    "challenge_participants", "challenge_results",
    "seo_log", "reddit_drafts", "partnership_log",
    "influencer_log", "milestone_log", "press_log",
    "community_replies", "referral_codes", "referral_payouts",
]

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    table = st.selectbox("Table", ALL_TABLES)
with col2:
    limit = st.number_input("Row limit", min_value=10, max_value=1000, value=50)
with col3:
    order = st.selectbox("Order", ["DESC", "ASC"])

df = run_query(f"SELECT * FROM {table} ORDER BY 1 {order} LIMIT {limit}")

st.markdown(f"**{len(df)} rows** from `{table}`")
st.dataframe(df, use_container_width=True, hide_index=True)

# Row counts for all tables
st.divider()
st.subheader("All table sizes")

count_rows = []
for t in ALL_TABLES:
    try:
        df_c = run_query(f"SELECT COUNT(*) AS n FROM {t}")
        count_rows.append({"table": t, "rows": int(df_c["n"].iloc[0]) if not df_c.empty else 0})
    except Exception:
        count_rows.append({"table": t, "rows": "missing"})

count_df = pd.DataFrame(count_rows)
st.dataframe(count_df, use_container_width=True, hide_index=True)

# ── Custom read-only query ────────────────────────────────────────────────────

st.divider()
st.subheader("Custom read-only query")
st.caption("SELECT queries only. No writes.")

custom_sql = st.text_area(
    "SQL",
    value="SELECT * FROM waitlist_signups LIMIT 10",
    height=100,
)

if st.button("Run query"):
    sql_clean = custom_sql.strip().upper()
    if not sql_clean.startswith("SELECT"):
        st.error("Only SELECT queries allowed.")
    else:
        result = run_query(custom_sql)
        st.dataframe(result, use_container_width=True, hide_index=True)
