"""
================================================================================
AGENT 3: THE RECRUITER
================================================================================
TRIGGER:      Monday 08:00 UTC cron (GitHub Actions)
INPUTS:       GitHub API, Twitter/X API
OUTPUTS:      Google Sheets queue — one row per prospect, with personalised
              outreach draft for human review before sending
HUMAN REVIEW: YES — writes drafts to Sheets, pings Discord, waits for approval
FREQUENCY:    Weekly (Monday)
DEDUP:        Postgres table `recruiter_prospects` keyed on github_username
              or twitter_handle — never contacts the same person twice
BLOCKED ON:   Nothing — all credentials self-contained
================================================================================

HOW IT WORKS
1. DISCOVERY  Search GitHub for repos tagged fpl-bot, fantasy-football,
              ai-agent, fpl-ai. Search Twitter for FPL bot builders.
2. RESEARCH   For each prospect: read their repo README + recent commits,
              summarise what they built.
3. DRAFT      Claude writes a personalised DM/email referencing their
              specific project and why Fantopy Arena suits them.
4. REVIEW     Appends draft to Google Sheets queue with status=PENDING.
5. NOTIFY     Pings Discord with count of new drafts awaiting review.

Human approves rows in Sheets → separate send script handles delivery.
================================================================================
"""

import os
import sys
import logging
import datetime
from dotenv import load_dotenv
from github import Github, GithubException
import tweepy
import httpx

# Add parent dir to path for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import has_been_contacted, log_contact
from shared.sheets import append_to_queue
from shared.llm import ask

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_03_recruiter")

# ── Config ────────────────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
TWITTER_BEARER_TOKEN = os.environ["TWITTER_BEARER_TOKEN"]
SHEET_ID = os.environ["RECRUITER_SHEET_ID"]
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DB_TABLE = "recruiter_prospects"

MAX_GITHUB_PROSPECTS = 30   # per run
MAX_TWITTER_PROSPECTS = 20  # per run

GITHUB_SEARCH_QUERIES = [
    "fpl bot fantasy premier league stars:>5",
    "fpl ai agent fantasy football stars:>3",
    "fantasy-football-bot python stars:>3",
    "fpl-automation stars:>2",
    "ai agent competition game python stars:>5",
]

TWITTER_SEARCH_QUERIES = [
    "built FPL bot -is:retweet lang:en",
    "fantasy premier league automation python -is:retweet lang:en",
    "FPL python bot transfer -is:retweet lang:en",
]

# ── Google Sheets columns ─────────────────────────────────────────────────────

SHEET_HEADERS = [
    "timestamp", "source", "handle", "name", "profile_url",
    "repo_url", "repo_description", "stars", "last_commit",
    "research_summary", "outreach_draft", "status", "notes"
]

# ── System prompt for LLM ─────────────────────────────────────────────────────

RESEARCH_SYSTEM = """You are a researcher for Fantopy Arena — an AI agent vs agent
Fantasy Premier League (FPL) competition platform. Your job is to read a GitHub
repo description and summarise what the builder made in 2-3 sentences, focusing on:
- What problem they solved
- Their technical approach
- How sophisticated the agent/bot appears to be
Be factual and concise. No hype."""

OUTREACH_SYSTEM = """You are writing personalised outreach for Fantopy Arena —
a platform where AI agents compete in Fantasy Premier League autonomously.
Builders deploy their agents, pay entry fees in USDC (Solana), and top agents
split prize pools at season end. The platform runs on the real EPL season.

Write a SHORT, personalised Twitter DM or cold email (≤120 words) that:
1. Opens by referencing something SPECIFIC about their project (not generic praise)
2. Explains what Fantopy Arena is in one sentence
3. Makes a clear, low-friction call to action (join waitlist at fantopyarena.com)

Tone: peer-to-peer, builder-to-builder. Not salesy. No exclamation marks.
Do not mention money/prizes in the first message.
Output ONLY the message text — no subject line, no sign-off placeholder."""

# ── Step 1: Discovery — GitHub ────────────────────────────────────────────────

def search_github() -> list[dict]:
    gh = Github(GITHUB_TOKEN)
    prospects = []
    seen_users = set()

    for query in GITHUB_SEARCH_QUERIES:
        log.info(f"GitHub search: '{query}'")
        try:
            results = gh.search_repositories(query=query, sort="stars", order="desc")
            for repo in results[:10]:
                username = repo.owner.login
                if username in seen_users:
                    continue
                seen_users.add(username)

                # Dedup check
                if has_been_contacted(DB_TABLE, "github_username", username):
                    log.info(f"  Skip (already contacted): {username}")
                    continue

                prospects.append({
                    "source": "github",
                    "handle": username,
                    "name": repo.owner.name or username,
                    "profile_url": f"https://github.com/{username}",
                    "repo_url": repo.html_url,
                    "repo_name": repo.name,
                    "repo_description": repo.description or "",
                    "stars": repo.stargazers_count,
                    "last_commit": str(repo.updated_at.date()) if repo.updated_at else "",
                    "readme": _get_readme(repo),
                })

                if len(prospects) >= MAX_GITHUB_PROSPECTS:
                    return prospects

        except GithubException as e:
            log.error(f"GitHub search error: {e}")

    return prospects


def _get_readme(repo) -> str:
    """Fetch first 800 chars of README for LLM research."""
    try:
        readme = repo.get_readme()
        return readme.decoded_content.decode("utf-8", errors="ignore")[:800]
    except Exception:
        return ""


# ── Step 1: Discovery — Twitter ───────────────────────────────────────────────

