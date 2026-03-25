"""
Beat the Bot — register participants, view results, see leaderboard.
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

st.set_page_config(page_title="Beat the Bot", page_icon="🤖", layout="wide")

from theme import inject
inject()
st.title("🤖 Beat the Bot")
st.caption("Register participants, track results, view the season leaderboard.")

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

tab1, tab2, tab3, tab4 = st.tabs(["Register participant", "Participants", "Results", "Leaderboard"])

# ── Tab 1: Register ───────────────────────────────────────────────────────────

with tab1:
    st.subheader("Register a Beat the Bot participant")
    with st.form("register_form"):
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("Email *")
            name = st.text_input("Display name *")
            fpl_id = st.number_input("FPL entry ID *", min_value=1, value=1,
                                     help="Found in the FPL URL: fantasy.premierleague.com/entry/{ID}/history")
        with col2:
            agent_id = st.text_input("Target Fantopy agent ID *",
                                     help="The agent_id from the Fantopy platform they're challenging")
            agent_name = st.text_input("Agent display name (optional)")
            discord = st.text_input("Discord handle (optional)")

        submitted = st.form_submit_button("Register", type="primary")
        if submitted:
            if not all([email, name, fpl_id, agent_id]):
                st.error("Email, name, FPL ID, and agent ID are required.")
            else:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO challenge_participants
                              (email, name, fpl_entry_id, target_agent_id, target_agent_name, discord_handle)
                            VALUES (:email, :name, :fpl_id, :agent_id, :agent_name, :discord)
                            ON CONFLICT (email) DO UPDATE SET
                              fpl_entry_id = EXCLUDED.fpl_entry_id,
                              target_agent_id = EXCLUDED.target_agent_id,
                              active = TRUE
                        """), {
                            "email": email, "name": name, "fpl_id": fpl_id,
                            "agent_id": agent_id, "agent_name": agent_name, "discord": discord
                        })
                    st.success(f"Registered {name} ({email})")
                except Exception as e:
                    st.error(f"Error: {e}")

    # Test FPL ID lookup
    st.divider()
    st.subheader("Verify FPL entry ID")
    test_fpl_id = st.number_input("FPL entry ID to verify", min_value=1, value=1)
    if st.button("Look up on FPL API"):
        import httpx
        try:
            with st.spinner("Fetching from FPL API..."):
                r = httpx.get(f"https://fantasy.premierleague.com/api/entry/{test_fpl_id}/", timeout=10)
                r.raise_for_status()
                data = r.json()
                st.success(f"Found: **{data.get('player_first_name')} {data.get('player_last_name')}** "
                           f"— Team: {data.get('name')} — Overall rank: {data.get('summary_overall_rank'):,}")
        except Exception as e:
            st.error(f"FPL API error: {e}")

# ── Tab 2: Participants ───────────────────────────────────────────────────────

with tab2:
    st.subheader("Active participants")
    df = run_query("""
        SELECT id, name, email, fpl_entry_id, target_agent_id,
               target_agent_name, discord_handle, joined_at, active
        FROM challenge_participants ORDER BY joined_at DESC
    """)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if not df.empty:
        st.divider()
        st.subheader("Deactivate participant")
        deact_id = st.number_input("Participant ID to deactivate", min_value=1)
        if st.button("Deactivate"):
            with engine.begin() as conn:
                conn.execute(text("UPDATE challenge_participants SET active=FALSE WHERE id=:id"),
                             {"id": deact_id})
            st.success(f"Participant {deact_id} deactivated")
            st.rerun()

# ── Tab 3: Results ────────────────────────────────────────────────────────────

