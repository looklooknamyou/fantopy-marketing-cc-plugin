"""
================================================================================
AGENT 4: CONTENT WRITER
================================================================================
TRIGGER:      Every Wednesday 07:00 UTC cron (GitHub Actions)
INPUTS:       Topic from Postgres queue OR auto-generated from FPL calendar
OUTPUTS:      Draft blog post → Google Sheets queue for human review
HUMAN REVIEW: YES — draft queued in Sheets, Discord ping, human approves/edits
              before publishing to blog CMS
FORMAT:       800-1200 word blog post, markdown
TONE:         Builder-focused or spectator-focused depending on topic type
TOPICS POOL:  Seeded from Postgres `content_topics` table. Falls back to
              auto-generating a topic based on FPL season calendar.
DEDUP:        Postgres `content_log` — never writes the same topic twice
BLOCKED ON:   Google Sheets, Discord webhook, Anthropic API key
================================================================================

TOPIC TYPES (stored in content_topics.type):
  builder_technical   — e.g. "How to use xG data in your FPL agent"
  builder_strategy    — e.g. "When should your agent play the wildcard?"
  spectator_narrative — e.g. "Why watching AI agents fail is the best part"
  platform_explainer  — e.g. "How Fantopy Arena works: a quick guide"
  fpl_primer          — e.g. "FPL for non-football people: the basics"

AUTO-TOPIC FALLBACK (if queue is empty):
  Looks at current week in EPL season and generates a seasonally relevant topic.
================================================================================
"""

import os
import sys
import logging
import datetime
import json
import httpx
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session
from shared.sheets import append_to_queue, get_sheet
from shared.llm import ask

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_04_content")

SHEET_ID = os.environ["RECRUITER_SHEET_ID"]  # reuse sheet, different tab
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

SHEET_HEADERS = [
    "timestamp", "topic_id", "topic_title", "topic_type",
    "word_count", "post_draft_markdown", "status", "notes"
]

# ── DB helpers ────────────────────────────────────────────────────────────────

def ensure_content_tables() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS content_topics (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                notes TEXT,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS content_log (
                id SERIAL PRIMARY KEY,
                topic_id INT,
                topic_title TEXT,
                written_at TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'PENDING'
            )
        """))
        session.commit()


def pop_next_topic() -> dict | None:
    """Get and mark-used the oldest unused topic."""
    with Session() as session:
        row = session.execute(text("""
            SELECT id, title, type, notes
            FROM content_topics
            WHERE used = FALSE
            ORDER BY created_at ASC
            LIMIT 1
        """)).mappings().fetchone()

        if not row:
            return None

        session.execute(text(
            "UPDATE content_topics SET used = TRUE WHERE id = :id"
        ), {"id": row["id"]})
        session.commit()
        return dict(row)


def log_content(topic_id: int | None, title: str) -> None:
    with Session() as session:
        session.execute(text("""
            INSERT INTO content_log (topic_id, topic_title)
            VALUES (:tid, :title)
        """), {"tid": topic_id, "title": title})
        session.commit()


# ── Auto-topic generation ─────────────────────────────────────────────────────

def get_epl_week_context() -> str:
    """Rough EPL season week estimator for auto-topic fallback."""
    now = datetime.datetime.utcnow()
    month = now.month
    if month in (8, 9):
        return "early season (GW1-6): transfer strategies and early movers"
    elif month in (10, 11):
        return "mid-season (GW7-16): fixture swings and international breaks"
    elif month == 12:
        return "festive period (GW17-21): blank/double gameweeks, squad depth"
    elif month in (1, 2):
        return "transfer window and second half push (GW22-27)"
    elif month in (3, 4):
        return "run-in (GW28-35): double gameweeks, chip timing"
    else:
        return "season finale (GW36-38): final push"


AUTO_TOPIC_SYSTEM = """You are a content strategist for Fantopy Arena — an AI agent
vs agent Fantasy Premier League competition platform. Generate ONE blog post topic
that would be genuinely useful for either:
  a) A developer thinking about building an FPL agent
  b) A spectator curious about AI competing in fantasy sports

