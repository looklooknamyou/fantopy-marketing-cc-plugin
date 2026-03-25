"""
Queue Monitor — view and manage pending items from all review queues.
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

st.set_page_config(page_title="Queue Monitor", page_icon="📋", layout="wide")

from theme import inject
inject()
st.title("📋 Queue Monitor")
st.caption("Review pending items from all agents. Approve or reject before sending.")

@st.cache_resource
def get_engine():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        return None
    from sqlalchemy import create_engine
    return create_engine(db_url, pool_pre_ping=True)

engine = get_engine()

def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    if engine is None:
        return pd.DataFrame()
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})
    except Exception as e:
        st.error(f"DB: {e}")
        return pd.DataFrame()

def run_update(sql: str, params: dict) -> None:
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text(sql), params)

if engine is None:
    st.error("DATABASE_URL not set.")
    st.stop()

# ── Queue selector ────────────────────────────────────────────────────────────

QUEUES = {
    "Agent 3 — Recruiter prospects": {
        "table": "recruiter_prospects",
        "cols": "id, source, github_username AS handle, profile_url, status, queued_at",
        "status_col": "status",
    },
    "Agent 9 — Intel log": {
        "table": "intel_log",
        "cols": "id, source, url, classification, seen_at",
        "status_col": None,
    },
    "Agent 2 — Scout queue": {
        "table": "scout_replied",
        "cols": "id, source, platform_id, url, status, queued_at",
        "status_col": "status",
    },
    "Agent 7 — Reddit drafts": {
        "table": "reddit_drafts",
        "cols": "id, subreddit, post_id, draft_type, fantopy_mention, status, queued_at",
        "status_col": "status",
    },
    "Agent 8 — Partnership log": {
        "table": "partnership_log",
        "cols": "id, source, target_name, opportunity_type, url, status, queued_at",
        "status_col": "status",
    },
    "Agent 11 — Influencer log": {
        "table": "influencer_log",
        "cols": "id, twitter_handle, fit_score, status",
        "status_col": "status",
    },
    "Agent 12 — Milestone log": {
        "table": "milestone_log",
        "cols": "id, milestone, detail, pitched, logged_at",
        "status_col": None,
    },
}

selected_q = st.selectbox("Select queue", list(QUEUES.keys()))
q = QUEUES[selected_q]

# Filter by status
status_filter = "PENDING"
if q["status_col"]:
    status_filter = st.radio("Filter", ["PENDING", "APPROVED", "REJECTED", "ALL"], horizontal=True)

where = ""
if q["status_col"] and status_filter != "ALL":
    where = f"WHERE {q['status_col']} = '{status_filter}'"

df = run_query(f"SELECT {q['cols']} FROM {q['table']} {where} ORDER BY 1 DESC LIMIT 100")

st.markdown(f"**{len(df)} rows**")
st.dataframe(df, use_container_width=True, hide_index=True)

# Bulk status update
if q["status_col"] and not df.empty:
    st.divider()
    st.subheader("Update status")
    col1, col2, col3 = st.columns(3)
    with col1:
        row_id = st.number_input("Row ID", min_value=1, value=int(df["id"].iloc[0]) if "id" in df.columns else 1)
    with col2:
        new_status = st.selectbox("New status", ["APPROVED", "REJECTED", "PENDING", "SENT"])
    with col3:
        st.write("")
        st.write("")
        if st.button("Update", type="primary"):
            run_update(
                f"UPDATE {q['table']} SET {q['status_col']} = :status WHERE id = :id",
                {"status": new_status, "id": row_id}
            )
            st.success(f"Row {row_id} → {new_status}")
            st.rerun()
