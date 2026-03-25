"""
================================================================================
AGENT 9: COMPETITOR MONITOR
================================================================================
TRIGGER:      Every Friday 08:00 UTC cron (GitHub Actions)
INPUTS:       Twitter/X API, GitHub API, Product Hunt API (RSS)
OUTPUTS:      Weekly intel report → Discord channel + Slack webhook
HUMAN REVIEW: NO — fully autonomous
KEYWORDS WATCHED:
  - "agent vs agent gaming"
  - "AI fantasy football"
  - "agent competition platform"
  - "fantasy football bot"
  - "FPL automation platform"
  - "fantasy sports AI"
BLOCKED ON:   Twitter bearer token, Discord webhook, GitHub token
================================================================================

HOW IT WORKS
1. DISCOVERY  Search Twitter, GitHub, Product Hunt for keywords
              across the past 7 days
2. RESEARCH   Claude classifies each hit: direct competitor / adjacent /
              noise. Extracts key signals (funding, traction, feature launch)
3. DRAFT      Claude writes a concise weekly intel brief
4. SEND       Posts to Discord intel channel + Slack (if configured)
5. TRACK      Logs seen URLs to Postgres to avoid re-reporting same items
================================================================================
"""

import os
import sys
import logging
import datetime
import httpx
import json
import feedparser
from dotenv import load_dotenv
import tweepy
from github import Github, GithubException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session, engine
from shared.llm import ask
from sqlalchemy import text

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_09_monitor")

