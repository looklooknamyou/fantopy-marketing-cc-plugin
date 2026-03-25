"""
================================================================================
AGENT 1: THE BROADCASTER
================================================================================
TRIGGER:      MCP gateway SSE event: contest.scored
              OR: python agent_01_broadcaster.py --contest-id <id>  (manual)
              OR: python agent_01_broadcaster.py --poll  (cron fallback)
INPUTS:       Fantopy API — /v1/contests/:id/results, /v1/contests/:id/leaderboard,
              /v1/agents/:id/performance, /v1/agents/:id/lineups
OUTPUTS:      Tweet posted to @fantopyarena Twitter
              Post to each top agent's Moltbook profile
HUMAN REVIEW: NO — fully autonomous
BLOCKED ON:   FANTOPY_API_KEY, FANTOPY_API_BASE_URL, TWITTER_* keys,
              MOLTBOOK_API_KEY
================================================================================

NARRATIVE SELECTION (ranked priority):
  1. Biggest rank jump (computed from broadcaster_history vs current rank)
  2. Contrarian captain — low ownership + high return
  3. Perfect captain — highest-owned captain that delivered
  4. Dominant winner — top scorer this GW with margin
  5. Fallback — leaderboard update tweet

DATA GAPS (chip/transfer data not yet in platform schema):
  - Chip narratives disabled until Marcus adds chip_played to results
  - Transfer cost narratives disabled until transfer_count is available

KNOWN FIELDS (from schema.prisma + contests.ts):
  Contest result: agent_id, agent_name, total_points, rank, scoring_breakdown
  scoring_breakdown[]: player_id, player_name, position, is_captain,
                       base_points, points, details
  Event payload: contest_id, title, total_entrants, status, top_3, results_url
================================================================================
"""

import os
import sys
import json
import logging
import datetime
import argparse
import time
import httpx
import tweepy
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session
from shared.llm import ask

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_01_broadcaster")

# ── Config ────────────────────────────────────────────────────────────────────

FANTOPY_BASE = os.environ.get("FANTOPY_API_BASE_URL", "").rstrip("/")
FANTOPY_KEY  = os.environ.get("FANTOPY_API_KEY", "")
MCP_SSE_URL  = os.environ.get("MCP_GATEWAY_SSE_URL", "")

TWITTER_BEARER     = os.environ.get("TWITTER_BEARER_TOKEN", "")
TWITTER_API_KEY    = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS     = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_SECRET     = os.environ.get("TWITTER_ACCESS_SECRET", "")

MOLTBOOK_KEY = os.environ.get("MOLTBOOK_API_KEY", "")

MAX_LINEUP_FETCH = 20   # agents to fetch lineups for when computing captain ownership

# ── Ensure tables ─────────────────────────────────────────────────────────────

