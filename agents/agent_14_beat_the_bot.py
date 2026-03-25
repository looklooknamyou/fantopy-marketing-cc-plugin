"""
================================================================================
AGENT 14: BEAT THE BOT COORDINATOR
================================================================================
TRIGGER:      1. Cron: 2h before each GW deadline (reminder emails)
              2. Cron: After GW finalises (results + content)
              3. Manual: python agent_14_beat_the_bot.py --register <email> <fpl_id> <agent_id>
INPUTS:       FPL public API (human scores), Fantopy API (agent scores),
              Postgres challenge_participants table
OUTPUTS:      Pre-GW reminder emails/Discord posts
              Post-GW results → Discord announcement + tweet draft → Sheets queue
              Weekly leaderboard update
HUMAN REVIEW: Results tweet goes to Sheets queue for approval before posting
              Email reminders are fully autonomous
BLOCKED ON:   FANTOPY_API_KEY (agent scores), RESEND_API_KEY (emails),
              DISCORD_WEBHOOK_URL
FPL API:      Public, no auth needed.
              Entry history: https://fantasy.premierleague.com/api/entry/{id}/history/
              Bootstrap: https://fantasy.premierleague.com/api/bootstrap-static/
================================================================================

BEAT THE BOT DESIGN:
  - Humans register their FPL manager ID + choose which Fantopy agent to challenge
  - Each gameweek: human score vs agent score fetched automatically
  - Win/loss/draw logged per gameweek per participant
  - Season leaderboard: % of GWs beaten
  - Milestone celebrations: "First human to beat 3 agents in a row"
  - Generates content: results summary for Discord + tweet for review

TABLE: challenge_participants
  id, email, name, fpl_entry_id, target_agent_id, target_agent_name,
  discord_handle, joined_at, active

TABLE: challenge_results
  id, participant_id, gameweek, human_points, agent_points,
  outcome (WIN|LOSS|DRAW), recorded_at
================================================================================
"""

import os
import sys
import logging
import datetime
import argparse
import httpx
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session
from shared.sheets import append_to_queue, get_sheet
from shared.llm import ask

import resend
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_14_beat_the_bot")

FANTOPY_BASE  = os.environ.get("FANTOPY_API_BASE_URL", "").rstrip("/")
FANTOPY_KEY   = os.environ.get("FANTOPY_API_KEY", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
SHEET_ID      = os.environ.get("RECRUITER_SHEET_ID", "")
FROM_EMAIL    = os.environ.get("FROM_EMAIL", "hello@fantopyarena.com")
FPL_BASE      = "https://fantasy.premierleague.com/api"

resend.api_key = os.environ.get("RESEND_API_KEY", "")

# ── DB setup ──────────────────────────────────────────────────────────────────

def ensure_tables() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS challenge_participants (
                id               SERIAL PRIMARY KEY,
                email            TEXT NOT NULL UNIQUE,
                name             TEXT,
                fpl_entry_id     INT NOT NULL,
                target_agent_id  TEXT NOT NULL,
                target_agent_name TEXT,
                discord_handle   TEXT,
                joined_at        TIMESTAMPTZ DEFAULT NOW(),
                active           BOOLEAN DEFAULT TRUE
            )
        """))
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS challenge_results (
                id              SERIAL PRIMARY KEY,
                participant_id  INT NOT NULL REFERENCES challenge_participants(id),
                gameweek        INT NOT NULL,
                human_points    INT,
                agent_points    INT,
                outcome         TEXT,   -- WIN | LOSS | DRAW
                recorded_at     TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (participant_id, gameweek)
            )
        """))
        session.commit()


def register_participant(email: str, name: str, fpl_entry_id: int,
                         target_agent_id: str, target_agent_name: str = "",
                         discord_handle: str = "") -> None:
    with Session() as session:
        session.execute(text("""
            INSERT INTO challenge_participants
              (email, name, fpl_entry_id, target_agent_id, target_agent_name, discord_handle)
            VALUES (:email, :name, :fpl_id, :agent_id, :agent_name, :discord)
            ON CONFLICT (email) DO UPDATE SET
              fpl_entry_id = EXCLUDED.fpl_entry_id,
              target_agent_id = EXCLUDED.target_agent_id,
              active = TRUE
        """), {
            "email": email, "name": name, "fpl_id": fpl_entry_id,
            "agent_id": target_agent_id, "agent_name": target_agent_name,
            "discord": discord_handle,
        })
        session.commit()
    log.info(f"Registered: {email} challenging agent {target_agent_id}")


def get_active_participants() -> list[dict]:
    with Session() as session:
        rows = session.execute(text("""
            SELECT * FROM challenge_participants WHERE active = TRUE
        """)).mappings().all()
        return [dict(r) for r in rows]


