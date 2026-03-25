"""
================================================================================
AGENT 8: THE PARTNERSHIP SCOUT
================================================================================
TRIGGER:      Every Monday 09:00 UTC cron
INPUTS:       Twitter API, GitHub API, product news RSS feeds
OUTPUTS:      Partnership pitch drafts → Google Sheets queue for human review
HUMAN REVIEW: YES — always. Pitches go to Sheets, Discord ping, human sends.
BUILD:        Month 2+
BLOCKED ON:   Twitter bearer token, GitHub token, Google Sheets
================================================================================

WHAT IT MONITORS:
  - AI framework launches/updates: LangChain, CrewAI, AutoGen, LlamaIndex
  - Hackathon announcements: Devpost, GitHub, Twitter
  - FPL tool launches: new bots, APIs, data providers
  - Agent framework communities: new releases with >100 GitHub stars in a week

PARTNERSHIP ANGLES:
  - "Feature Fantopy in your launch content" (new framework launch)
  - "Run a Fantopy challenge at your hackathon"
  - "Integrate Fantopy as a benchmark/test environment for your agent framework"
  - "Co-marketing: your FPL data tool + our competition platform"

TRIGGER EXAMPLES (from workflow doc):
  "CrewAI just announced v3" → draft pitch for Fantopy to be featured
  "New AI hackathon announced" → draft pitch to add Fantopy as a challenge track
  "FPL data API launched with 1k stars" → draft integration/partnership pitch
================================================================================
"""

import os
import sys
import logging
import datetime
import feedparser
import httpx
from dotenv import load_dotenv
import tweepy
from github import Github, GithubException
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session
from shared.sheets import append_to_queue, get_sheet
from shared.llm import ask

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_08_partnership")