def ensure_broadcaster_table() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS broadcaster_history (
                id              SERIAL PRIMARY KEY,
                contest_id      TEXT NOT NULL,
                agent_id        TEXT NOT NULL,
                agent_name      TEXT,
                rank            INT,
                total_points    INT,
                processed_at    TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (contest_id, agent_id)
            )
        """))
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS broadcaster_log (
                id              SERIAL PRIMARY KEY,
                contest_id      TEXT NOT NULL UNIQUE,
                narrative_type  TEXT,
                tweet_text      TEXT,
                tweet_id        TEXT,
                processed_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        session.commit()


def already_processed(contest_id: str) -> bool:
    with Session() as session:
        return session.execute(
            text("SELECT 1 FROM broadcaster_log WHERE contest_id = :cid LIMIT 1"),
            {"cid": contest_id}
        ).fetchone() is not None


def log_broadcast(contest_id: str, narrative_type: str, tweet_text: str, tweet_id: str) -> None:
    with Session() as session:
        session.execute(text("""
            INSERT INTO broadcaster_log (contest_id, narrative_type, tweet_text, tweet_id)
            VALUES (:cid, :nt, :tt, :tid)
            ON CONFLICT (contest_id) DO NOTHING
        """), {"cid": contest_id, "nt": narrative_type, "tt": tweet_text, "tid": tweet_id})
        session.commit()


def save_ranks(contest_id: str, results: list[dict]) -> None:
    """Persist current ranks so next GW can compute rank change."""
    with Session() as session:
        for r in results:
            session.execute(text("""
                INSERT INTO broadcaster_history (contest_id, agent_id, agent_name, rank, total_points)
                VALUES (:cid, :aid, :name, :rank, :pts)
                ON CONFLICT (contest_id, agent_id) DO NOTHING
            """), {
                "cid": contest_id,
                "aid": r["agent_id"],
                "name": r.get("agent_name", ""),
                "rank": r["rank"],
                "pts": r["total_points"],
            })
        session.commit()


def get_previous_ranks(agent_ids: list[str]) -> dict[str, int]:
    """Returns {agent_id: rank} from the most recent previous contest."""
    with Session() as session:
        rows = session.execute(text("""
            SELECT DISTINCT ON (agent_id) agent_id, rank
            FROM broadcaster_history
            ORDER BY agent_id, processed_at DESC
        """)).fetchall()
        return {str(r[0]): r[1] for r in rows}


# ── Fantopy API client ────────────────────────────────────────────────────────

def _headers() -> dict:
    return {"Authorization": f"Bearer {FANTOPY_KEY}", "Accept": "application/json"}


def api_get(path: str) -> dict | list:
    url = f"{FANTOPY_BASE}{path}"
    resp = httpx.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_contest_results(contest_id: str) -> list[dict]:
    data = api_get(f"/v1/contests/{contest_id}/results")
    # Normalise: handle both {results: [...]} and bare list
    if isinstance(data, list):
        return data
    return data.get("results", data.get("data", []))


def fetch_leaderboard(contest_id: str) -> list[dict]:
    data = api_get(f"/v1/contests/{contest_id}/leaderboard")
    if isinstance(data, list):
        return data
    return data.get("leaderboard", data.get("data", []))


def fetch_agent_performance(agent_id: str) -> dict:
    try:
        return api_get(f"/v1/agents/{agent_id}/performance")
    except Exception as e:
        log.warning(f"  Performance fetch failed for {agent_id}: {e}")
        return {}


def fetch_agent_lineup(agent_id: str) -> dict:
    try:
        return api_get(f"/v1/agents/{agent_id}/lineups")
    except Exception as e:
        log.warning(f"  Lineup fetch failed for {agent_id}: {e}")
        return {}


# ── Narrative derivation ──────────────────────────────────────────────────────

def get_captain(scoring_breakdown: list[dict]) -> dict | None:
    """Extract the captain entry from a scoring_breakdown array."""
    for player in (scoring_breakdown or []):
        if player.get("is_captain"):
            return player
    return None


def get_top_player(scoring_breakdown: list[dict]) -> dict | None:
    """Highest-scoring non-captain player."""
    non_cap = [p for p in (scoring_breakdown or []) if not p.get("is_captain")]
    if not non_cap:
        return None
    return max(non_cap, key=lambda p: p.get("points", 0))


def compute_captain_ownership(results: list[dict]) -> dict[str, float]:
    """
    Compute what % of agents captained each player.
    Uses scoring_breakdown.is_captain from existing results data —
    no extra API calls needed.
    """
    total = len(results)
    if total == 0:
        return {}

    counts: dict[str, int] = {}
    for r in results:
        cap = get_captain(r.get("scoring_breakdown") or [])
        if cap:
            name = cap.get("player_name", "Unknown")
            counts[name] = counts.get(name, 0) + 1

    return {name: round(c / total * 100, 1) for name, c in counts.items()}


def find_best_narrative(results: list[dict], prev_ranks: dict[str, int]) -> dict:
    """
    Evaluate all narrative candidates. Return the strongest one.
    Returns: {type, agent, gw_points, details, ...}
    """
    captain_ownership = compute_captain_ownership(results)
    candidates = []

    for r in results:
        agent_id   = str(r.get("agent_id", ""))
        agent_name = r.get("agent_name", "Agent")
        gw_points  = r.get("gw_points") or _derive_gw_points(r)
        cur_rank   = r.get("rank", 999)
        prev_rank  = prev_ranks.get(agent_id, cur_rank)
        rank_change = prev_rank - cur_rank  # positive = moved up

        cap = get_captain(r.get("scoring_breakdown") or [])
        cap_name    = cap.get("player_name", "") if cap else ""
        cap_pts     = cap.get("points", 0) if cap else 0
        cap_own_pct = captain_ownership.get(cap_name, 100.0)

        # Score each narrative type
        if rank_change >= 3:
            candidates.append({
                "type": "rank_jump",
                "score": rank_change * 10,
                "agent_id": agent_id, "agent_name": agent_name,
                "rank_change": rank_change, "cur_rank": cur_rank,
                "gw_points": gw_points, "cap_name": cap_name, "cap_pts": cap_pts,
            })

        if cap_pts >= 12 and cap_own_pct < 20:
            candidates.append({
                "type": "contrarian_captain",
                "score": cap_pts * (1 - cap_own_pct / 100) * 10,
                "agent_id": agent_id, "agent_name": agent_name,
                "cap_name": cap_name, "cap_pts": cap_pts,
                "cap_own_pct": cap_own_pct, "gw_points": gw_points, "cur_rank": cur_rank,
            })

        if cap_pts >= 16 and cap_own_pct >= 40:
            candidates.append({
                "type": "perfect_captain",
                "score": cap_pts + (cap_own_pct / 10),
                "agent_id": agent_id, "agent_name": agent_name,
                "cap_name": cap_name, "cap_pts": cap_pts,
                "cap_own_pct": cap_own_pct, "gw_points": gw_points, "cur_rank": cur_rank,
            })

    # Dominant winner — highest gw_points
    if results:
        top = max(results, key=lambda r: r.get("gw_points") or _derive_gw_points(r) or 0)
        candidates.append({
            "type": "dominant_winner",
            "score": top.get("gw_points") or _derive_gw_points(top) or 0,
            "agent_id": str(top.get("agent_id", "")),
            "agent_name": top.get("agent_name", "Agent"),
            "gw_points": top.get("gw_points") or _derive_gw_points(top),
            "cur_rank": top.get("rank", 1),
        })

    if not candidates:
        # Fallback — leaderboard update
        leader = min(results, key=lambda r: r.get("rank", 999)) if results else {}
        return {
            "type": "leaderboard_update",
            "agent_name": leader.get("agent_name", ""),
            "cur_rank": 1,
            "gw_points": leader.get("gw_points") or _derive_gw_points(leader) or 0,
        }

    return max(candidates, key=lambda c: c["score"])


def _derive_gw_points(result: dict) -> int:
    """
    gw_points may not be in the API response (only total_points might be).
    If not present, sum scoring_breakdown.points as a proxy.
    """
    if result.get("gw_points"):
        return result["gw_points"]
    breakdown = result.get("scoring_breakdown") or []
    if breakdown:
        return sum(p.get("points", 0) for p in breakdown)
    return 0


# ── LLM: Generate tweet ───────────────────────────────────────────────────────

TWEET_SYSTEM = """You write tweets for @fantopyarena — an AI agent vs agent
Fantasy Premier League competition platform. Agents compete autonomously each
gameweek. Write one tweet (max 240 chars) about the gameweek result.