def already_recorded(participant_id: int, gameweek: int) -> bool:
    with Session() as session:
        return session.execute(text("""
            SELECT 1 FROM challenge_results
            WHERE participant_id = :pid AND gameweek = :gw LIMIT 1
        """), {"pid": participant_id, "gw": gameweek}).fetchone() is not None


def save_result(participant_id: int, gameweek: int,
                human_pts: int, agent_pts: int, outcome: str) -> None:
    with Session() as session:
        session.execute(text("""
            INSERT INTO challenge_results (participant_id, gameweek, human_points, agent_points, outcome)
            VALUES (:pid, :gw, :hp, :ap, :oc)
            ON CONFLICT (participant_id, gameweek) DO NOTHING
        """), {"pid": participant_id, "gw": gameweek,
               "hp": human_pts, "ap": agent_pts, "oc": outcome})
        session.commit()


def get_season_record(participant_id: int) -> dict:
    with Session() as session:
        row = session.execute(text("""
            SELECT
              COUNT(*) AS played,
              SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) AS wins,
              SUM(CASE WHEN outcome='LOSS' THEN 1 ELSE 0 END) AS losses,
              SUM(CASE WHEN outcome='DRAW' THEN 1 ELSE 0 END) AS draws
            FROM challenge_results
            WHERE participant_id = :pid
        """), {"pid": participant_id}).mappings().fetchone()
        return dict(row) if row else {"played": 0, "wins": 0, "losses": 0, "draws": 0}


# ── FPL API ───────────────────────────────────────────────────────────────────

def get_current_gameweek() -> int:
    resp = httpx.get(f"{FPL_BASE}/bootstrap-static/", timeout=15)
    resp.raise_for_status()
    events = resp.json().get("events", [])
    for e in events:
        if e.get("is_current"):
            return e["id"]
    # Fallback: last finished
    finished = [e for e in events if e.get("finished")]
    return finished[-1]["id"] if finished else 1


def get_fpl_gw_points(fpl_entry_id: int, gameweek: int) -> int | None:
    try:
        resp = httpx.get(f"{FPL_BASE}/entry/{fpl_entry_id}/history/", timeout=15)
        resp.raise_for_status()
        history = resp.json().get("current", [])
        for gw in history:
            if gw["event"] == gameweek:
                return gw["points"] - gw.get("event_transfers_cost", 0)
        return None
    except Exception as e:
        log.error(f"FPL API error for entry {fpl_entry_id}: {e}")
        return None


def get_fpl_manager_name(fpl_entry_id: int) -> str:
    try:
        resp = httpx.get(f"{FPL_BASE}/entry/{fpl_entry_id}/", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return f"{data.get('player_first_name','')} {data.get('player_last_name','')}".strip()
    except Exception:
        return f"FPL#{fpl_entry_id}"


# ── Fantopy API ───────────────────────────────────────────────────────────────

def get_agent_gw_points(agent_id: str, contest_id: str | None = None) -> int | None:
    if not FANTOPY_KEY or not FANTOPY_BASE:
        log.warning("Fantopy API not configured — agent points unavailable")
        return None
    try:
        if contest_id:
            resp = httpx.get(
                f"{FANTOPY_BASE}/v1/contests/{contest_id}/results",
                headers={"Authorization": f"Bearer {FANTOPY_KEY}"},
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json()
            if isinstance(results, dict):
                results = results.get("results", results.get("data", []))
            for r in results:
                if str(r.get("agent_id")) == str(agent_id):
                    pts = r.get("gw_points")
                    if pts is None:
                        breakdown = r.get("scoring_breakdown") or []
                        pts = sum(p.get("points", 0) for p in breakdown)
                    return pts
        # Fallback: performance endpoint
        resp = httpx.get(
            f"{FANTOPY_BASE}/v1/agents/{agent_id}/performance",
            headers={"Authorization": f"Bearer {FANTOPY_KEY}"},
            timeout=15,
        )
        resp.raise_for_status()
        perf = resp.json()
        history = perf.get("gameweek_history") or perf.get("history") or []
        gw = get_current_gameweek()
        for entry in history:
            if entry.get("gameweek") == gw or entry.get("event") == gw:
                return entry.get("points")
        return None
    except Exception as e:
        log.error(f"Fantopy API error for agent {agent_id}: {e}")
        return None


# ── Emails ────────────────────────────────────────────────────────────────────

def send_reminder_email(participant: dict, gameweek: int, deadline_str: str) -> None:
    name = participant.get("name") or "there"
    agent_name = participant.get("target_agent_name") or f"Agent #{participant['target_agent_id']}"
    subject = f"GW{gameweek} starts soon — {agent_name} is ready. Are you?"
    html = f"""<p>Hey {name},</p>
<p>Gameweek {gameweek} deadline is <strong>{deadline_str}</strong>.</p>
<p>You're challenging <strong>{agent_name}</strong> this week.
It has already locked in its squad. Make sure yours is set.</p>
<p>Check your FPL team → <a href="https://fantasy.premierleague.com">fantasy.premierleague.com</a></p>
<p>Results posted on Discord after the gameweek finalises.</p>
<p>— Fantopy Arena</p>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0">
<p style="color:#888;font-size:12px">
<a href="https://fantopyarena.com/unsubscribe">Unsubscribe</a>
</p>"""
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": participant["email"],
            "subject": subject,
            "html": html,
        })
        log.info(f"  Reminder sent to {participant['email']}")
    except Exception as e:
        log.error(f"  Reminder failed for {participant['email']}: {e}")


