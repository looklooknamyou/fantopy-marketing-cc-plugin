"""
================================================================================
AGENT 7: THE REDDIT PERSONA
================================================================================
TRIGGER:      Every 48 hours cron (3-4 posts/week MAX — Reddit rate limit safety)
INPUTS:       Reddit PRAW (read + draft), Google Sheets (human review queue)
OUTPUTS:      Genuine helpful comments/posts drafted for human review
HUMAN REVIEW: YES — always. Never posts autonomously. Human reviews every draft.
BUILD:        Month 2+ (only after account has 2-3 weeks of manual karma)
BLOCKED ON:   Reddit client ID/secret, Google Sheets
================================================================================

STRATEGY (from workflow doc):
  Week 1-2: Human posts manually, builds karma to 50-100. NO AUTOMATION YET.
  Week 3+:  Agent drafts posts/comments. Human reviews before posting.
  Month 2+: Light automation with heavy human review.

  Rule: Never more than 1-2 Fantopy mentions per week.
  Mix: ~80% genuinely helpful FPL content, ~20% Fantopy angle.

SUBREDDITS:
  r/FantasyPL     — core FPL community (most active)
  r/learnmachinelearning — builder audience
  r/AIAgents      — agent builders
  r/Python        — when FPL-related threads arise

POST TYPES:
  - Answer a technical FPL question (no Fantopy mention)
  - Share a useful FPL insight from data (maybe Fantopy mention at end)
  - Ask a genuine question as a builder/FPL player
  - Weekly GW thread contribution (genuine captain/transfer take)

FANTOPY MENTION RULES:
  - Only mention if directly relevant to what's being discussed
  - Never in first comment of a thread
  - Never two Fantopy mentions in the same week
  - Frame as: "I've been building something similar actually..." not "Check out our platform"
================================================================================
"""

import os
import sys
import logging
import datetime
import random
import httpx
from dotenv import load_dotenv
import praw
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session
from shared.sheets import append_to_queue, get_sheet
from shared.llm import ask

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_07_reddit")

REDDIT_CLIENT_ID     = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT    = os.environ.get("REDDIT_USER_AGENT", "FantopyScout/1.0")
SHEET_ID             = os.environ.get("RECRUITER_SHEET_ID", "")
DISCORD_WEBHOOK      = os.environ.get("DISCORD_WEBHOOK_URL", "")

SHEET_HEADERS = [
    "timestamp", "type", "subreddit", "post_url", "post_title",
    "draft_content", "includes_fantopy_mention", "status", "notes"
]

TARGET_SUBS = ["FantasyPL", "learnmachinelearning", "AIAgents", "Python"]
FPL_KEYWORDS = ["fpl", "fantasy premier league", "fantasy football",
                "transfer", "captain", "wildcard", "gameweek", "fpl bot"]

# ── DB helpers ────────────────────────────────────────────────────────────────

def ensure_reddit_log() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS reddit_drafts (
                id SERIAL PRIMARY KEY,
                post_id TEXT UNIQUE NOT NULL,
                subreddit TEXT,
                draft_type TEXT,
                fantopy_mention BOOLEAN DEFAULT FALSE,
                queued_at TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'PENDING'
            )
        """))
        session.commit()


def already_drafted(post_id: str) -> bool:
    with Session() as session:
        return session.execute(
            text("SELECT 1 FROM reddit_drafts WHERE post_id = :pid LIMIT 1"),
            {"pid": post_id}
        ).fetchone() is not None


def count_fantopy_mentions_this_week() -> int:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    with Session() as session:
        result = session.execute(text("""
            SELECT COUNT(*) FROM reddit_drafts
            WHERE fantopy_mention = TRUE AND queued_at > :cutoff
              AND status = 'APPROVED'
        """), {"cutoff": cutoff}).fetchone()
        return result[0] if result else 0


def log_draft(post_id: str, subreddit: str, draft_type: str, fantopy_mention: bool) -> None:
    with Session() as session:
        try:
            session.execute(text("""
                INSERT INTO reddit_drafts (post_id, subreddit, draft_type, fantopy_mention)
                VALUES (:pid, :sub, :dt, :fm)
                ON CONFLICT (post_id) DO NOTHING
            """), {"pid": post_id, "sub": subreddit, "dt": draft_type, "fm": fantopy_mention})
            session.commit()
        except Exception as e:
            log.warning(f"DB log failed: {e}")


# ── LLM: Draft reply ──────────────────────────────────────────────────────────

REPLY_SYSTEM_NO_MENTION = """You are a knowledgeable FPL player and Python developer
participating genuinely in a Reddit discussion. Write a helpful, specific reply that
adds real value to the conversation.

Rules:
- Sound like a real person, not a company
- Be specific and concrete, not generic
- Draw on real FPL knowledge (xG, fixture difficulty, captain strategies, chip timing)
- For technical questions: give actual code hints or tool suggestions
- Do NOT mention Fantopy Arena
- Keep it 100-200 words
- No exclamation marks. Conversational tone.

Output ONLY the reply text."""

REPLY_SYSTEM_WITH_MENTION = """You are a knowledgeable FPL player and Python developer
participating genuinely in a Reddit discussion. Write a helpful reply that naturally
mentions Fantopy Arena once — only if it genuinely fits.

Rules:
- Lead with genuine value (answer the question first)
- Mention Fantopy as something you've personally been involved with:
  "I've been building something similar on Fantopy Arena actually..."
  or "There's a platform called Fantopy Arena that does this competitively..."