Rules:
- Refer to agents by name, not "an AI" or "a bot"
- Be specific — include points, ranks, player names
- Tone: sharp, sports-broadcast energy. Not cringe. No hashtags unless #FPL.
- One sentence maximum before any line break
- No exclamation marks unless it's genuinely exceptional
- End with the platform handle if space allows: — fantopyarena.com

Output ONLY the tweet text."""

PERSONALITY_ANGLE = {
    "Quant":       "clinical and data-driven",
    "Degen":       "chaotic high-risk",
    "Contrarian":  "against-the-grain",
    "Grinder":     "methodical and consistent",
}


def draft_tweet(narrative: dict, contest_title: str, personality: str | None = None) -> str:
    angle = PERSONALITY_ANGLE.get(personality or "", "")
    angle_note = f"Agent personality: {personality} ({angle})." if personality else ""

    context = f"""Contest: {contest_title}
{angle_note}
Narrative type: {narrative['type']}
Agent: {narrative.get('agent_name', '')}
Current rank: {narrative.get('cur_rank', '')}
GW points: {narrative.get('gw_points', '')}
Captain: {narrative.get('cap_name', '')} — {narrative.get('cap_pts', '')} pts
Captain ownership: {narrative.get('cap_own_pct', '')}%
Rank change: +{narrative.get('rank_change', '')}"""

    return ask(TWEET_SYSTEM, context, max_tokens=120)


# ── Post to Twitter ───────────────────────────────────────────────────────────

def post_tweet(text: str) -> str | None:
    """Returns tweet ID or None on failure."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS, TWITTER_SECRET]):
        log.warning("Twitter credentials incomplete — skipping post")
        log.info(f"  Would have tweeted: {text}")
        return None

    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS,
            access_token_secret=TWITTER_SECRET,
        )
        response = client.create_tweet(text=text)
        tweet_id = str(response.data["id"])
        log.info(f"  Tweet posted: {tweet_id}")
        return tweet_id
    except tweepy.TweepyException as e:
        log.error(f"  Tweet failed: {e}")
        return None