Season context will be provided. Output JSON:
{"title": "...", "type": "builder_technical|builder_strategy|spectator_narrative|platform_explainer|fpl_primer", "angle": "1-sentence brief"}
Output ONLY valid JSON."""


def generate_auto_topic() -> dict:
    context = get_epl_week_context()
    raw = ask(AUTO_TOPIC_SYSTEM, f"Current season context: {context}", max_tokens=200)
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(clean)
        return {
            "id": None,
            "title": data["title"],
            "type": data["type"],
            "notes": data.get("angle", ""),
        }
    except Exception as e:
        log.error(f"Auto-topic generation failed: {e}")
        return {
            "id": None,
            "title": "How AI agents make decisions in Fantasy Premier League",
            "type": "platform_explainer",
            "notes": "Fallback topic",
        }


# ── LLM: Write the post ───────────────────────────────────────────────────────

def get_writer_system(topic_type: str) -> str:
    tone_map = {
        "builder_technical": "technical, peer-to-peer, assumes Python knowledge",
        "builder_strategy":  "analytical, FPL-savvy, treats agents as serious competitors",
        "spectator_narrative": "narrative-driven, accessible, no coding assumed, emphasises drama",
        "platform_explainer": "clear, welcoming, equally accessible to builders and spectators",
        "fpl_primer":        "friendly explainer, assume zero football knowledge, analogies welcome",
    }
    tone = tone_map.get(topic_type, "clear and engaging")

    return f"""You are writing a blog post for Fantopy Arena — an AI agent vs agent
Fantasy Premier League competition platform built by Benchwarmers Pte Ltd.

Tone: {tone}

Format requirements:
- 800-1000 words
- Markdown format (# for H1, ## for H2)
- No fluff intro ("In the world of..." etc) — open with a hook or direct claim
- Include 3-4 subheadings
- End with a subtle mention of Fantopy Arena and a link placeholder: [fantopyarena.com]
- Do not use exclamation marks
- Write as if published on the Fantopy blog

Output ONLY the markdown post."""


def write_post(topic: dict) -> str:
    system = get_writer_system(topic["type"])
    user_prompt = f"""Topic: {topic['title']}
Type: {topic['type']}
Notes/angle: {topic.get('notes', '')}

Write the full blog post."""
    return ask(system, user_prompt, max_tokens=2000)


# ── Queue to Sheets ───────────────────────────────────────────────────────────

def queue_to_sheets(topic: dict, post_markdown: str) -> None:
    word_count = len(post_markdown.split())
    row = [
        datetime.datetime.utcnow().isoformat(),
        topic.get("id") or "auto",
        topic["title"],
        topic["type"],
        word_count,
        post_markdown,
        "PENDING",
        topic.get("notes", ""),
    ]
    try:
        ws = get_sheet(SHEET_ID, "ContentQueue")
        if ws.row_count == 0 or not ws.row_values(1):
            ws.insert_row(SHEET_HEADERS, 1)
        append_to_queue(SHEET_ID, row, worksheet_name="ContentQueue")
        log.info(f"Queued to Sheets: '{topic['title']}' ({word_count} words)")
    except Exception as e:
        log.error(f"Sheets write failed: {e}")


# ── Notify ────────────────────────────────────────────────────────────────────

def notify_discord(title: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        httpx.post(DISCORD_WEBHOOK_URL, json={
            "content": f"**Agent 4 — Content Writer** drafted a new post for review:\n> {title}\nCheck the Content Queue sheet."
        }, timeout=10)
    except Exception as e:
        log.error(f"Discord notify failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    log.info("=== Agent 4: Content Writer — starting ===")
    ensure_content_tables()

    topic = pop_next_topic()
    if topic:
        log.info(f"Using queued topic: '{topic['title']}' ({topic['type']})")
    else:
        log.info("No topics in queue — generating auto-topic")
        topic = generate_auto_topic()
        log.info(f"Auto-topic: '{topic['title']}'")

    log.info("Writing post...")
    post = write_post(topic)
    log.info(f"Post written ({len(post.split())} words)")

    queue_to_sheets(topic, post)
    log_content(topic.get("id"), topic["title"])
    notify_discord(topic["title"])

    log.info("=== Done ===")


if __name__ == "__main__":
    run()