TWITTER_BEARER_TOKEN = os.environ["TWITTER_BEARER_TOKEN"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
DISCORD_INTEL_CHANNEL_ID = os.environ.get("DISCORD_INTEL_CHANNEL_ID", "")

KEYWORDS = [
    "agent vs agent gaming",
    "AI fantasy football",
    "agent competition platform",
    "fantasy football bot platform",
    "FPL automation platform",
    "fantasy sports AI agent",
]

PRODUCT_HUNT_RSS = "https://www.producthunt.com/feed"

# ── Ensure dedup table ────────────────────────────────────────────────────────

def ensure_intel_log_table() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS intel_log (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                source TEXT,
                seen_at TIMESTAMPTZ DEFAULT NOW(),
                classification TEXT
            )
        """))
        session.commit()


def is_already_seen(url: str) -> bool:
    with Session() as session:
        result = session.execute(
            text("SELECT 1 FROM intel_log WHERE url = :url LIMIT 1"),
            {"url": url}
        ).fetchone()
        return result is not None


def mark_seen(url: str, source: str, classification: str = "unknown") -> None:
    with Session() as session:
        try:
            session.execute(text("""
                INSERT INTO intel_log (url, source, classification)
                VALUES (:url, :source, :classification)
                ON CONFLICT (url) DO NOTHING
            """), {"url": url, "source": source, "classification": classification})
            session.commit()
        except Exception as e:
            log.warning(f"DB mark_seen failed: {e}")


# ── Step 1: Discovery ─────────────────────────────────────────────────────────

def search_twitter() -> list[dict]:
    client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN, wait_on_rate_limit=True)
    hits = []
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for keyword in KEYWORDS:
        query = f'"{keyword}" -is:retweet lang:en'
        log.info(f"Twitter: {query}")
        try:
            response = client.search_recent_tweets(
                query=query,
                max_results=10,
                tweet_fields=["author_id", "text", "created_at", "public_metrics"],
                expansions=["author_id"],
                user_fields=["username", "name"],
                start_time=since,
            )
            if not response.data:
                continue

            users_by_id = {u.id: u for u in ((response.includes or {}).get("users") or [])}

            for tweet in response.data:
                url = f"https://twitter.com/i/web/status/{tweet.id}"
                if is_already_seen(url):
                    continue
                user = users_by_id.get(tweet.author_id)
                hits.append({
                    "source": "twitter",
                    "url": url,
                    "title": f"@{user.username if user else 'unknown'}: {tweet.text[:100]}",
                    "text": tweet.text,
                    "keyword": keyword,
                    "likes": tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0,
                    "date": str(tweet.created_at)[:10] if tweet.created_at else "",
                })
        except tweepy.TweepyException as e:
            log.error(f"Twitter error: {e}")

    return hits


def search_github() -> list[dict]:
    gh = Github(GITHUB_TOKEN)
    hits = []
    queries = [
        "ai fantasy football agent stars:>2",
        "agent competition game python stars:>5",
        "fantasy premier league bot platform stars:>3",
    ]
    since = datetime.datetime.utcnow() - datetime.timedelta(days=7)

    for query in queries:
        log.info(f"GitHub: {query}")
        try:
            results = gh.search_repositories(query=query, sort="updated", order="desc")
            for repo in results[:5]:
                if repo.updated_at and repo.updated_at.replace(tzinfo=None) < since:
                    continue
                if is_already_seen(repo.html_url):
                    continue
                hits.append({
                    "source": "github",
                    "url": repo.html_url,
                    "title": f"{repo.full_name} ★{repo.stargazers_count}",
                    "text": repo.description or "",
                    "keyword": query,
                    "likes": repo.stargazers_count,
                    "date": str(repo.updated_at.date()) if repo.updated_at else "",
                })
        except GithubException as e:
            log.error(f"GitHub error: {e}")

    return hits


def search_product_hunt() -> list[dict]:
    hits = []
    log.info("Product Hunt: scanning RSS feed")
    try:
        feed = feedparser.parse(PRODUCT_HUNT_RSS)
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)

        for entry in feed.entries[:50]:
            title = entry.get("title", "").lower()
            summary = entry.get("summary", "").lower()
            combined = title + " " + summary

            if not any(kw.lower() in combined for kw in [
                "fantasy", "football", "fpl", "agent", "ai game", "sports ai"
            ]):
                continue

            url = entry.get("link", "")
            if not url or is_already_seen(url):
                continue

            hits.append({
                "source": "product_hunt",
                "url": url,
                "title": entry.get("title", ""),
                "text": entry.get("summary", "")[:300],
                "keyword": "product_hunt_scan",
                "likes": 0,
                "date": entry.get("published", "")[:10],
            })
    except Exception as e:
        log.error(f"Product Hunt RSS error: {e}")

    return hits


# ── Step 2: Classify with LLM ─────────────────────────────────────────────────

CLASSIFY_SYSTEM = """You are a competitive intelligence analyst for Fantopy Arena —
an AI agent vs agent Fantasy Premier League competition platform.

Classify each item as ONE of:
  DIRECT_COMPETITOR  — another platform where AI agents compete in fantasy sports
  ADJACENT           — AI gaming, fantasy sports tool, agent framework, or FPL tool
                       that could threaten or partner with Fantopy
  NOISE              — not relevant

Return a JSON array. Each item: {"url": "...", "classification": "...", "signal": "1-sentence reason"}
Output ONLY valid JSON."""


def classify_hits(hits: list[dict]) -> list[dict]:
    if not hits:
        return []

    items_text = "\n".join(
        f'{i+1}. URL: {h["url"]}\n   Title: {h["title"]}\n   Text: {h["text"][:200]}'
        for i, h in enumerate(hits)
    )

    raw = ask(CLASSIFY_SYSTEM, items_text, max_tokens=1500)

    try:
        # Strip markdown code fences if present
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        classified = json.loads(clean)
        url_to_class = {c["url"]: c for c in classified}
        for hit in hits:
            meta = url_to_class.get(hit["url"], {})
            hit["classification"] = meta.get("classification", "NOISE")
            hit["signal"] = meta.get("signal", "")
        return hits
    except Exception as e:
        log.error(f"Classification parse failed: {e} — raw: {raw[:200]}")
        for hit in hits:
            hit["classification"] = "UNKNOWN"
            hit["signal"] = ""
        return hits


# ── Step 3: Draft intel brief ─────────────────────────────────────────────────

BRIEF_SYSTEM = """You are writing a weekly competitive intelligence brief for
Fantopy Arena (AI agent vs agent Fantasy Premier League platform).

Format the brief in plain text suitable for Discord (use ** for bold, no markdown headers).
Structure:
  **DIRECT COMPETITORS** — list each with 1-line summary (or "None found")
  **ADJACENT SIGNALS** — top 3-5 most interesting, with why they matter
  **NOISE SKIPPED** — just a count

Keep it under 400 words. Be direct. Flag anything that needs urgent attention."""


def draft_brief(hits: list[dict]) -> str:
    if not hits:
        return "**Weekly Intel Brief** — No new signals found this week."

    relevant = [h for h in hits if h.get("classification") in ("DIRECT_COMPETITOR", "ADJACENT")]
    if not relevant:
        noise_count = len(hits)
        return f"**Weekly Intel Brief** — No relevant signals. {noise_count} items scanned, all noise."

    items_text = "\n".join(
        f'[{h["classification"]}] {h["title"]}\n  URL: {h["url"]}\n  Signal: {h.get("signal","")}'
        for h in relevant
    )

    return ask(BRIEF_SYSTEM, items_text, max_tokens=600)


# ── Step 4: Send report ───────────────────────────────────────────────────────

def send_to_discord(brief: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        log.info("No Discord webhook — skipping")
        return
    week = datetime.datetime.utcnow().strftime("%Y-W%U")
    payload = {"content": f"**Competitor Intel — Week {week}**\n\n{brief}"}
    try:
        resp = httpx.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Intel report sent to Discord")
    except Exception as e:
        log.error(f"Discord send failed: {e}")


def send_to_slack(brief: str) -> None:
    if not SLACK_WEBHOOK_URL:
        return
    week = datetime.datetime.utcnow().strftime("%Y-W%U")
    payload = {"text": f"*Competitor Intel — Week {week}*\n\n{brief}"}
    try:
        resp = httpx.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Intel report sent to Slack")
    except Exception as e:
        log.error(f"Slack send failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    log.info("=== Agent 9: Competitor Monitor — starting ===")
    ensure_intel_log_table()

    all_hits = search_twitter() + search_github() + search_product_hunt()
    log.info(f"Raw hits: {len(all_hits)}")

    if not all_hits:
        send_to_discord("**Weekly Intel Brief** — No new signals found this week.")
        send_to_slack("*Weekly Intel Brief* — No new signals found this week.")
        return

    classified = classify_hits(all_hits)

    # Mark all seen in DB
    for hit in classified:
        mark_seen(hit["url"], hit["source"], hit.get("classification", "NOISE"))

    brief = draft_brief(classified)
    log.info(f"Brief drafted ({len(brief)} chars)")

    send_to_discord(brief)
    send_to_slack(brief)

    direct = sum(1 for h in classified if h.get("classification") == "DIRECT_COMPETITOR")
    adjacent = sum(1 for h in classified if h.get("classification") == "ADJACENT")
    log.info(f"=== Done. {direct} direct competitors, {adjacent} adjacent signals ===")


if __name__ == "__main__":
    run()
