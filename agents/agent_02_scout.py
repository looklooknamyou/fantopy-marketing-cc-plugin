"""
================================================================================
AGENT 2: THE SCOUT
================================================================================
TRIGGER:      Every 6 hours cron (GitHub Actions)
INPUTS:       Twitter/X API, Reddit API (PRAW)
OUTPUTS:      Reply/comment drafts → Google Sheets queue for human review
HUMAN REVIEW: YES — drafts queued in Sheets, Discord ping, human approves
MONITORS:
  Twitter keywords: "FPL bot", "fantasy football AI", "fantasy premier league bot",
                    "FPL automation", "built FPL", "AI fantasy"
  Reddit subreddits: r/FantasyPL, r/learnmachinelearning, r/MachineLearning,
                     r/AIAgents, r/Python (FPL-related threads)
DEDUP:        Postgres `scout_replied` table — never drafts reply for same
              tweet/post twice
BLOCKED ON:   Twitter bearer token, Reddit client ID/secret, Google Sheets
================================================================================

HOW IT WORKS
1. DISCOVERY  Monitor Twitter + Reddit for posts about FPL bots/AI agents
2. RESEARCH   Claude reads the post, decides if Fantopy Arena is relevant
              to mention (only drafts if genuinely relevant — not spam)
3. DRAFT      Claude writes a natural reply that adds value, then mentions
              Fantopy Arena only if it fits organically
4. REVIEW     Appends to Google Sheets with original post URL, context,
              draft reply, relevance score
5. NOTIFY     Discord ping with count of new drafts
================================================================================
"""

import os
import sys
import logging
import datetime
import httpx
from dotenv import load_dotenv
import json
import tweepy
import praw
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session
from shared.sheets import append_to_queue, get_sheet
from shared.llm import ask

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_02_scout")

TWITTER_BEARER_TOKEN = os.environ["TWITTER_BEARER_TOKEN"]
REDDIT_CLIENT_ID = os.environ["REDDIT_CLIENT_ID"]
REDDIT_CLIENT_SECRET = os.environ["REDDIT_CLIENT_SECRET"]
REDDIT_USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "FantopyScout/1.0")
SHEET_ID = os.environ["RECRUITER_SHEET_ID"]  # reuse sheet, different tab
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DB_TABLE = "scout_replied"

SHEET_HEADERS = [
    "timestamp", "source", "platform_id", "url", "author",
    "original_text", "relevance_score", "reply_draft", "status", "notes"
]

TWITTER_KEYWORDS = [
    "FPL bot -is:retweet lang:en",
    "fantasy football AI agent -is:retweet lang:en",
    "built FPL automation -is:retweet lang:en",
    "fantasy premier league automation -is:retweet lang:en",
]

REDDIT_SUBS = ["FantasyPL", "learnmachinelearning", "AIAgents", "Python"]
REDDIT_FPL_KEYWORDS = ["fpl", "fantasy premier league", "fantasy football bot", "fpl bot", "fpl agent"]

# ── DB helpers ────────────────────────────────────────────────────────────────

def ensure_scout_table() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS scout_replied (
                id SERIAL PRIMARY KEY,
                platform_id TEXT UNIQUE NOT NULL,
                source TEXT,
                url TEXT,
                queued_at TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'PENDING'
            )
        """))
        session.commit()


def is_already_queued(platform_id: str) -> bool:
    with Session() as session:
        result = session.execute(
            text("SELECT 1 FROM scout_replied WHERE platform_id = :pid LIMIT 1"),
            {"pid": platform_id}
        ).fetchone()
        return result is not None


def mark_queued(platform_id: str, source: str, url: str) -> None:
    with Session() as session:
        try:
            session.execute(text("""
                INSERT INTO scout_replied (platform_id, source, url)
                VALUES (:pid, :source, :url)
                ON CONFLICT (platform_id) DO NOTHING
            """), {"pid": platform_id, "source": source, "url": url})
            session.commit()
        except Exception as e:
            log.warning(f"DB mark failed: {e}")


# ── LLM: Relevance check + draft ─────────────────────────────────────────────

RELEVANCE_SYSTEM = """You are evaluating whether a social media post is a good
opportunity to mention Fantopy Arena — an AI agent vs agent Fantasy Premier League
competition platform where builders deploy autonomous agents to compete.

Return JSON: {"score": 1-10, "reason": "brief explanation"}

Score guide:
  8-10: Post is directly about FPL bots, AI agents in fantasy sports, or
        someone actively looking to test/showcase their FPL bot
  5-7:  Post is about FPL strategy, AI agent frameworks, or Python bots
        — Fantopy could be mentioned naturally
  1-4:  Not relevant or would feel spammy

Output ONLY valid JSON."""

REPLY_SYSTEM = """You are writing a community reply on behalf of Fantopy Arena —
an AI agent vs agent Fantasy Premier League competition platform.

Rules:
1. Lead with genuine value or insight about what they posted — don't open by talking about Fantopy
2. Mention Fantopy Arena only if it fits naturally as something they'd find interesting
3. Never be promotional or salesy — peer-to-peer tone
4. Keep it under 80 words
5. No hashtags, no exclamation marks
6. End with something that invites continued conversation, not a hard CTA