TWITTER_BEARER = os.environ.get("TWITTER_BEARER_TOKEN", "")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
SHEET_ID       = os.environ.get("RECRUITER_SHEET_ID", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

SHEET_HEADERS = [
    "timestamp", "source", "url", "target_name", "opportunity_type",
    "trigger_summary", "pitch_draft", "contact_info", "status", "notes"
]

# Framework keywords to watch
FRAMEWORK_KEYWORDS = [
    "LangChain", "CrewAI", "AutoGen", "LlamaIndex", "smolagents",
    "OpenAI Agents SDK", "Anthropic Claude agent"
]
HACKATHON_KEYWORDS = ["hackathon", "buildathon", "AI challenge", "agent competition"]
FPL_TOOL_KEYWORDS  = ["fantasy premier league api", "fpl data", "fpl statistics api"]

NEWS_RSS_FEEDS = [
    "https://dev.to/feed",
    "https://hackernoon.com/feed",
]

# ── DB helpers ────────────────────────────────────────────────────────────────

def ensure_partnership_log() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS partnership_log (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                target_name TEXT,
                opportunity_type TEXT,
                queued_at TIMESTAMPTZ DEFAULT NOW(),
                status TEXT DEFAULT 'PENDING'
            )
        """))
        session.commit()


def already_pitched(url: str) -> bool:
    with Session() as session:
        return session.execute(
            text("SELECT 1 FROM partnership_log WHERE url = :url LIMIT 1"),
            {"url": url}
        ).fetchone() is not None


def log_opportunity(url: str, target: str, opp_type: str) -> None:
    with Session() as session:
        try:
            session.execute(text("""
                INSERT INTO partnership_log (url, target_name, opportunity_type)
                VALUES (:url, :target, :type) ON CONFLICT (url) DO NOTHING
            """), {"url": url, "target": target, "type": opp_type})
            session.commit()
        except Exception as e:
            log.warning(f"DB log failed: {e}")


# ── Discovery ─────────────────────────────────────────────────────────────────

def search_github_launches() -> list[dict]:
    """Find fast-rising repos in AI agent / FPL space from the past 7 days."""
    gh = Github(GITHUB_TOKEN)
    hits = []
    since = datetime.datetime.utcnow() - datetime.timedelta(days=7)

    queries = [
        "langchain agent framework stars:>50 pushed:>2026-01-01",
        "crewai agent python stars:>50 pushed:>2026-01-01",
        "fantasy premier league api python stars:>10",
        "ai agent competition game stars:>20",
    ]

    for query in queries:
        try:
            results = gh.search_repositories(query=query, sort="updated", order="desc")
            for repo in results[:5]:
                if repo.updated_at and repo.updated_at.replace(tzinfo=None) < since:
                    continue
                if already_pitched(repo.html_url):
                    continue

                # Classify opportunity
                combined = f"{repo.name} {repo.description or ''}".lower()
                if any(kw.lower() in combined for kw in ["langchain", "crewai", "autogen", "agent framework"]):
                    opp_type = "framework_launch"
                elif any(kw.lower() in combined for kw in ["fpl", "fantasy premier league"]):
                    opp_type = "fpl_tool"
                else:
                    opp_type = "ai_tool"

                hits.append({
                    "source": "github",
                    "url": repo.html_url,
                    "target_name": repo.full_name,
                    "opportunity_type": opp_type,
                    "trigger": f"{repo.description or ''} — ★{repo.stargazers_count}",
                    "contact": f"https://github.com/{repo.owner.login}",
                })
        except GithubException as e:
            log.error(f"GitHub search error: {e}")

    return hits


def search_twitter_launches() -> list[dict]:
    if not TWITTER_BEARER:
        return []
    client = tweepy.Client(bearer_token=TWITTER_BEARER, wait_on_rate_limit=True)
    hits = []
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    queries = [
        f'"{kw}" launch OR release OR announced -is:retweet lang:en'
        for kw in FRAMEWORK_KEYWORDS[:4]
    ] + ['"AI hackathon" -is:retweet lang:en', '"FPL api" launch -is:retweet lang:en']

    for query in queries:
        try:
            response = client.search_recent_tweets(
                query=query, max_results=5,
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
                if already_pitched(url):
                    continue
                metrics = tweet.public_metrics or {}
                if metrics.get("like_count", 0) < 10:
                    continue  # skip low-signal
                user = users_by_id.get(tweet.author_id)
                combined = tweet.text.lower()
                if any(kw.lower() in combined for kw in HACKATHON_KEYWORDS):
                    opp_type = "hackathon"
                elif any(kw.lower() in combined for kw in FRAMEWORK_KEYWORDS):
                    opp_type = "framework_launch"
                else:
                    opp_type = "general_ai"

                hits.append({
                    "source": "twitter",
                    "url": url,
                    "target_name": user.name if user else "Unknown",
                    "opportunity_type": opp_type,
                    "trigger": tweet.text[:200],
                    "contact": f"@{user.username}" if user else "",
                })
        except tweepy.TweepyException as e:
            log.error(f"Twitter error: {e}")

    return hits


def search_rss_news() -> list[dict]:
    hits = []
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    all_keywords = FRAMEWORK_KEYWORDS + HACKATHON_KEYWORDS + FPL_TOOL_KEYWORDS

    for feed_url in NEWS_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:30]:
                combined = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
                if not any(kw.lower() in combined for kw in all_keywords):
                    continue
                url = entry.get("link", "")
                if not url or already_pitched(url):
                    continue
                opp_type = "hackathon" if any(kw.lower() in combined for kw in HACKATHON_KEYWORDS) else "framework_launch"
                hits.append({
                    "source": "rss",
                    "url": url,
                    "target_name": entry.get("author", feed.feed.get("title", "Unknown")),
                    "opportunity_type": opp_type,
                    "trigger": entry.get("title", ""),
                    "contact": "",
                })
        except Exception as e:
            log.error(f"RSS error {feed_url}: {e}")

    return hits


# ── LLM: Write pitch ──────────────────────────────────────────────────────────

PITCH_SYSTEM = """You are drafting a partnership outreach email/DM for Fantopy Arena —
an AI agent vs agent Fantasy Premier League competition platform built by Benchwarmers Pte Ltd.

Write a SHORT personalised pitch (≤150 words) that:
1. Opens by referencing the specific thing they announced/built
2. Proposes one clear, concrete partnership angle
3. Makes an easy ask (30-min call, feature us in your docs, etc.)

Partnership angles by type:
  framework_launch → "Use Fantopy Arena as a real-world benchmark for your agents"
  hackathon → "Add a Fantopy Arena track — best agent wins prize pool in USDC"
  fpl_tool → "Integrate your data into our competition platform"
  general_ai → "Feature Fantopy in your launch content / newsletter"

Tone: peer-to-peer, builder energy. Not corporate. No exclamation marks.
Output ONLY the pitch text."""


def draft_pitch(opportunity: dict) -> str:
    prompt = f"""Target: {opportunity['target_name']}
Opportunity type: {opportunity['opportunity_type']}
Trigger (what they announced/built): {opportunity['trigger']}
Their contact: {opportunity.get('contact', 'unknown')}

Write the partnership pitch."""
    return ask(PITCH_SYSTEM, prompt, max_tokens=250)


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    log.info("=== Agent 8: Partnership Scout — starting ===")
    ensure_partnership_log()

    all_opps = search_github_launches() + search_twitter_launches() + search_rss_news()
    log.info(f"Found {len(all_opps)} new opportunities")

    queued = 0
    for opp in all_opps[:5]:  # max 5 pitches per run
        log.info(f"  Drafting pitch for: {opp['target_name']} ({opp['opportunity_type']})")
        pitch = draft_pitch(opp)
        row = [
            datetime.datetime.utcnow().isoformat(),
            opp["source"], opp["url"], opp["target_name"],
            opp["opportunity_type"], opp["trigger"][:200],
            pitch, opp.get("contact", ""), "PENDING", ""
        ]
        try:
            ws = get_sheet(SHEET_ID, "PartnershipQueue")
            if ws.row_count == 0 or not ws.row_values(1):
                ws.insert_row(SHEET_HEADERS, 1)
            append_to_queue(SHEET_ID, row, worksheet_name="PartnershipQueue")
            log_opportunity(opp["url"], opp["target_name"], opp["opportunity_type"])
            queued += 1
        except Exception as e:
            log.error(f"  Sheets write failed: {e}")

    if queued > 0 and DISCORD_WEBHOOK:
        try:
            httpx.post(DISCORD_WEBHOOK, json={
                "content": f"**Agent 8 — Partnership Scout** found {queued} opportunity/ies this week. Check Partnership Queue sheet."
            }, timeout=10)
        except Exception as e:
            log.error(f"Discord notify failed: {e}")

    log.info(f"=== Done. {queued} pitches queued ===")


if __name__ == "__main__":
    run()
