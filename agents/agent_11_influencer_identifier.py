"""
================================================================================
AGENT 11: THE INFLUENCER IDENTIFIER
================================================================================
TRIGGER:      Every Sunday 08:00 UTC cron
INPUTS:       Twitter API
OUTPUTS:      Ranked influencer list + tailored collab pitch per account
              → Google Sheets queue for human review
HUMAN REVIEW: YES — always. Human reviews and sends pitches.
BUILD:        Month 2+
BLOCKED ON:   Twitter bearer token, Google Sheets
================================================================================

TARGETING CRITERIA (from workflow doc):
  High audience fit score = high engagement in AI + FPL overlap

  Scoring factors:
    - Follower count (weighted less — engagement matters more)
    - Posts about FPL regularly
    - Posts about AI/Python/automation
    - No crypto red flags (avoids negative association)
    - Engagement rate > 2% (real audience)
    - Recent activity (posted in last 30 days)

EXAMPLE OUTPUT (from workflow doc):
  "@FPLReview has 89k followers, posts about automation regularly,
   no crypto mentions = low friction pitch.
   Recommended angle: [draft]"

PITCH ANGLES:
  - "Feature Fantopy in a YouTube video / Twitter thread"
  - "Play a challenge gameweek against an agent live"
  - "Affiliate: refer builders, earn % of entry fees"
  - "Co-create content: your FPL takes vs AI agent picks"
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
log = logging.getLogger("agent_11_influencer")

TWITTER_BEARER = os.environ.get("TWITTER_BEARER_TOKEN", "")
SHEET_ID       = os.environ.get("RECRUITER_SHEET_ID", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

SHEET_HEADERS = [
    "timestamp", "twitter_handle", "follower_count", "engagement_rate",
    "fit_score", "fpl_focus", "ai_focus", "crypto_flags",
    "recent_sample_tweet", "pitch_angle", "pitch_draft", "status", "notes"
]

SEARCH_QUERIES = [
    "FPL tips analysis -is:retweet lang:en min_faves:20",
    "fantasy premier league data analysis python -is:retweet lang:en",
    "FPL youtube channel -is:retweet lang:en min_faves:10",
    "AI automation football -is:retweet lang:en min_faves:15",
    "fantasy football automation bot -is:retweet lang:en min_faves:10",
]

CRYPTO_RED_FLAGS = ["nft", "crypto", "web3", "token", "presale", "rugpull", "shitcoin"]

# ── DB helpers ────────────────────────────────────────────────────────────────

def ensure_influencer_log() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS influencer_log (
                id SERIAL PRIMARY KEY,
                twitter_handle TEXT UNIQUE NOT NULL,
                fit_score FLOAT,
                pitched_at TIMESTAMPTZ,
                status TEXT DEFAULT 'IDENTIFIED'
            )
        """))
        session.commit()


def already_identified(handle: str) -> bool:
    with Session() as session:
        return session.execute(
            text("SELECT 1 FROM influencer_log WHERE twitter_handle = :h LIMIT 1"),
            {"h": handle.lower()}
        ).fetchone() is not None


def log_influencer(handle: str, fit_score: float) -> None:
    with Session() as session:
        try:
            session.execute(text("""
                INSERT INTO influencer_log (twitter_handle, fit_score)
                VALUES (:h, :s) ON CONFLICT (twitter_handle) DO NOTHING
            """), {"h": handle.lower(), "s": fit_score})
            session.commit()
        except Exception as e:
            log.warning(f"DB log failed: {e}")


# ── Discovery + scoring ───────────────────────────────────────────────────────

def score_account(user, recent_tweets: list) -> dict:
    """Score an influencer by audience fit. Returns score dict."""
    followers = user.public_metrics.get("followers_count", 0) if user.public_metrics else 0
    tweet_count = user.public_metrics.get("tweet_count", 1) if user.public_metrics else 1

    # Analyse recent tweets
    all_text = " ".join(t.text.lower() for t in recent_tweets[:10])
    bio_text = (user.description or "").lower()
    combined = all_text + " " + bio_text

    # Scoring
    fpl_focus   = sum(1 for kw in ["fpl", "fantasy premier league", "gameweek", "transfer", "captain"] if kw in combined) >= 3
    ai_focus    = sum(1 for kw in ["python", "ai", "automation", "bot", "agent", "data", "model"] if kw in combined) >= 2
    crypto_flag = any(kw in combined for kw in CRYPTO_RED_FLAGS)

    # Engagement rate proxy (likes + retweets per tweet, from recent)
    total_engagement = sum(
        (t.public_metrics.get("like_count", 0) + t.public_metrics.get("retweet_count", 0))
        for t in recent_tweets if t.public_metrics
    )
    eng_rate = (total_engagement / max(len(recent_tweets), 1)) / max(followers, 1) * 100

    # Fit score
    score = 0.0
    if fpl_focus:     score += 35
    if ai_focus:      score += 25
    if not crypto_flag: score += 20
    if eng_rate > 1:  score += 15
    if followers > 1000:  score += 5

    # Follower range bonus (sweet spot: 2k-200k)
    if 2000 <= followers <= 200000:
        score += 10
    elif followers > 200000:
        score += 5  # big but maybe harder to reach

    return {
        "handle": user.username,
        "followers": followers,
        "eng_rate": round(eng_rate, 3),
        "fit_score": round(score, 1),
        "fpl_focus": fpl_focus,
        "ai_focus": ai_focus,
        "crypto_flag": crypto_flag,
        "sample_tweet": recent_tweets[0].text[:150] if recent_tweets else "",
    }