def search_twitter() -> list[dict]:
    client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN, wait_on_rate_limit=True)
    prospects = []
    seen_users = set()

    for query in TWITTER_SEARCH_QUERIES:
        log.info(f"Twitter search: '{query}'")
        try:
            response = client.search_recent_tweets(
                query=query,
                max_results=10,
                tweet_fields=["author_id", "text", "created_at"],
                expansions=["author_id"],
                user_fields=["username", "name", "description", "public_metrics"],
            )

            if not response.data:
                continue

            users_by_id = {u.id: u for u in ((response.includes or {}).get("users") or [])}

            for tweet in response.data:
                user = users_by_id.get(tweet.author_id)
                if not user:
                    continue

                handle = user.username
                if handle in seen_users:
                    continue
                seen_users.add(handle)

                if has_been_contacted(DB_TABLE, "twitter_handle", handle):
                    log.info(f"  Skip (already contacted): @{handle}")
                    continue

                prospects.append({
                    "source": "twitter",
                    "handle": handle,
                    "name": user.name,
                    "profile_url": f"https://twitter.com/{handle}",
                    "repo_url": "",
                    "repo_name": "",
                    "repo_description": user.description or "",
                    "stars": 0,
                    "last_commit": "",
                    "readme": tweet.text,  # use tweet text as research input
                })

                if len(prospects) >= MAX_TWITTER_PROSPECTS:
                    return prospects

        except tweepy.TweepyException as e:
            log.error(f"Twitter search error: {e}")

    return prospects


# ── Step 2: Research ──────────────────────────────────────────────────────────

def research_prospect(prospect: dict) -> str:
    user_prompt = f"""GitHub username: {prospect['handle']}
Repo: {prospect.get('repo_name', 'N/A')}
Description: {prospect['repo_description']}
README excerpt:
{prospect['readme']}

Summarise what this builder made."""

    return ask(RESEARCH_SYSTEM, user_prompt, max_tokens=200)


# ── Step 3: Draft outreach ────────────────────────────────────────────────────

def draft_outreach(prospect: dict, research_summary: str) -> str:
    user_prompt = f"""Builder: {prospect['name']} (@{prospect['handle']})
Their project summary: {research_summary}
Their repo/profile: {prospect['profile_url']}

Write the outreach message."""

    return ask(OUTREACH_SYSTEM, user_prompt, max_tokens=180)


# ── Step 4: Write to Google Sheets ───────────────────────────────────────────

def queue_to_sheets(prospect: dict, research_summary: str, outreach_draft: str) -> None:
    row = [
        datetime.datetime.utcnow().isoformat(),
        prospect["source"],
        prospect["handle"],
        prospect["name"],
        prospect["profile_url"],
        prospect.get("repo_url", ""),
        prospect["repo_description"][:200],
        prospect.get("stars", 0),
        prospect.get("last_commit", ""),
        research_summary,
        outreach_draft,
        "PENDING",
        "",
    ]
    append_to_queue(SHEET_ID, row, worksheet_name="Queue")
    log.info(f"  Queued to Sheets: {prospect['handle']}")


# ── Step 7: Track in Postgres ─────────────────────────────────────────────────

def track_prospect(prospect: dict) -> None:
    data = {
        "github_username": prospect["handle"] if prospect["source"] == "github" else None,
        "twitter_handle": prospect["handle"] if prospect["source"] == "twitter" else None,
        "source": prospect["source"],
        "profile_url": prospect["profile_url"],
        "queued_at": datetime.datetime.utcnow().isoformat(),
        "status": "PENDING",
    }
    # Remove None values
    data = {k: v for k, v in data.items() if v is not None}
    try:
        log_contact(DB_TABLE, data)
    except Exception as e:
        log.warning(f"  DB log failed (may not exist yet): {e}")


# ── Step 5: Notify Discord ────────────────────────────────────────────────────

def notify_discord(count: int) -> None:
    if not DISCORD_WEBHOOK_URL:
        log.info("No Discord webhook configured — skipping notification")
        return
    try:
        payload = {
            "content": (
                f"**Agent 3 — Recruiter run complete** \n"
                f"{count} new prospect draft(s) queued for review.\n"
                f"Open the Google Sheet to approve or reject outreach."
            )
        }
        httpx.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        log.info(f"Discord notification sent ({count} drafts)")
    except Exception as e:
        log.error(f"Discord notify failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    log.info("=== Agent 3: The Recruiter — starting run ===")
    queued = 0

    # Ensure Sheets has header row
    try:
        from shared.sheets import get_sheet
        ws = get_sheet(SHEET_ID, "Queue")
        if ws.row_count == 0 or not ws.row_values(1):
            ws.insert_row(SHEET_HEADERS, 1)
    except Exception as e:
        log.warning(f"Could not write sheet headers: {e}")

    all_prospects = search_github() + search_twitter()
    log.info(f"Found {len(all_prospects)} new prospects to process")

    for prospect in all_prospects:
        try:
            log.info(f"Processing: {prospect['handle']} ({prospect['source']})")

            research = research_prospect(prospect)
            log.info(f"  Research done")

            draft = draft_outreach(prospect, research)
            log.info(f"  Draft done")

            queue_to_sheets(prospect, research, draft)
            track_prospect(prospect)
            queued += 1

        except Exception as e:
            log.error(f"  Failed on {prospect['handle']}: {e}")
            continue

    notify_discord(queued)
    log.info(f"=== Done. {queued} prospects queued. ===")


if __name__ == "__main__":
    run()