with tab3:
    st.subheader("GW results")
    col1, col2 = st.columns(2)
    with col1:
        gw_filter = st.number_input("Filter by gameweek (0 = all)", min_value=0, value=0)
    with col2:
        outcome_filter = st.selectbox("Outcome", ["ALL", "WIN", "LOSS", "DRAW"])

    where_clauses = []
    params = {}
    if gw_filter > 0:
        where_clauses.append("cr.gameweek = :gw")
        params["gw"] = gw_filter
    if outcome_filter != "ALL":
        where_clauses.append("cr.outcome = :oc")
        params["oc"] = outcome_filter

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    df = run_query(f"""
        SELECT cp.name, cp.target_agent_name AS agent,
               cr.gameweek, cr.human_points, cr.agent_points, cr.outcome, cr.recorded_at
        FROM challenge_results cr
        JOIN challenge_participants cp ON cp.id = cr.participant_id
        {where}
        ORDER BY cr.gameweek DESC, cp.name
    """, params)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Add manual result
    st.divider()
    st.subheader("Add manual result")
    with st.form("add_result"):
        participants_df = run_query("SELECT id, name FROM challenge_participants WHERE active=TRUE")
        if participants_df.empty:
            st.info("No active participants yet.")
        else:
            p_options = {f"{r['name']} (#{r['id']})": r['id'] for _, r in participants_df.iterrows()}
            selected_p = st.selectbox("Participant", list(p_options.keys()))
            c1, c2, c3 = st.columns(3)
            with c1: gw_m = st.number_input("Gameweek", min_value=1, max_value=38, value=1)
            with c2: h_pts = st.number_input("Human points", min_value=0, value=50)
            with c3: a_pts = st.number_input("Agent points", min_value=0, value=50)
            if st.form_submit_button("Save result"):
                outcome = "WIN" if h_pts > a_pts else ("LOSS" if a_pts > h_pts else "DRAW")
                pid = p_options[selected_p]
                try:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO challenge_results
                              (participant_id, gameweek, human_points, agent_points, outcome)
                            VALUES (:pid, :gw, :hp, :ap, :oc)
                            ON CONFLICT (participant_id, gameweek) DO NOTHING
                        """), {"pid": pid, "gw": gw_m, "hp": h_pts, "ap": a_pts, "oc": outcome})
                    st.success(f"Result saved: {outcome}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# ── Tab 4: Leaderboard ────────────────────────────────────────────────────────

with tab4:
    st.subheader("Season leaderboard")
    df = run_query("""
        SELECT
          cp.name,
          cp.target_agent_name AS challenging,
          COUNT(*) AS played,
          SUM(CASE WHEN cr.outcome='WIN' THEN 1 ELSE 0 END) AS wins,
          SUM(CASE WHEN cr.outcome='LOSS' THEN 1 ELSE 0 END) AS losses,
          SUM(CASE WHEN cr.outcome='DRAW' THEN 1 ELSE 0 END) AS draws,
          ROUND(100.0 * SUM(CASE WHEN cr.outcome='WIN' THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 1) AS win_pct,
          SUM(cr.human_points) AS total_human_pts,
          SUM(cr.agent_points) AS total_agent_pts
        FROM challenge_participants cp
        JOIN challenge_results cr ON cr.participant_id = cp.id
        WHERE cp.active = TRUE
        GROUP BY cp.id, cp.name, cp.target_agent_name
        ORDER BY win_pct DESC NULLS LAST, wins DESC
    """)

    if df.empty:
        st.info("No results yet. Register participants and add results first.")
    else:
        # Highlight winners
        def highlight(row):
            if row.get("win_pct", 0) and row["win_pct"] > 50:
                return ["background-color: #d4edda"] * len(row)
            elif row.get("win_pct", 0) and row["win_pct"] < 50:
                return ["background-color: #f8d7da"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df.style.apply(highlight, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        # Summary stats
        c1, c2, c3 = st.columns(3)
        c1.metric("Total participants", len(df))
        c2.metric("Humans winning", len(df[df["win_pct"] > 50]) if "win_pct" in df.columns else "-")
        c3.metric("Agents winning", len(df[df["win_pct"] < 50]) if "win_pct" in df.columns else "-")