def discover_influencers() -> list[dict]:
    client = tweepy.Client(bearer_token=TWITTER_BEARER, wait_on_rate_limit=True)
    seen_users = set()
    candidates = []

    for query in SEARCH_QUERIES:
        log.info(f"Searching: {query[:60]}")
        try:
            response = client.search_recent_tweets(
                query=query, max_results=10,
                tweet_fields=["author_id", "text", "public_metrics"],
                expansions=["author_id"],
                user_fields=["username", "name", "description", "public_metrics"],
            )
            if not response.data:
                continue
            users_by_id = {u.id: u for u in ((response.includes or {}).get("users") or [])}

            for tweet in response.data:
                user = users_by_id.get(tweet.author_id)
                if not user or user.username in seen_users:
                    continue
                seen_users.add(user.username)

                if already_identified(user.username):
                    continue

                followers = (user.public_metrics or {}).get("followers_count", 0)
                if followers < 500:
                    continue

                # Fetch recent tweets for scoring
                try:
                    recent_resp = client.get_users_tweets(
                        user.id,
                        max_results=10,
                        tweet_fields=["public_metrics", "text"],
                    )
                    recent = recent_resp.data or [tweet]
                except Exception:
                    recent = [tweet]

                scored = score_account(user, recent)
                if scored["fit_score"] >= 50 and not scored["crypto_flag"]:
                    candidates.append(scored)

        except tweepy.TweepyException as e:
            log.error(f"Twitter error: {e}")

    return sorted(candidates, key=lambda c: c["fit_score"], reverse=True)


# ── LLM: Draft pitch ──────────────────────────────────────────────────────────

PITCH_SYSTEM = """You are drafting a collab pitch for Fantopy Arena — an AI agent
vs agent Fantasy Premier League competition platform.

Based on what you know about the influencer, recommend ONE pitch angle and write
a SHORT (≤100 word) personalised DM that:
1. Opens with something specific about their content
2. Proposes the collab angle naturally
3. Makes a low-friction ask

Pitch angles available:
  - Feature Fantopy in a video/thread about FPL automation tools
  - "Beat the Bot" challenge: play a GW against an AI agent, post results
  - Affiliate: refer builders, earn % of entry fees
  - Co-create: their FPL takes vs what the AI agents actually pick each GW

Choose the angle that fits their content style best.
Tone: casual, peer-to-peer, no corporate language. No exclamation marks.
Output JSON: {"angle": "...", "pitch": "..."}"""


def draft_pitch(influencer: dict) -> tuple[str, str]:
    prompt = f"""Influencer: @{influencer['handle']}
Followers: {influencer['followers']:,}
FPL focus: {influencer['fpl_focus']}
AI/tech focus: {influencer['ai_focus']}
Engagement rate: {influencer['eng_rate']}%
Recent tweet sample: {influencer['sample_tweet']}

Draft the pitch."""
    raw = ask(PITCH_SYSTEM, prompt, max_tokens=250)
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(clean)
        return data.get("angle", ""), data.get("pitch", raw)
    except Exception:
        return "general", raw


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    log.info("=== Agent 11: Influencer Identifier — starting ===")
    ensure_influencer_log()

    candidates = discover_influencers()
    log.info(f"Found {len(candidates)} qualified influencers")

    queued = 0
    for inf in candidates[:8]:  # max 8 per run
        log.info(f"  @{inf['handle']} — fit score {inf['fit_score']}")
        angle, pitch = draft_pitch(inf)
        row = [
            datetime.datetime.utcnow().isoformat(),
            inf["handle"], inf["followers"], inf["eng_rate"],
            inf["fit_score"],
            "YES" if inf["fpl_focus"] else "NO",
            "YES" if inf["ai_focus"] else "NO",
            "YES" if inf["crypto_flag"] else "NO",
            inf["sample_tweet"], angle, pitch, "PENDING", ""
        ]
        try:
            ws = get_sheet(SHEET_ID, "InfluencerQueue")
            if ws.row_count == 0 or not ws.row_values(1):
                ws.insert_row(SHEET_HEADERS, 1)
            append_to_queue(SHEET_ID, row, worksheet_name="InfluencerQueue")
            log_influencer(inf["handle"], inf["fit_score"])
            queued += 1
        except Exception as e:
            log.error(f"  Sheets write failed: {e}")

    if queued > 0 and DISCORD_WEBHOOK:
        try:
            httpx.post(DISCORD_WEBHOOK, json={
                "content": f"**Agent 11 — Influencer Identifier** found {queued} influencer(s) this week. Check Influencer Queue sheet."
            }, timeout=10)
        except Exception as e:
            log.error(f"Discord notify failed: {e}")

    log.info(f"=== Done. {queued} influencers queued ===")


if __name__ == "__main__":
    run()
