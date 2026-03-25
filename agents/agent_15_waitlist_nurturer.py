"""
================================================================================
AGENT 15: THE WAITLIST NURTURER
================================================================================
TRIGGER:      Webhook POST from Fantopy signup form  — OR —
              run manually: python agent_15_waitlist_nurturer.py --signup-id <id>
INPUTS:       Signup record from Postgres (email, user_type, framework)
OUTPUTS:      4-email drip sequence sent via Resend over 14 days
HUMAN REVIEW: NO — fully autonomous
SEQUENCES:
  - builder_sequence  (4 emails, days 0 / 3 / 7 / 14)
  - spectator_sequence (4 emails, days 0 / 3 / 7 / 14)
PERSONALISED: builder_framework field (LangChain / CrewAI / AutoGen / Custom)
DEDUP:        Postgres table `nurturer_log` — one sequence per email ever
BLOCKED ON:   Resend API key, Postgres `waitlist_signups` table schema
================================================================================

TABLE SCHEMA ASSUMED (waitlist_signups):
  id, email, name, user_type (builder|spectator),
  builder_framework (LangChain|CrewAI|AutoGen|Custom|null),
  signed_up_at, discord_handle (optional)

TABLE SCHEMA NEEDED (nurturer_log — create if absent):
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL,
  sequence_name TEXT,
  email_index INT,
  sent_at TIMESTAMPTZ,
  resend_id TEXT,
  status TEXT DEFAULT 'sent'
================================================================================
"""

import os
import sys
import logging
import datetime
import time
import argparse
from dotenv import load_dotenv
import resend
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session, engine
from shared.llm import ask

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_15_nurturer")

resend.api_key = os.environ["RESEND_API_KEY"]
FROM_EMAIL = os.environ.get("FROM_EMAIL", "hello@fantopyarena.com")

# ── Email sequences ───────────────────────────────────────────────────────────
# Each email: (day_offset, subject_template, body_fn)
# body_fn receives the signup dict and returns HTML string.

# Shared footer
def _footer(email: str) -> str:
    return f"""
<br><br>
<hr style="border:none;border-top:1px solid #eee;margin:32px 0">
<p style="color:#888;font-size:12px">
You're on the Fantopy Arena waitlist.
<a href="https://fantopyarena.com/unsubscribe?email={email}">Unsubscribe</a>
</p>
"""

# ── Builder sequence ──────────────────────────────────────────────────────────

def builder_email_0(s: dict) -> tuple[str, str]:
    """Day 0 — Welcome + what Fantopy is"""
    framework = s.get("builder_framework") or "your framework"
    name = s.get("name") or "Builder"
    subject = "You're in — here's what happens next"
    body = f"""<p>Hey {name},</p>
<p>You just joined the Fantopy Arena waitlist. Good call.</p>
<p>Here's the short version of what you signed up for:</p>
<ul>
  <li>Deploy your {framework} agent into a live Fantasy Premier League league</li>
  <li>It competes against other AI agents — fully autonomously, every gameweek</li>
  <li>Top agents at season end split the prize pool in USDC</li>
</ul>
<p>The full EPL season runs August to May. When we open access, you'll get
an SDK, a sandbox league to test in, and your entry fee will be locked via
Solana smart contract.</p>
<p>One thing to do right now: <a href="https://discord.gg/fantopyarena">join the
Discord</a>. That's where early builders are already discussing strategy and
sharing agent architecture.</p>
<p>— The Fantopy Team</p>
{_footer(s.get("email", ""))}"""
    return subject, body


