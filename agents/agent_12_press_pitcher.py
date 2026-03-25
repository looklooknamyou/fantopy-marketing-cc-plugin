"""
================================================================================
AGENT 12: THE PRESS PITCHER
================================================================================
TRIGGER:      Event-driven — fires when a Fantopy milestone is logged
              OR: python agent_12_press_pitcher.py --milestone "<description>"
              Weekly passive scan: Sunday 09:00 UTC cron
INPUTS:       Twitter API (journalist discovery), milestone_log table
OUTPUTS:      Tailored press pitches per journalist → Google Sheets queue
HUMAN REVIEW: YES — always. No press pitch ever sends automatically.
BUILD:        At first major milestone (first USDC payout / 100 agents / Season 1 winner)
BLOCKED ON:   Twitter bearer token, Google Sheets
================================================================================

MILESTONE TRIGGERS (from workflow doc):
  - First USDC payout processed
  - 100 agents registered
  - Season 1 winner announced
  - 1000 waitlist signups
  - First human beats a top-ranked agent in Beat the Bot

JOURNALIST TARGETING:
  Criteria: covers AI + crypto + sports intersection
  Sources: Twitter search for journalists who've written about:
    - AI in sports/gaming
    - Crypto gaming / GameFi
    - Fantasy sports technology
    - Autonomous AI agents
  Avoid: pure crypto/DeFi journalists, pure sports journalists with no tech angle

PITCH STRUCTURE:
  Subject line: specific, numerical, milestone-led
  Body:
    1. Hook — the milestone with a number
    2. What Fantopy is — one sentence
    3. Why it's a story — the angle for their beat
    4. Simple ask — 20-min call or written Q&A
================================================================================
"""

import os
import sys
import logging
import datetime
import json
import httpx
import tweepy
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session
from shared.sheets import append_to_queue, get_sheet
from shared.llm import ask

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_12_press")

TWITTER_BEARER  = os.environ.get("TWITTER_BEARER_TOKEN", "")
SHEET_ID        = os.environ.get("RECRUITER_SHEET_ID", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

SHEET_HEADERS = [
    "timestamp", "journalist_handle", "outlet", "beat_summary",
    "milestone", "email_subject", "pitch_draft",
    "contact_url", "status", "notes"
]

JOURNALIST_QUERIES = [
    '"AI gaming" journalist OR reporter OR writer -is:retweet lang:en min_faves:5',
    '"crypto gaming" reporter OR journalist -is:retweet lang:en min_faves:5',
    '"fantasy sports" technology AI -is:retweet lang:en min_faves:5',
    '"autonomous agents" gaming OR sports -is:retweet lang:en min_faves:5',
    '"AI agents" interesting story OR launch OR first -is:retweet lang:en min_faves:10',
]

JOURNALIST_BIO_KEYWORDS = [
    "journalist", "reporter", "writer", "editor",
    "correspondent", "@techcrunch", "@wired", "@decrypt",
    "@coindesk", "@theguardian", "@bbc", "@forbes"
]

# ── DB helpers ────────────────────────────────────────────────────────────────

def ensure_tables() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS milestone_log (
                id SERIAL PRIMARY KEY,
                milestone TEXT NOT NULL,
                detail TEXT,
                logged_at TIMESTAMPTZ DEFAULT NOW(),
                pitched BOOLEAN DEFAULT FALSE
            )
        """))
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS press_log (
                id SERIAL PRIMARY KEY,
                journalist_handle TEXT NOT NULL,
                milestone TEXT,
                queued_at TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'PENDING',
                UNIQUE (journalist_handle, milestone)
            )
        """))
        session.commit()


def log_milestone(milestone: str, detail: str = "") -> int:
    with Session() as session:
        result = session.execute(text("""
            INSERT INTO milestone_log (milestone, detail)
            VALUES (:m, :d) RETURNING id
        """), {"m": milestone, "d": detail})
        session.commit()
        return result.fetchone()[0]


def get_unpitched_milestone() -> dict | None:
    with Session() as session:
        row = session.execute(text("""
            SELECT id, milestone, detail FROM milestone_log
            WHERE pitched = FALSE ORDER BY logged_at DESC LIMIT 1
        """)).mappings().fetchone()
        return dict(row) if row else None


def mark_milestone_pitched(milestone_id: int) -> None:
    with Session() as session:
        session.execute(text(
            "UPDATE milestone_log SET pitched = TRUE WHERE id = :id"
        ), {"id": milestone_id})
        session.commit()


def already_pitched(handle: str, milestone: str) -> bool:
    with Session() as session:
        return session.execute(text("""
            SELECT 1 FROM press_log WHERE journalist_handle = :h AND milestone = :m LIMIT 1
        """), {"h": handle.lower(), "m": milestone}).fetchone() is not None


def log_pitch(handle: str, milestone: str) -> None:
    with Session() as session:
        try:
            session.execute(text("""
                INSERT INTO press_log (journalist_handle, milestone)
                VALUES (:h, :m) ON CONFLICT DO NOTHING
            """), {"h": handle.lower(), "m": milestone})
            session.commit()
        except Exception as e:
            log.warning(f"DB log failed: {e}")


# ── Journalist discovery ──────────────────────────────────────────────────────

def is_journalist(user) -> bool:
    bio = (user.description or "").lower()
    return any(kw.lower() in bio for kw in JOURNALIST_BIO_KEYWORDS)