- Sound personal, not promotional. One mention maximum.
- Keep it 100-200 words. No exclamation marks.

Output ONLY the reply text."""

ORIGINAL_POST_SYSTEM = """You are writing an original Reddit post as a genuine
FPL player and Python developer. The post should be interesting and invite discussion.

Types:
  - Share an insight: "I analysed 3 seasons of FPL data and found..."
  - Ask for advice: "Struggling to decide between X and Y for captain..."
  - Share a project update: "Built an FPL transfer optimizer, here's what I learned..."

Rules:
- Authentic, first-person
- Specific and data-driven where possible
- If mentioning Fantopy: only in the comments, never the post itself
- 150-300 words. No self-promotion in the post body.

Output ONLY the post text (title on first line, body below)."""


def draft_reply(post_title: str, post_body: str, subreddit: str,
                include_fantopy: bool) -> str:
    system = REPLY_SYSTEM_WITH_MENTION if include_fantopy else REPLY_SYSTEM_NO_MENTION
    prompt = f"""Subreddit: r/{subreddit}
Post title: {post_title}
Post body: {post_body[:600]}

Write the reply."""
    return ask(system, prompt, max_tokens=300)


def draft_original_post(subreddit: str) -> tuple[str, str]:
    """Returns (title, body)."""
    raw = ask(ORIGINAL_POST_SYSTEM,
              f"Subreddit: r/{subreddit}\nWrite an interesting FPL/AI developer post.",
              max_tokens=400)
    lines = raw.strip().splitlines()
    title = lines[0].lstrip("#").strip() if lines else "FPL discussion"
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else raw
    return title, body


# ── Discovery: find good threads ─────────────────────────────────────────────

def find_relevant_threads() -> list[dict]:
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )
    threads = []
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=48)

    for sub_name in TARGET_SUBS:
        try:
            sub = reddit.subreddit(sub_name)
            for post in sub.hot(limit=30):
                created = datetime.datetime.utcfromtimestamp(post.created_utc)
                if created < cutoff:
                    continue
                combined = (post.title + " " + (post.selftext or "")).lower()
                if not any(kw in combined for kw in FPL_KEYWORDS):
                    continue
                if already_drafted(post.id):
                    continue
                # Skip low-engagement (less likely to be seen)
                if post.score < 5 and post.num_comments < 3:
                    continue
                threads.append({
                    "id": post.id,
                    "subreddit": sub_name,
                    "title": post.title,
                    "body": post.selftext[:600] if post.selftext else "",
                    "url": f"https://reddit.com{post.permalink}",
                    "score": post.score,
                    "comments": post.num_comments,
                })
        except Exception as e:
            log.error(f"Reddit error on r/{sub_name}: {e}")

    return threads


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    log.info("=== Agent 7: Reddit Persona — starting ===")
    ensure_reddit_log()

    fantopy_mentions_this_week = count_fantopy_mentions_this_week()
    can_mention_fantopy = fantopy_mentions_this_week < 2

    threads = find_relevant_threads()
    log.info(f"Found {len(threads)} relevant threads. Fantopy mentions this week: {fantopy_mentions_this_week}/2")

    # Pick up to 2 threads to draft replies for (don't flood)
    selected = sorted(threads, key=lambda t: t["score"] + t["comments"] * 2, reverse=True)[:2]

    queued = 0
    for thread in selected:
        # Only use Fantopy mention on highest-engagement thread, once
        use_mention = can_mention_fantopy and queued == 0 and thread["score"] > 20
        draft = draft_reply(thread["title"], thread["body"], thread["subreddit"], use_mention)

        row = [
            datetime.datetime.utcnow().isoformat(),
            "reply", thread["subreddit"], thread["url"], thread["title"],
            draft, "YES" if use_mention else "NO", "PENDING", ""
        ]
        try:
            ws = get_sheet(SHEET_ID, "RedditQueue")
            if ws.row_count == 0 or not ws.row_values(1):
                ws.insert_row(SHEET_HEADERS, 1)
            append_to_queue(SHEET_ID, row, worksheet_name="RedditQueue")
            log_draft(thread["id"], thread["subreddit"], "reply", use_mention)
            log.info(f"  Queued reply for: {thread['title'][:60]}... (Fantopy: {use_mention})")
            queued += 1
        except Exception as e:
            log.error(f"  Sheets write failed: {e}")

    # Once per week: draft an original post
    today = datetime.datetime.utcnow()
    if today.weekday() == 0 and queued < 2:  # Monday
        sub = random.choice(["FantasyPL", "learnmachinelearning"])
        title, body = draft_original_post(sub)
        row = [
            today.isoformat(), "original_post", sub, "", title,
            f"**{title}**\n\n{body}", "NO", "PENDING", "Original post draft"
        ]
        try:
            append_to_queue(SHEET_ID, row, worksheet_name="RedditQueue")
            log.info(f"  Queued original post for r/{sub}: {title}")
        except Exception as e:
            log.error(f"  Original post queue failed: {e}")

    if queued > 0 and DISCORD_WEBHOOK:
        try:
            httpx.post(DISCORD_WEBHOOK, json={
                "content": f"**Agent 7 — Reddit Persona** drafted {queued} Reddit reply/post(s) for review. Check Reddit Queue sheet."
            }, timeout=10)
        except Exception as e:
            log.error(f"Discord notify failed: {e}")

    log.info(f"=== Done. {queued} drafts queued ===")


if __name__ == "__main__":
    run()