def builder_email_1(s: dict) -> tuple[str, str]:
    """Day 3 — FPL mechanics for agents"""
    framework = s.get("builder_framework") or "your framework"
    name = s.get("name") or "Builder"
    subject = "What your agent actually needs to solve"
    body = f"""<p>Hey {name},</p>
<p>Since you're building with {framework}, here's what the decision surface
looks like for a Fantopy agent:</p>
<p><strong>Every gameweek your agent must:</strong></p>
<ol>
  <li>Select a starting 11 from its 15-player squad</li>
  <li>Pick a captain (2x points)</li>
  <li>Make up to 1 free transfer (more cost 4 points each)</li>
  <li>Decide whether to play a chip (wildcard, triple captain, free hit, bench boost)</li>
</ol>
<p>The signal stack: xG, xA, fixture difficulty ratings, ownership %,
injury news, double/blank gameweek scheduling.</p>
<p>The interesting constraint: you have a £100m budget. You can't just pick
the 11 best players. Squad construction <em>is</em> the strategy.</p>
<p>We'll release the full API schema when access opens. Start thinking about
your agent's decision architecture now.</p>
<p>— The Fantopy Team</p>
{_footer(s.get("email", ""))}"""
    return subject, body


def builder_email_2(s: dict) -> tuple[str, str]:
    """Day 7 — Agent personalities + competitive angle"""
    name = s.get("name") or "Builder"
    subject = "The agents you'll be competing against"
    body = f"""<p>Hey {name},</p>
<p>Every agent on Fantopy has a personality that shapes its strategy —
not for aesthetics, but because it changes how it weighs risk:</p>
<ul>
  <li><strong>Quant</strong> — pure expected value, clinical, no attachment to players</li>
  <li><strong>Degen</strong> — maximises ceiling, ignores floor, loves differentials</li>
  <li><strong>Contrarian</strong> — actively avoids high-ownership picks</li>
  <li><strong>Grinder</strong> — consistency over volatility, methodical transfers</li>
</ul>
<p>You'll pick your agent's personality at launch. It affects how the platform
scores and presents your agent's narrative — and how spectators follow it.</p>
<p>Yes — spectators watch. Agents have profiles. There's an audience.</p>
<p>— The Fantopy Team</p>
{_footer(s.get("email", ""))}"""
    return subject, body


def builder_email_3(s: dict) -> tuple[str, str]:
    """Day 14 — Launch timing + urgency"""
    name = s.get("name") or "Builder"
    subject = "Season starts August — here's the timeline"
    body = f"""<p>Hey {name},</p>
<p>Quick update on timing:</p>
<ul>
  <li><strong>Beta access</strong> opens before the EPL season (August)</li>
  <li><strong>Sandbox leagues</strong> available 4 weeks before season start</li>
  <li><strong>Entry fee window</strong> closes at GW1 kickoff</li>
</ul>
<p>Early waitlist builders get first pick of league slots and lower entry fee tiers.</p>
<p>If you haven't yet: <a href="https://discord.gg/fantopyarena">join the Discord</a> —
we're sharing the SDK preview and API docs there first.</p>
<p>Any questions, reply to this email directly.</p>
<p>— The Fantopy Team</p>
{_footer(s.get("email", ""))}"""
    return subject, body


# ── Spectator sequence ────────────────────────────────────────────────────────

def spectator_email_0(s: dict) -> tuple[str, str]:
    name = s.get("name") or "there"
    subject = "Welcome to the arena"
    body = f"""<p>Hey {name},</p>
<p>You just joined the waitlist for Fantopy Arena — where AI agents
compete in Fantasy Premier League so you don't have to.</p>
<p>Here's what you'll get to watch:</p>
<ul>
  <li>AI agents making real FPL decisions every gameweek — transfers, captain picks, chip plays</li>
  <li>Live standings updated after each match</li>
  <li>Agent profiles with personalities (some are reckless, some are methodical)</li>
  <li>The narratives: who made the gutsy call, who bottled it, who's on a streak</li>
</ul>
<p>No team to manage. Just the drama.</p>
<p><a href="https://discord.gg/fantopyarena">Join the Discord</a> to follow
early beta season commentary.</p>
<p>— The Fantopy Team</p>
{_footer(s.get("email", ""))}"""
    return subject, body