def discover_journalists() -> list[dict]:
    if not TWITTER_BEARER:
        return []
    client = tweepy.Client(bearer_token=TWITTER_BEARER, wait_on_rate_limit=True)
    seen = set()
    journalists = []

    for query in JOURNALIST_QUERIES:
        try:
            resp = client.search_recent_tweets(
                query=query, max_results=10,
                tweet_fields=["author_id", "text"],
                expansions=["author_id"],
                user_fields=["username", "name", "description", "public_metrics", "url"],
            )
            if not resp.data:
                continue
            users_by_id = {u.id: u for u in (resp.includes.get("users") or [])}
            for tweet in resp.data:
                user = users_by_id.get(tweet.author_id)
                if not user or user.username in seen:
                    continue
                seen.add(user.username)
                if not is_journalist(user):
                    continue
                followers = (user.public_metrics or {}).get("followers_count", 0)
                if followers < 500:
                    continue
                journalists.append({
                    "handle": user.username,
                    "name": user.name,
                    "bio": user.description or "",
                    "followers": followers,
                    "profile_url": f"https://twitter.com/{user.username}",
                    "sample_tweet": tweet.text[:200],
                })
        except tweepy.TweepyException as e:
            log.error(f"Twitter error: {e}")

    return journalists


# ── LLM: Classify beat + draft pitch ──────────────────────────────────────────

BEAT_SYSTEM = """Given a journalist's Twitter bio and recent tweet, identify their beat in 10 words or less.
Examples: "AI/crypto tech reporter", "sports technology writer", "GameFi & blockchain gaming journalist"
Output ONLY the beat description."""

PITCH_SYSTEM = """You are writing a press pitch email for Fantopy Arena —
an AI agent vs agent Fantasy Premier League competition platform.

Write a SHORT pitch email (≤180 words):
  Subject line: milestone-specific, numerical hook
  Body:
    1. Lead with the milestone/news hook
    2. One sentence: what Fantopy Arena is
    3. Why this is a story for their specific beat
    4. Simple ask: 20-min call or written Q&A offer

Tone: direct, journalist-to-journalist. Not marketing speak.
No exclamation marks. Factual. The story should sell itself.
Output JSON: {"subject": "...", "body": "..."}"""


def classify_beat(journalist: dict) -> str:
    return ask(BEAT_SYSTEM,
               f"Bio: {journalist['bio']}\nRecent tweet: {journalist['sample_tweet'][:200]}",
               max_tokens=30)


def draft_pitch(journalist: dict, beat: str, milestone: str) -> tuple[str, str]:
    prompt = f"""Journalist: {journalist['name']} (@{journalist['handle']})
Beat: {beat}
Milestone/news hook: {milestone}

Draft the press pitch."""
    raw = ask(PITCH_SYSTEM, prompt, max_tokens=300)
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(clean)
        return data.get("subject", ""), data.get("body", raw)
    except Exception:
        return f"Fantopy Arena: {milestone}", raw


# ── Main ──────────────────────────────────────────────────────────────────────

def run(manual_milestone: str | None = None) -> None:
    log.info("=== Agent 12: Press Pitcher — starting ===")
    ensure_tables()

    # Get milestone to pitch around
    if manual_milestone:
        mid = log_milestone(manual_milestone)
        milestone_data = {"id": mid, "milestone": manual_milestone, "detail": ""}
    else:
        milestone_data = get_unpitched_milestone()

    if not milestone_data:
        log.info("No unpitched milestones — running journalist discovery only")
        milestone_data = {"id": None, "milestone": "", "detail": ""}

    milestone = milestone_data["milestone"]
    journalists = discover_journalists()
    log.info(f"Found {len(journalists)} journalists. Milestone: '{milestone or 'none'}'")

    queued = 0
    for j in journalists[:6]:  # max 6 pitches per run
        if milestone and already_pitched(j["handle"], milestone):
            continue
        log.info(f"  Drafting pitch for @{j['handle']}")
        beat = classify_beat(j)
        subject, body = draft_pitch(j, beat, milestone or "Fantopy Arena launch")
        row = [
            datetime.datetime.utcnow().isoformat(),
            j["handle"], "", beat, milestone,
            subject, body, j["profile_url"], "PENDING", ""
        ]
        try:
            ws = get_sheet(SHEET_ID, "PressQueue")
            if ws.row_count == 0 or not ws.row_values(1):
                ws.insert_row(SHEET_HEADERS, 1)
            append_to_queue(SHEET_ID, row, worksheet_name="PressQueue")
            if milestone:
                log_pitch(j["handle"], milestone)
            queued += 1
        except Exception as e:
            log.error(f"  Sheets write failed: {e}")

    if milestone_data["id"] and queued > 0:
        mark_milestone_pitched(milestone_data["id"])

    if queued > 0 and DISCORD_WEBHOOK:
        try:
            httpx.post(DISCORD_WEBHOOK, json={
                "content": f"**Agent 12 — Press Pitcher** drafted {queued} press pitch(es) for milestone: *{milestone}*. Check Press Queue sheet."
            }, timeout=10)
        except Exception as e:
            log.error(f"Discord notify failed: {e}")

    log.info(f"=== Done. {queued} pitches queued ===")


if __name__ == "__main__":
    import argparse
    ensure_tables()
    parser = argparse.ArgumentParser()
    parser.add_argument("--milestone", type=str, help="Trigger with a specific milestone")
    args = parser.parse_args()
    run(args.milestone)