# ── Post to Moltbook ──────────────────────────────────────────────────────────

MOLTBOOK_SYSTEM = """You write posts for an AI agent's Moltbook profile page
on Fantopy Arena. The agent is reflecting on its own gameweek performance.
Write in first person as the agent, using its personality trait.

Max 180 chars. Tone matches personality:
  Quant: detached, analytical ("Expected value: delivered.")
  Degen: chaotic, no regrets ("Captained a 5% pick. It hit. Obviously.")
  Contrarian: smug or silently pleased
  Grinder: matter-of-fact ("GW done. Points banked. On to the next.")

Output ONLY the post text."""


def post_to_moltbook(agent_id: str, agent_name: str, personality: str,
                     gw_points: int, rank: int, cap_name: str, cap_pts: int) -> None:
    if not MOLTBOOK_KEY:
        log.warning(f"  Moltbook key not set — skipping profile post for {agent_name}")
        return

    prompt = f"""Agent: {agent_name}
Personality: {personality}
GW points: {gw_points}
Current rank: {rank}
Captain: {cap_name} ({cap_pts} pts)"""

    post_text = ask(MOLTBOOK_SYSTEM, prompt, max_tokens=80)

    # ── Moltbook API call (stub — update when docs received from Marcus) ──
    try:
        resp = httpx.post(
            f"https://api.moltbook.com/v1/agents/{agent_id}/posts",  # placeholder URL
            headers={"Authorization": f"Bearer {MOLTBOOK_KEY}", "Content-Type": "application/json"},
            json={"content": post_text, "type": "gameweek_recap"},
            timeout=15,
        )
        resp.raise_for_status()
        log.info(f"  Moltbook post sent for {agent_name}")
    except Exception as e:
        log.error(f"  Moltbook post failed for {agent_name}: {e}")


# ── Core: process a contest.scored event ─────────────────────────────────────

def process_contest(contest_id: str, contest_title: str = "", total_entrants: int = 0) -> None:
    log.info(f"Processing contest: {contest_id} — '{contest_title}'")

    if already_processed(contest_id):
        log.info(f"  Already processed — skipping")
        return

    # 1. Fetch results
    results = fetch_contest_results(contest_id)
    if not results:
        log.error(f"  No results returned for {contest_id}")
        return
    log.info(f"  {len(results)} agent results fetched")

    # 2. Fetch previous ranks for rank-change narrative
    agent_ids = [str(r["agent_id"]) for r in results]
    prev_ranks = get_previous_ranks(agent_ids)

    # 3. Save current ranks for next GW
    save_ranks(contest_id, results)

    # 4. Derive best narrative
    narrative = find_best_narrative(results, prev_ranks)
    log.info(f"  Narrative selected: {narrative['type']}")

    # 5. Fetch personality for the featured agent
    personality = None
    if narrative.get("agent_id"):
        perf = fetch_agent_performance(narrative["agent_id"])
        personality = perf.get("personality") or perf.get("agent_personality")

    # 6. Draft and post tweet
    tweet_text = draft_tweet(narrative, contest_title or f"Contest {contest_id}", personality)
    log.info(f"  Tweet: {tweet_text}")
    tweet_id = post_tweet(tweet_text)

    # 7. Moltbook posts for top 3 agents
    leaderboard = fetch_leaderboard(contest_id)
    top3 = leaderboard[:3] if leaderboard else results[:3]
    for entry in top3:
        aid = str(entry.get("agent_id", ""))
        aname = entry.get("agent_name", "")
        rank = entry.get("rank", 0)
        gw_pts = entry.get("gw_points") or _derive_gw_points(entry)
        perf = fetch_agent_performance(aid)
        p = perf.get("personality") or "Grinder"
        cap = get_captain(entry.get("scoring_breakdown") or [])
        post_to_moltbook(
            agent_id=aid, agent_name=aname, personality=p,
            gw_points=gw_pts, rank=rank,
            cap_name=cap.get("player_name", "") if cap else "",
            cap_pts=cap.get("points", 0) if cap else 0,
        )

    # 8. Log
    log_broadcast(contest_id, narrative["type"], tweet_text, tweet_id or "")
    log.info(f"  Broadcast complete for {contest_id}")


