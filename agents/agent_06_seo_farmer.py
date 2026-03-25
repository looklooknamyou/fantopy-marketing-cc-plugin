"""
================================================================================
AGENT 6: THE SEO FARMER
================================================================================
TRIGGER:      Every Tuesday 06:00 UTC cron
INPUTS:       Keyword research via web search, existing content_log
OUTPUTS:      SEO-optimised long-form page/post draft → Google Sheets queue
HUMAN REVIEW: YES — draft to Sheets, Discord ping, publish after approval
BUILD:        Month 2+
BLOCKED ON:   Google Sheets, Discord webhook
================================================================================

SEO STRATEGY:
  Target: people actively searching for FPL automation tools.
  Content types:
    - Comparison pages: "best FPL bot 2026", "FPL automation tools compared"
    - How-to: "how to automate fantasy premier league transfers"
    - Tool-specific: "LangChain FPL agent tutorial", "CrewAI fantasy football"
    - Question targets: "can AI play FPL?", "best FPL captain predictor"

  Each post: 1000-1500 words, one primary keyword, 3-5 secondary keywords,
  clear H1/H2 structure, internal links to fantopyarena.com/waitlist.

KEYWORD SEEDS (expanded by agent each run):
  Primary: "FPL bot", "fantasy premier league automation",
           "AI fantasy football", "FPL agent python"
  Secondary: "FPL transfer optimizer", "automated FPL transfers",
             "fantasy football AI agent", "LangChain FPL", "CrewAI FPL"
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
log = logging.getLogger("agent_06_seo")

SHEET_ID = os.environ.get("RECRUITER_SHEET_ID", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

KEYWORD_SEEDS = [
    "FPL bot 2026",
    "fantasy premier league automation python",
    "how to automate FPL transfers",
    "AI fantasy football agent",
    "LangChain FPL tutorial",
    "CrewAI fantasy football",
    "can AI play fantasy premier league",
    "best FPL captain predictor AI",
    "FPL transfer optimizer",
    "automated fantasy premier league",
]

SHEET_HEADERS = [
    "timestamp", "primary_keyword", "secondary_keywords",
    "title", "word_count", "draft_markdown", "status", "notes"
]

# ── DB: dedup published topics ────────────────────────────────────────────────

def ensure_seo_log() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS seo_log (
                id SERIAL PRIMARY KEY,
                keyword TEXT UNIQUE NOT NULL,
                queued_at TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'PENDING'
            )
        """))
        session.commit()


def is_keyword_done(keyword: str) -> bool:
    with Session() as session:
        return session.execute(
            text("SELECT 1 FROM seo_log WHERE keyword = :kw LIMIT 1"),
            {"kw": keyword.lower()}
        ).fetchone() is not None


def mark_keyword_done(keyword: str) -> None:
    with Session() as session:
        session.execute(text("""
            INSERT INTO seo_log (keyword) VALUES (:kw) ON CONFLICT DO NOTHING
        """), {"kw": keyword.lower()})
        session.commit()


# ── LLM: Expand keyword list ──────────────────────────────────────────────────

KEYWORD_EXPAND_SYSTEM = """You are an SEO strategist for Fantopy Arena — an AI agent
vs agent Fantasy Premier League competition platform.

Given a seed keyword, generate 5 related long-tail keyword variations that people
actually search for when looking for FPL automation tools or AI gaming platforms.

Focus on:
- Question keywords (how to, what is, can I)
- Tool-specific (LangChain, CrewAI, AutoGen + FPL)
- Comparison (best X for Y)
- Practical intent (automate, build, create)

Output a JSON array of 5 strings. Output ONLY valid JSON."""


def expand_keywords(seed: str) -> list[str]:
    raw = ask(KEYWORD_EXPAND_SYSTEM, f"Seed keyword: {seed}", max_tokens=200)
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except Exception:
        return []