def send_result_email(participant: dict, gameweek: int,
                      human_pts: int, agent_pts: int, outcome: str,
                      record: dict) -> None:
    name = participant.get("name") or "there"
    agent_name = participant.get("target_agent_name") or "the agent"
    outcome_line = {
        "WIN":  f"You beat {agent_name} this week. {human_pts} vs {agent_pts}.",
        "LOSS": f"{agent_name} beat you this week. {agent_pts} vs {human_pts}.",
        "DRAW": f"It's a draw. Both you and {agent_name} scored {human_pts} points.",
    }[outcome]
    subject_map = {
        "WIN": f"GW{gameweek}: You won. {human_pts} vs {agent_pts}",
        "LOSS": f"GW{gameweek}: {agent_name} wins. {agent_pts} vs {human_pts}",
        "DRAW": f"GW{gameweek}: Draw. {human_pts} all.",
    }
    season_line = f"Season record: {record['wins']}W / {record['losses']}L / {record['draws']}D"
    html = f"""<p>Hey {name},</p>
<p><strong>GW{gameweek} result:</strong> {outcome_line}</p>
<p>{season_line}</p>
<p>See the full leaderboard on <a href="https://discord.gg/fantopyarena">Discord</a>.</p>
<p>— Fantopy Arena</p>"""
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": participant["email"],
            "subject": subject_map[outcome],
            "html": html,
        })
        log.info(f"  Result email sent to {participant['email']}")
    except Exception as e:
        log.error(f"  Result email failed: {e}")


# ── Discord announcements ─────────────────────────────────────────────────────

def post_to_discord(message: str) -> None:
    if not DISCORD_WEBHOOK:
        return
    try:
        httpx.post(DISCORD_WEBHOOK, json={"content": message}, timeout=10).raise_for_status()
    except Exception as e:
        log.error(f"Discord post failed: {e}")


# ── Content generation ────────────────────────────────────────────────────────

RESULTS_SUMMARY_SYSTEM = """You write Discord announcements for Fantopy Arena's
Beat the Bot challenge — where humans compete against AI agents in Fantasy Premier League.

Write a short announcement (max 200 words) summarising the gameweek results.
Tone: excited sports commentator, but dry and direct. No exclamation marks.
Include wins, losses, standout moments. Make it feel like a live score update.
Output ONLY the announcement text."""

TWEET_SYSTEM = """Write a tweet (max 240 chars) for @fantopyarena about the
Beat the Bot challenge results. Sharp, specific, sports-broadcast tone.
No hashtags except #FPL. No exclamation marks. Output ONLY the tweet text."""


def generate_results_content(gameweek: int, results: list[dict]) -> tuple[str, str]:
    wins  = [r for r in results if r["outcome"] == "WIN"]
    losses = [r for r in results if r["outcome"] == "LOSS"]
    draws  = [r for r in results if r["outcome"] == "DRAW"]

    context = f"""GW{gameweek} Beat the Bot results:
Total participants: {len(results)}
Human wins: {len(wins)} | Agent wins: {len(losses)} | Draws: {len(draws)}

Individual results:
{chr(10).join(f"- {r['name']} ({r['human_pts']}pts) vs {r['agent_name']} ({r['agent_pts']}pts) → {r['outcome']}" for r in results[:10])}"""

    discord_msg = ask(RESULTS_SUMMARY_SYSTEM, context, max_tokens=300)
    tweet = ask(TWEET_SYSTEM, context, max_tokens=100)
    return discord_msg, tweet


# ── Core flows ────────────────────────────────────────────────────────────────

def run_reminders(gameweek: int, deadline_str: str) -> None:
    log.info(f"=== Agent 14: Sending GW{gameweek} reminders ===")
    participants = get_active_participants()
    log.info(f"  {len(participants)} active participants")
    for p in participants:
        send_reminder_email(p, gameweek, deadline_str)


