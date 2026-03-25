"""
Fantopy Marketing Dashboard — Main entry point
Run: streamlit run dashboard/Home.py
"""

import os
import sys
import pandas as pd
import streamlit as st
from datetime import datetime

# Add parent dir so shared modules resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="Fantopy Marketing Ops",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

from theme import inject
inject()

st.title("Fantopy Marketing Ops")
st.caption("Agent fleet dashboard  ·  " + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))

# ── DB connection check ───────────────────────────────────────────────────────

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

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
            from sqlalchemy import text
            return pd.read_sql(text(sql), conn, params=params)
    except Exception as e:
        st.error(f"DB error: {e}")
        return pd.DataFrame()

# ── Connection status ─────────────────────────────────────────────────────────

col_status, col_env = st.columns([1, 2])

with col_status:
    if engine is None:
        st.error("DATABASE_URL not set — add it to .env")
    else:
        try:
            run_query("SELECT 1")
            st.success("Postgres connected")
        except Exception as e:
            st.error(f"DB connection failed: {e}")

with col_env:
    keys = {
        "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "GITHUB_TOKEN": bool(os.environ.get("GITHUB_TOKEN")),
        "TWITTER_BEARER_TOKEN": bool(os.environ.get("TWITTER_BEARER_TOKEN")),
        "RESEND_API_KEY": bool(os.environ.get("RESEND_API_KEY")),
        "DISCORD_WEBHOOK_URL": bool(os.environ.get("DISCORD_WEBHOOK_URL")),
        "RECRUITER_SHEET_ID": bool(os.environ.get("RECRUITER_SHEET_ID")),
        "FANTOPY_API_KEY": bool(os.environ.get("FANTOPY_API_KEY")),
    }
    set_count = sum(keys.values())
    st.info(f"{set_count}/{len(keys)} credentials configured")
    with st.expander("Credential status"):
        for k, v in keys.items():
            st.write(f"{'✅' if v else '❌'} `{k}`")

st.divider()

# ── Table row counts ──────────────────────────────────────────────────────────

st.subheader("Database — table sizes")

TABLES = [
    ("recruiter_prospects", "Agent 3"),
    ("nurturer_log", "Agent 15"),
    ("waitlist_signups", "Platform"),
    ("intel_log", "Agent 9"),
    ("scout_replied", "Agent 2"),
    ("content_topics", "Agent 4"),
    ("content_log", "Agent 4"),
    ("broadcaster_history", "Agent 1"),
    ("broadcaster_log", "Agent 1"),
    ("challenge_participants", "Agent 14"),
    ("challenge_results", "Agent 14"),
    ("seo_log", "Agent 6"),
    ("reddit_drafts", "Agent 7"),
    ("partnership_log", "Agent 8"),
    ("influencer_log", "Agent 11"),
    ("milestone_log", "Agent 12"),
    ("press_log", "Agent 12"),
    ("community_replies", "Agent 13"),
    ("referral_codes", "Agent 10"),
    ("referral_payouts", "Agent 10"),
]

counts = {}
if engine is not None:
    for table, agent in TABLES:
        try:
            df = run_query(f"SELECT COUNT(*) AS n FROM {table}")
            counts[table] = (agent, int(df["n"].iloc[0]) if not df.empty else 0)
        except Exception:
            counts[table] = (agent, "table missing")

cols = st.columns(4)
for i, (table, (agent, count)) in enumerate(counts.items()):
    with cols[i % 4]:
        color = "normal" if isinstance(count, int) and count > 0 else "off"
        st.metric(
            label=f"{table}",
            value=str(count),
            help=f"Used by {agent}",
        )

st.divider()

# ── Recent activity ───────────────────────────────────────────────────────────

st.subheader("Recent activity")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Agent 3 — Last prospects**")
    df = run_query("""
        SELECT github_username AS handle, source, status, queued_at
        FROM recruiter_prospects ORDER BY queued_at DESC LIMIT 5
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

with col2:
    st.markdown("**Agent 15 — Last emails sent**")
    df = run_query("""
        SELECT email, sequence_name, email_index, sent_at
        FROM nurturer_log ORDER BY sent_at DESC LIMIT 5
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

with col3:
    st.markdown("**Agent 14 — Last GW results**")
    df = run_query("""
        SELECT cp.name, cr.gameweek, cr.human_points,
               cr.agent_points, cr.outcome, cr.recorded_at
        FROM challenge_results cr
        JOIN challenge_participants cp ON cp.id = cr.participant_id
        ORDER BY cr.recorded_at DESC LIMIT 5
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)
