"""
Agent Runner — manually trigger any agent from the dashboard.
"""

import os
import sys
import subprocess
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

st.set_page_config(page_title="Agent Runner", page_icon="▶️", layout="wide")

from theme import inject
inject()

st.title("Agent Runner")
st.caption("Manually trigger any agent. Output streams in real time.")

AGENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "agents")

AGENTS = {
    "Agent 3 — Recruiter": {
        "file": "agent_03_recruiter.py",
        "description": "Searches GitHub + Twitter for FPL builders. Writes outreach drafts to Sheets.",
        "args": [],
    },
    "Agent 15 — Waitlist Nurturer (batch)": {
        "file": "agent_15_waitlist_nurturer.py",
        "description": "Sends any due emails in the nurturer sequences.",
        "args": ["--batch"],
    },
    "Agent 9 — Competitor Monitor": {
        "file": "agent_09_competitor_monitor.py",
        "description": "Scans Twitter, GitHub, Product Hunt for competitor signals.",
        "args": [],
    },
    "Agent 1 — Broadcaster (poll)": {
        "file": "agent_01_broadcaster.py",
        "description": "Polls for new scored contests and posts results.",
        "args": ["--poll"],
    },
    "Agent 14 — Beat the Bot (results)": {
        "file": "agent_14_beat_the_bot.py",
        "description": "Fetches GW results for all active participants.",
        "args": ["--results"],
    },
    "Agent 14 — Beat the Bot (leaderboard)": {
        "file": "agent_14_beat_the_bot.py",
        "description": "Posts season leaderboard to Discord.",
        "args": ["--leaderboard"],
    },
    "Agent 2 — Scout": {
        "file": "agent_02_scout.py",
        "description": "Scans Twitter + Reddit for reply opportunities.",
        "args": [],
    },
    "Agent 4 — Content Writer": {
        "file": "agent_04_content_writer.py",
        "description": "Writes one blog post draft to Sheets.",
        "args": [],
    },
    "Agent 6 — SEO Farmer": {
        "file": "agent_06_seo_farmer.py",
        "description": "Writes one SEO post draft to Sheets.",
        "args": [],
    },
    "Agent 7 — Reddit Persona": {
        "file": "agent_07_reddit_persona.py",
        "description": "Drafts Reddit replies/posts to Sheets.",
        "args": [],
    },
    "Agent 8 — Partnership Scout": {
        "file": "agent_08_partnership_scout.py",
        "description": "Finds framework/hackathon opportunities and drafts pitches.",
        "args": [],
    },
    "Agent 11 — Influencer Identifier": {
        "file": "agent_11_influencer_identifier.py",
        "description": "Finds high-fit influencers and drafts collab pitches.",
        "args": [],
    },
    "Agent 12 — Press Pitcher": {
        "file": "agent_12_press_pitcher.py",
        "description": "Finds journalists and drafts press pitches.",
        "args": [],
    },
    "Agent 10 — Referral Tracker": {
        "file": "agent_10_referral_tracker.py",
        "description": "Generates referral codes, tracks counts, queues USDC payouts.",
        "args": [],
    },
    "Agent 13 — Community Manager": {
        "file": "agent_13_community_manager.py",
        "description": "Starts the always-on Discord bot. Requires DISCORD_BOT_TOKEN. Runs until manually stopped.",
        "args": [],
    },
}

selected = st.selectbox("Select agent to run", list(AGENTS.keys()))
agent = AGENTS[selected]

st.markdown(f"**{selected}**")
st.caption(agent["description"])

# Extra args for specific agents
extra_args = []
if "Nurturer" in selected:
    signup_id = st.number_input("Or run for specific signup ID (0 = batch mode)", min_value=0, value=0)
    if signup_id > 0:
        extra_args = ["--signup-id", str(signup_id)]
    else:
        extra_args = ["--batch"]

if "Broadcaster" in selected and "poll" not in selected.lower():
    contest_id = st.text_input("Contest ID (optional)")
    if contest_id:
        extra_args = ["--contest-id", contest_id]

if "Beat the Bot" in selected and "results" in selected.lower():
    gw = st.number_input("Gameweek (0 = current)", min_value=0, value=0)
    if gw > 0:
        extra_args += ["--gameweek", str(gw)]
    contest_id = st.text_input("Fantopy contest ID for this GW (optional)")
    if contest_id:
        extra_args += ["--contest-id", contest_id]

if "Press" in selected:
    milestone = st.text_input("Milestone description (optional)")
    if milestone:
        extra_args = ["--milestone", milestone]

run_btn = st.button(f"▶ Run {selected}", type="primary")

if run_btn:
    script = os.path.join(AGENTS_DIR, agent["file"])
    cmd = [sys.executable, script] + (extra_args or agent["args"])

    st.info(f"Running: `{' '.join(cmd)}`")
    output_box = st.empty()
    output_lines = []

    with st.spinner("Running..."):
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={**os.environ},
                cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
            )
            for line in proc.stdout:
                output_lines.append(line.rstrip())
                output_box.code("\n".join(output_lines[-50:]), language="bash")
            proc.wait()
            if proc.returncode == 0:
                st.success(f"Completed (exit 0)")
            else:
                st.error(f"Exited with code {proc.returncode}")
        except FileNotFoundError:
            st.error(f"Script not found: {script}")
        except Exception as e:
            st.error(f"Error: {e}")