# ── Mode 1: SSE listener ──────────────────────────────────────────────────────

def run_sse_listener() -> None:
    """
    Connect to MCP gateway SSE stream and listen for contest.scored events.
    Recommended for production — run as an always-on service.
    """
    if not MCP_SSE_URL:
        log.error("MCP_GATEWAY_SSE_URL not set")
        return

    log.info(f"=== Connecting to MCP gateway SSE: {MCP_SSE_URL} ===")

    while True:
        try:
            with httpx.stream("GET", MCP_SSE_URL,
                              headers=_headers(), timeout=None) as stream:
                buffer = ""
                for line in stream.iter_lines():
                    line = line.strip()

                    if line.startswith("data:"):
                        buffer += line[5:].strip()
                    elif line == "" and buffer:
                        # End of SSE message — parse it
                        try:
                            event = json.loads(buffer)
                            _handle_sse_event(event)
                        except json.JSONDecodeError as e:
                            log.warning(f"SSE parse error: {e} — data: {buffer[:100]}")
                        buffer = ""
                    elif line.startswith("event:"):
                        pass  # event type line — data line follows

        except httpx.RemoteProtocolError as e:
            log.warning(f"SSE connection dropped: {e} — reconnecting in 10s")
            time.sleep(10)
        except Exception as e:
            log.error(f"SSE listener error: {e} — reconnecting in 30s")
            time.sleep(30)


def _handle_sse_event(event: dict) -> None:
    event_type = event.get("type") or event.get("event")

    if event_type != "contest.scored":
        return  # ignore other events

    payload = event.get("data") or event.get("payload") or event
    contest_id = str(payload.get("contest_id", ""))
    title = payload.get("title", "")
    total_entrants = payload.get("total_entrants", 0)

    if not contest_id:
        log.warning(f"contest.scored event missing contest_id: {payload}")
        return

    log.info(f"contest.scored received: {contest_id}")
    try:
        process_contest(contest_id, title, total_entrants)
    except Exception as e:
        log.error(f"Failed to process contest {contest_id}: {e}")


# ── Mode 2: Manual / single contest ──────────────────────────────────────────

def run_single(contest_id: str) -> None:
    ensure_broadcaster_table()
    log.info(f"=== Agent 1: Broadcaster — manual run for {contest_id} ===")
    process_contest(contest_id)
    log.info("=== Done ===")


# ── Mode 3: Poll for new scored contests ──────────────────────────────────────

def run_poll() -> None:
    """
    Cron fallback: call /v1/contests?status=SCORED, process any not yet logged.
    Use this if SSE is unavailable or for GitHub Actions cron.
    """
    ensure_broadcaster_table()
    log.info("=== Agent 1: Broadcaster — poll mode ===")
    try:
        data = api_get("/v1/contests?status=SCORED&limit=5")
        contests = data if isinstance(data, list) else data.get("contests", data.get("data", []))
    except Exception as e:
        log.error(f"Failed to fetch scored contests: {e}")
        return

    processed = 0
    for c in contests:
        cid = str(c.get("id") or c.get("contest_id", ""))
        if cid and not already_processed(cid):
            process_contest(cid, c.get("title", ""), c.get("total_entrants", 0))
            processed += 1

    log.info(f"=== Done. {processed} new contest(s) processed ===")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ensure_broadcaster_table()

    parser = argparse.ArgumentParser(description="Agent 1: The Broadcaster")
    parser.add_argument("--listen", action="store_true", help="SSE listener mode (production)")
    parser.add_argument("--poll", action="store_true", help="Poll for new scored contests (cron)")
    parser.add_argument("--contest-id", type=str, help="Process a specific contest by ID")
    args = parser.parse_args()

    if args.listen:
        run_sse_listener()
    elif args.poll:
        run_poll()
    elif args.contest_id:
        run_single(args.contest_id)
    else:
        # Default: poll mode
        run_poll()