Output ONLY the reply text."""


def evaluate_relevance(text_content: str, source: str) -> dict:
    raw = ask(RELEVANCE_SYSTEM, f"Platform: {source}\n\nPost:\n{text_content[:600]}", max_tokens=150)
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except Exception:
        return {"score": 0, "reason": "parse error"}


def draft_reply(original_text: str, source: str) -> str:
    return ask(REPLY_SYSTEM, f"Platform: {source}\n\nOriginal post:\n{original_text[:600]}", max_tokens=150)


# ── Discovery: Twitter ────────────────────────────────────────────────────────

def search_twitter() -> list[dict]:
    client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN, wait_on_rate_limit=True)
    hits = []
    since = (datetime.datetime.utcnow() - datetime.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for query in TWITTER_KEYWORDS:
        log.info(f"Twitter: {query}")
        try:
            response = client.search_recent_tweets(
                query=query,
                max_results=10,
                tweet_fields=["author_id", "text", "created_at"],
                expansions=["author_id"],
                user_fields=["username"],
                start_time=since,
            )
            if not response.data:
                continue
            users_by_id = {u.id: u for u in ((response.includes or {}).get("users") or [])}

            for tweet in response.data:
                pid = str(tweet.id)
                if is_already_queued(pid):
                    continue
                user = users_by_id.get(tweet.author_id)
                hits.append({
                    "source": "twitter",
                    "platform_id": pid,
                    "url": f"https://twitter.com/i/web/status/{pid}",
                    "author": f"@{user.username}" if user else "unknown",
                    "text": tweet.text,
                })
        except tweepy.TweepyException as e:
            log.error(f"Twitter error: {e}")

    return hits


# ── Discovery: Reddit ─────────────────────────────────────────────────────────

def search_reddit() -> list[dict]:
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )
    hits = []
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=6)

    for sub_name in REDDIT_SUBS:
        log.info(f"Reddit: r/{sub_name}")
        try:
            sub = reddit.subreddit(sub_name)
            for post in sub.new(limit=25):
                created = datetime.datetime.utcfromtimestamp(post.created_utc)
                if created < cutoff:
                    continue

                combined = (post.title + " " + (post.selftext or "")).lower()
                if not any(kw in combined for kw in REDDIT_FPL_KEYWORDS):
                    continue

                pid = f"reddit_{post.id}"
                if is_already_queued(pid):
                    continue

                hits.append({
                    "source": f"reddit/r/{sub_name}",
                    "platform_id": pid,
                    "url": f"https://reddit.com{post.permalink}",
                    "author": str(post.author),
                    "text": f"{post.title}\n\n{post.selftext[:400]}",
                })
        except Exception as e:
            log.error(f"Reddit error on r/{sub_name}: {e}")

    return hits


# ── Process hit ───────────────────────────────────────────────────────────────

def process_hit(hit: dict) -> bool:
    """Returns True if queued."""
    relevance = evaluate_relevance(hit["text"], hit["source"])
    score = relevance.get("score", 0)

    log.info(f"  Relevance {score}/10 — {relevance.get('reason','')[:60]}")

    if score < 6:
        # Mark as seen so we don't re-evaluate
        mark_queued(hit["platform_id"], hit["source"], hit["url"])
        return False

    draft = draft_reply(hit["text"], hit["source"])

    row = [
        datetime.datetime.utcnow().isoformat(),
        hit["source"],
        hit["platform_id"],
        hit["url"],
        hit["author"],
        hit["text"][:300],
        score,
        draft,
        "PENDING",
        relevance.get("reason", ""),
    ]

    try:
        ws = get_sheet(SHEET_ID, "ScoutQueue")
        if ws.row_count == 0 or not ws.row_values(1):
            ws.insert_row(SHEET_HEADERS, 1)
        append_to_queue(SHEET_ID, row, worksheet_name="ScoutQueue")
        mark_queued(hit["platform_id"], hit["source"], hit["url"])
        return True
    except Exception as e:
        log.error(f"  Sheets write failed: {e}")
        return False


# ── Notify ────────────────────────────────────────────────────────────────────

def notify_discord(count: int) -> None:
    if not DISCORD_WEBHOOK_URL or count == 0:
        return
    try:
        httpx.post(DISCORD_WEBHOOK_URL, json={
            "content": f"**Agent 2 — Scout** found {count} reply opportunit{'y' if count == 1 else 'ies'} to review."
        }, timeout=10)
    except Exception as e:
        log.error(f"Discord notify failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    log.info("=== Agent 2: The Scout — starting ===")
    ensure_scout_table()

    all_hits = search_twitter() + search_reddit()
    log.info(f"Found {len(all_hits)} new posts to evaluate")

    queued = 0
    for hit in all_hits:
        log.info(f"Evaluating: {hit['url']}")
        try:
            if process_hit(hit):
                queued += 1
        except Exception as e:
            log.error(f"  Failed on {hit['platform_id']}: {e}")

    notify_discord(queued)
    log.info(f"=== Done. {queued}/{len(all_hits)} queued for review ===")


if __name__ == "__main__":
    run()