# ── LLM: Write SEO post ───────────────────────────────────────────────────────

SEO_WRITER_SYSTEM = """You are writing an SEO-optimised blog post for Fantopy Arena —
an AI agent vs agent Fantasy Premier League competition platform.

Requirements:
- 1000-1500 words, markdown format
- H1 = the primary keyword phrase (natural)
- 3-4 H2 subheadings
- Primary keyword appears in: H1, first paragraph, 2-3 body sections, conclusion
- Secondary keywords appear naturally throughout
- Factual and genuinely useful — not thin content
- End with a CTA paragraph mentioning Fantopy Arena with link: [fantopyarena.com]
- No fluff intros. No "In today's digital world..." openers.
- Written for a technically literate audience (developers, FPL enthusiasts)

Output ONLY the markdown."""


def write_seo_post(primary_kw: str, secondary_kws: list[str]) -> str:
    prompt = f"""Primary keyword: {primary_kw}
Secondary keywords: {', '.join(secondary_kws[:5])}

Fantopy Arena context: AI agents compete autonomously in Fantasy Premier League.
Builders deploy Python/LangChain/CrewAI agents. Agents make real FPL decisions
(transfers, captain picks, chip plays) each gameweek. Entry fee in USDC, prize pool
at season end.

Write the SEO post."""
    return ask(SEO_WRITER_SYSTEM, prompt, max_tokens=2500)


# ── Queue to Sheets ───────────────────────────────────────────────────────────

def queue_to_sheets(primary_kw: str, secondary_kws: list[str], draft: str) -> None:
    word_count = len(draft.split())
    # Extract H1 as title
    title = next((l.lstrip("# ") for l in draft.splitlines() if l.startswith("# ")), primary_kw)
    row = [
        datetime.datetime.utcnow().isoformat(),
        primary_kw, ", ".join(secondary_kws),
        title, word_count, draft, "PENDING", ""
    ]
    try:
        ws = get_sheet(SHEET_ID, "SEOQueue")
        if ws.row_count == 0 or not ws.row_values(1):
            ws.insert_row(SHEET_HEADERS, 1)
        append_to_queue(SHEET_ID, row, worksheet_name="SEOQueue")
        log.info(f"  Queued: '{title}' ({word_count} words)")
    except Exception as e:
        log.error(f"  Sheets write failed: {e}")


def notify_discord(title: str) -> None:
    if not DISCORD_WEBHOOK:
        return
    try:
        httpx.post(DISCORD_WEBHOOK, json={
            "content": f"**Agent 6 — SEO Farmer** drafted a new post:\n> {title}\nCheck SEO Queue sheet."
        }, timeout=10)
    except Exception as e:
        log.error(f"Discord notify failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    log.info("=== Agent 6: SEO Farmer — starting ===")
    ensure_seo_log()

    # Pick next unprocessed seed keyword
    pending = [kw for kw in KEYWORD_SEEDS if not is_keyword_done(kw)]
    if not pending:
        log.info("All seed keywords processed. Expanding from first seed.")
        expanded = expand_keywords(KEYWORD_SEEDS[0])
        pending = [kw for kw in expanded if not is_keyword_done(kw)]

    if not pending:
        log.info("No new keywords to write. Done.")
        return

    primary_kw = pending[0]
    log.info(f"Writing post for: '{primary_kw}'")

    secondary_kws = expand_keywords(primary_kw)
    log.info(f"  Secondary keywords: {secondary_kws}")

    draft = write_seo_post(primary_kw, secondary_kws)
    log.info(f"  Draft complete ({len(draft.split())} words)")

    queue_to_sheets(primary_kw, secondary_kws, draft)
    mark_keyword_done(primary_kw)

    title = next((l.lstrip("# ") for l in draft.splitlines() if l.startswith("# ")), primary_kw)
    notify_discord(title)

    log.info("=== Done ===")


if __name__ == "__main__":
    run()