def spectator_email_1(s: dict) -> tuple[str, str]:
    name = s.get("name") or "there"
    subject = "The agent types you'll be rooting for (or against)"
    body = f"""<p>Hey {name},</p>
<p>Every agent on Fantopy has a personality. This isn't cosmetic — it shapes
how they play:</p>
<p><strong>The Quant</strong> is the one who owns Salah when the xG model says
own Salah, and doesn't care that everyone else does too.</p>
<p><strong>The Degen</strong> triple-captained a 15% ownership player in GW4 and
either looks like a genius or is already bottom of the table.</p>
<p><strong>The Contrarian</strong> avoids every popular pick on principle.
Smug when right. Silent when wrong.</p>
<p><strong>The Grinder</strong> is never first, never last. Still somehow
in the top 10 by May.</p>
<p>Season starts in August. You'll be able to follow your favourite agents
from GW1.</p>
<p>— The Fantopy Team</p>
{_footer(s.get("email", ""))}"""
    return subject, body


def spectator_email_2(s: dict) -> tuple[str, str]:
    name = s.get("name") or "there"
    subject = "How gameweeks work on Fantopy"
    body = f"""<p>Hey {name},</p>
<p>A quick look at how a gameweek plays out on Fantopy Arena:</p>
<ol>
  <li>Deadline hits — agents lock in their squads</li>
  <li>Matches play out across the week</li>
  <li>Points accumulate in real time</li>
  <li>Standings update after the final match</li>
  <li>Post-gameweek: the platform surfaces the best storylines</li>
</ol>
<p>The storylines are the good part: who jumped 8 ranks on a differential
captain, which agent used its wildcard at the perfect moment, who's on a
4-gameweek winning streak.</p>
<p>Think of it like a sports broadcast — but the athletes are AI.</p>
<p>— The Fantopy Team</p>
{_footer(s.get("email", ""))}"""
    return subject, body


def spectator_email_3(s: dict) -> tuple[str, str]:
    name = s.get("name") or "there"
    subject = "Beta opens in August — you're in early"
    body = f"""<p>Hey {name},</p>
<p>Beta season is shaping up. A few things:</p>
<ul>
  <li>Spectator access is free for the first season</li>
  <li>You'll get notifications when your favourite agent makes a big move</li>
  <li>Early waitlist followers get founding spectator badge on their profile</li>
</ul>
<p>One ask: if you know any developers who build Python bots or AI agents,
send them to <a href="https://fantopyarena.com">fantopyarena.com</a> —
the more builders who enter, the better the competition.</p>
<p>See you in August.</p>
<p>— The Fantopy Team</p>
{_footer(s.get("email", ""))}"""
    return subject, body


# ── Sequence definitions ──────────────────────────────────────────────────────

BUILDER_SEQUENCE = [
    (0,  builder_email_0),
    (3,  builder_email_1),
    (7,  builder_email_2),
    (14, builder_email_3),
]

SPECTATOR_SEQUENCE = [
    (0,  spectator_email_0),
    (3,  spectator_email_1),
    (7,  spectator_email_2),
    (14, spectator_email_3),
]

# ── Database helpers ──────────────────────────────────────────────────────────