def run_results(gameweek: int, contest_id: str | None = None) -> None:
    log.info(f"=== Agent 14: Processing GW{gameweek} results ===")
    participants = get_active_participants()
    processed_results = []

    for p in participants:
        pid = p["id"]
        if already_recorded(pid, gameweek):
            log.info(f"  Already recorded: {p['email']} GW{gameweek}")
            continue

        human_pts = get_fpl_gw_points(p["fpl_entry_id"], gameweek)
        agent_pts = get_agent_gw_points(p["target_agent_id"], contest_id)

        if human_pts is None or agent_pts is None:
            log.warning(f"  Missing scores for {p['email']} — human:{human_pts} agent:{agent_pts}")
            continue

        if human_pts > agent_pts:
            outcome = "WIN"
        elif agent_pts > human_pts:
            outcome = "LOSS"
        else:
            outcome = "DRAW"

        save_result(pid, gameweek, human_pts, agent_pts, outcome)
        record = get_season_record(pid)
        send_result_email(p, gameweek, human_pts, agent_pts, outcome, record)

        processed_results.append({
            "name": p.get("name", p["email"]),
            "agent_name": p.get("target_agent_name", p["target_agent_id"]),
            "human_pts": human_pts, "agent_pts": agent_pts, "outcome": outcome,
        })
        log.info(f"  {p['email']}: {human_pts} vs {agent_pts} → {outcome}")

    if not processed_results:
        log.info("  No new results to process")
        return

    # Generate and post Discord announcement
    discord_msg, tweet_draft = generate_results_content(gameweek, processed_results)
    post_to_discord(f"**Beat the Bot — GW{gameweek} Results**\n\n{discord_msg}")

    # Queue tweet for human review
    if SHEET_ID:
        try:
            ws = get_sheet(SHEET_ID, "BeatTheBotTweets")
            headers = ["timestamp", "gameweek", "tweet_draft", "status", "notes"]
            if ws.row_count == 0 or not ws.row_values(1):
                ws.insert_row(headers, 1)
            append_to_queue(SHEET_ID, [
                datetime.datetime.utcnow().isoformat(),
                gameweek, tweet_draft, "PENDING", ""
            ], worksheet_name="BeatTheBotTweets")
            log.info(f"  Tweet draft queued in Sheets")
        except Exception as e:
            log.error(f"  Sheets queue failed: {e}")
            log.info(f"  Tweet draft: {tweet_draft}")

    log.info(f"=== Done. {len(processed_results)} results processed ===")


def run_leaderboard_post() -> None:
    """Weekly Discord post: full season leaderboard."""
    with Session() as session:
        rows = session.execute(text("""
            SELECT
              cp.name, cp.target_agent_name,
              COUNT(*) AS played,
              SUM(CASE WHEN cr.outcome='WIN' THEN 1 ELSE 0 END) AS wins,
              SUM(CASE WHEN cr.outcome='LOSS' THEN 1 ELSE 0 END) AS losses,
              ROUND(100.0 * SUM(CASE WHEN cr.outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_pct
            FROM challenge_participants cp
            JOIN challenge_results cr ON cr.participant_id = cp.id
            WHERE cp.active = TRUE
            GROUP BY cp.id, cp.name, cp.target_agent_name
            ORDER BY win_pct DESC, wins DESC
            LIMIT 10
        """)).mappings().all()

    if not rows:
        return

    lines = ["**Beat the Bot — Season Leaderboard**\n"]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"{i}. {r['name']} vs {r['target_agent_name']} — "
            f"{r['wins']}W/{r['losses']}L ({r['win_pct']}%)"
        )
    post_to_discord("\n".join(lines))


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ensure_tables()

    parser = argparse.ArgumentParser(description="Agent 14: Beat the Bot")
    parser.add_argument("--reminders", action="store_true", help="Send GW reminders")
    parser.add_argument("--results", action="store_true", help="Process GW results")
    parser.add_argument("--leaderboard", action="store_true", help="Post season leaderboard")
    parser.add_argument("--register", nargs=4,
                        metavar=("EMAIL", "NAME", "FPL_ID", "AGENT_ID"),
                        help="Register a participant")
    parser.add_argument("--gameweek", type=int, help="Gameweek number (default: current)")
    parser.add_argument("--deadline", type=str, default="", help="Deadline string for reminders")
    parser.add_argument("--contest-id", type=str, help="Fantopy contest ID for this GW")
    args = parser.parse_args()

    if args.register:
        email, name, fpl_id, agent_id = args.register
        register_participant(email, name, int(fpl_id), agent_id)

    elif args.reminders:
        gw = args.gameweek or get_current_gameweek()
        run_reminders(gw, args.deadline or f"GW{gw} deadline")

    elif args.results:
        gw = args.gameweek or get_current_gameweek()
        run_results(gw, args.contest_id)

    elif args.leaderboard:
        run_leaderboard_post()

    else:
        parser.print_help()
