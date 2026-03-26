"""
Waitlist — add test signups, view email sequences, monitor nurturer log.
"""

import os
import sys
import pandas as pd
import streamlit as st
from sqlalchemy import text
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

st.set_page_config(page_title="Waitlist", page_icon="📧", layout="wide")

from theme import inject
inject()

st.title("Waitlist & Nurturer")

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

if engine is None:
    st.error("DATABASE_URL not set.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["Add test signup", "Waitlist signups", "Nurturer log"])

# ── Tab 1: Add signup ─────────────────────────────────────────────────────────

with tab1:
    st.subheader("Add a test waitlist signup")
    st.caption("Simulates a real signup — Agent 15 will pick it up on the next batch run.")
    with st.form("signup_form"):
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("Email *")
            name = st.text_input("Name")
            user_type = st.selectbox("User type", ["builder", "spectator"])
        with col2:
            framework = st.selectbox("Builder framework", ["LangChain", "CrewAI", "AutoGen", "Custom", ""])
            referral_code = st.text_input("Referral code (optional)")
            discord = st.text_input("Discord handle (optional)")

        submitted = st.form_submit_button("Add signup", type="primary")
        if submitted:
            if not email:
                st.error("Email is required.")
            else:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO waitlist_signups
                              (email, name, user_type, builder_framework, referral_code, discord_handle)
                            VALUES (:email, :name, :ut, :fw, :ref, :discord)
                            ON CONFLICT (email) DO UPDATE SET
                              user_type = EXCLUDED.user_type,
                              builder_framework = EXCLUDED.builder_framework
                        """), {
                            "email": email, "name": name, "ut": user_type,
                            "fw": framework or None, "ref": referral_code or None,
                            "discord": discord or None,
                        })
                    st.success(f"Signup added for {email}. Run Agent 15 batch to trigger email sequence.")
                except Exception as e:
                    st.error(f"Error: {e}")

    # Preview email sequence
    st.divider()
    st.subheader("Preview email sequence")

    agents_path = os.path.join(os.path.dirname(__file__), "..", "..", "agents")
    if agents_path not in sys.path:
        sys.path.insert(0, agents_path)

    try:
        import agent_15_waitlist_nurturer as a15

        pcol1, pcol2, pcol3 = st.columns([1, 1, 1])
        with pcol1:
            preview_type = st.selectbox("Sequence", ["builder", "spectator"])
        with pcol2:
            preview_framework = st.selectbox("Framework", ["LangChain", "CrewAI", "AutoGen", "Custom"])
        with pcol3:
            sequence = a15.BUILDER_SEQUENCE if preview_type == "builder" else a15.SPECTATOR_SEQUENCE
            day_labels = [f"Email {i+1} — Day {day}" for i, (day, _) in enumerate(sequence)]
            preview_idx = st.select_slider("Email", options=list(range(len(sequence))), format_func=lambda i: day_labels[i])

        fake_signup = {
            "email": "preview@test.com",
            "name": "Test User",
            "user_type": preview_type,
            "builder_framework": preview_framework,
        }
        day_offset, email_fn = sequence[preview_idx]
        subject, html = email_fn(fake_signup)

        st.markdown(f"**Subject:** `{subject}`  ·  **Scheduled:** Day {day_offset}")
        st.divider()
        st.components.v1.html(html, height=500, scrolling=True)

    except Exception as e:
        st.error(f"Preview failed: {e}")

# ── Tab 2: Signups ────────────────────────────────────────────────────────────

with tab2:
    st.subheader("Waitlist signups")
    df = run_query("""
        SELECT id, email, name, user_type, builder_framework,
               referral_code, signed_up_at
        FROM waitlist_signups ORDER BY signed_up_at DESC LIMIT 100
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if not df.empty:
        c1, c2 = st.columns(2)
        c1.metric("Total signups", len(df))
        builders = len(df[df["user_type"] == "builder"]) if "user_type" in df.columns else 0
        c2.metric("Builders", builders)

# ── Tab 3: Nurturer log ───────────────────────────────────────────────────────

with tab3:
    st.subheader("Nurturer email log")
    df = run_query("""
        SELECT n.email, n.sequence_name, n.email_index,
               n.sent_at, n.status, n.resend_id
        FROM nurturer_log n ORDER BY n.sent_at DESC LIMIT 200
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if not df.empty:
        st.divider()
        st.subheader("Sequence completion by email")
        summary = run_query("""
            SELECT email, sequence_name,
                   COUNT(*) AS emails_sent,
                   MAX(email_index) AS last_email_sent
            FROM nurturer_log
            GROUP BY email, sequence_name
            ORDER BY emails_sent DESC
        """)
        st.dataframe(summary, use_container_width=True, hide_index=True)