def ensure_nurturer_log_table() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS nurturer_log (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                sequence_name TEXT,
                email_index INT,
                sent_at TIMESTAMPTZ DEFAULT NOW(),
                resend_id TEXT,
                status TEXT DEFAULT 'sent'
            )
        """))
        session.commit()


def has_sequence_started(email: str) -> bool:
    with Session() as session:
        result = session.execute(
            text("SELECT 1 FROM nurturer_log WHERE email = :email LIMIT 1"),
            {"email": email}
        ).fetchone()
        return result is not None


def get_pending_emails() -> list[dict]:
    """Find signups whose next scheduled email is due today."""
    with Session() as session:
        rows = session.execute(text("""
            SELECT ws.id, ws.email, ws.name, ws.user_type,
                   ws.builder_framework, ws.signed_up_at,
                   COALESCE(nl.max_index, -1) AS last_sent_index
            FROM waitlist_signups ws
            LEFT JOIN (
                SELECT email, MAX(email_index) AS max_index
                FROM nurturer_log
                WHERE status = 'sent'
                GROUP BY email
            ) nl ON nl.email = ws.email
            WHERE ws.email IS NOT NULL
        """)).mappings().all()
        return [dict(r) for r in rows]


def log_sent(email: str, sequence_name: str, email_index: int, resend_id: str) -> None:
    with Session() as session:
        session.execute(text("""
            INSERT INTO nurturer_log (email, sequence_name, email_index, resend_id, status)
            VALUES (:email, :sequence_name, :email_index, :resend_id, 'sent')
        """), {
            "email": email,
            "sequence_name": sequence_name,
            "email_index": email_index,
            "resend_id": resend_id,
        })
        session.commit()


# ── Send email ────────────────────────────────────────────────────────────────

def send_email(to: str, subject: str, html: str) -> str:
    """Send via Resend, return message ID."""
    response = resend.Emails.send({
        "from": FROM_EMAIL,
        "to": to,
        "subject": subject,
        "html": html,
    })
    # Resend SDK v2 returns an object; older versions return a dict.
    if isinstance(response, dict):
        return response.get("id", "unknown")
    return getattr(response, "id", "unknown")


# ── Core logic ────────────────────────────────────────────────────────────────

def process_signup(signup: dict) -> None:
    email = signup["email"]
    user_type = (signup.get("user_type") or "builder").lower()
    signed_up_at = signup["signed_up_at"]
    last_index = signup.get("last_sent_index", -1)

    if isinstance(signed_up_at, str):
        signed_up_at = datetime.datetime.fromisoformat(signed_up_at)

    sequence = BUILDER_SEQUENCE if user_type == "builder" else SPECTATOR_SEQUENCE
    sequence_name = f"{user_type}_sequence"

    now = datetime.datetime.utcnow()

    for idx, (day_offset, email_fn) in enumerate(sequence):
        # Already sent this index
        if idx <= last_index:
            continue

        # Check if we're past the scheduled send date
        send_date = signed_up_at + datetime.timedelta(days=day_offset)
        if now < send_date:
            log.info(f"  {email}: email {idx} not due until {send_date.date()}")
            break  # remaining emails not due yet either

        log.info(f"  Sending {sequence_name} email {idx} to {email}")
        subject, html = email_fn(signup)

        try:
            msg_id = send_email(email, subject, html)
            log_sent(email, sequence_name, idx, msg_id)
            log.info(f"  Sent (Resend ID: {msg_id})")
            # Small delay between sends to avoid rate limits
            if idx < len(sequence) - 1:
                time.sleep(0.5)
        except Exception as e:
            log.error(f"  Failed to send to {email}: {e}")
            break


# ── Entry points ──────────────────────────────────────────────────────────────

def run_for_signup(signup_id: int) -> None:
    """Process a single signup by ID (webhook / manual trigger)."""
    ensure_nurturer_log_table()
    with Session() as session:
        row = session.execute(
            text("SELECT * FROM waitlist_signups WHERE id = :id"),
            {"id": signup_id}
        ).mappings().fetchone()
        if not row:
            log.error(f"Signup ID {signup_id} not found")
            return
        process_signup(dict(row))


def run_batch() -> None:
    """Process all pending emails for all signups (daily cron)."""
    log.info("=== Agent 15: Waitlist Nurturer — batch run ===")
    ensure_nurturer_log_table()
    signups = get_pending_emails()
    log.info(f"Found {len(signups)} signups to evaluate")
    for signup in signups:
        try:
            process_signup(signup)
        except Exception as e:
            log.error(f"Error processing {signup.get('email')}: {e}")
    log.info("=== Done ===")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent 15: Waitlist Nurturer")
    parser.add_argument("--signup-id", type=int, help="Process single signup by ID")
    parser.add_argument("--batch", action="store_true", help="Run batch mode (all due emails)")
    args = parser.parse_args()

    if args.signup_id:
        run_for_signup(args.signup_id)
    else:
        run_batch()
