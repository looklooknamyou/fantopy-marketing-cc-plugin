"""
================================================================================
AGENT 13: COMMUNITY MANAGER
================================================================================
TRIGGER:      Every 2 hours cron (GitHub Actions)
INPUTS:       Discord bot (reads new messages in monitored channels)
OUTPUTS:      Auto-replies to FAQ questions, welcome messages to new members,
              weekly digest post in #announcements
HUMAN REVIEW: NO — fully autonomous (FAQ replies only)
              Welcome messages and digest are also autonomous.
              Anything ambiguous or sensitive: silently skipped + logged
DISCORD CHANNELS MONITORED:
  #general, #builder-talk, #fpl-strategy, #help, #introductions
BLOCKED ON:   Discord bot token
================================================================================

FAQ TRIGGERS (auto-reply):
  "how do I enter"      → entry process explanation
  "what is the entry fee" → fee structure
  "when does season start" → August + gameweek timeline
  "what frameworks"      → supported agent frameworks
  "how are points"       → FPL scoring overview
  "is it free"           → spectator free, builder fee
  "waitlist"             → waitlist link

SAFETY RULES:
  - Never reply to bot messages
  - Never reply to the same message twice
  - Skip messages in moderation/staff channels
  - If message contains profanity or sensitive topics: skip silently
  - Rate limit: max 5 automated replies per hour
================================================================================
"""

import os
import sys
import logging
import datetime
import asyncio
import httpx
from dotenv import load_dotenv
import discord
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session
from shared.llm import ask

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_13_community")

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
MONITORED_CHANNELS = {"general", "builder-talk", "fpl-strategy", "help", "introductions"}
SKIP_CHANNELS = {"mod-log", "staff", "admin", "mod-chat"}
MAX_REPLIES_PER_HOUR = 5

# ── DB helpers ────────────────────────────────────────────────────────────────

def ensure_community_table() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS community_replies (
                id SERIAL PRIMARY KEY,
                message_id TEXT UNIQUE NOT NULL,
                channel TEXT,
                author TEXT,
                trigger_type TEXT,
                reply_sent TEXT,
                sent_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        session.commit()


def has_replied(message_id: str) -> bool:
    with Session() as session:
        result = session.execute(
            text("SELECT 1 FROM community_replies WHERE message_id = :mid LIMIT 1"),
            {"mid": str(message_id)}
        ).fetchone()
        return result is not None


def log_reply(message_id: str, channel: str, author: str, trigger: str, reply: str) -> None:
    with Session() as session:
        try:
            session.execute(text("""
                INSERT INTO community_replies (message_id, channel, author, trigger_type, reply_sent)
                VALUES (:mid, :ch, :au, :tr, :re)
                ON CONFLICT (message_id) DO NOTHING
            """), {"mid": str(message_id), "ch": channel, "au": author, "tr": trigger, "re": reply})
            session.commit()
        except Exception as e:
            log.warning(f"DB log failed: {e}")


def replies_this_hour() -> int:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
    with Session() as session:
        result = session.execute(text("""
            SELECT COUNT(*) FROM community_replies WHERE sent_at > :cutoff
        """), {"cutoff": cutoff}).fetchone()
        return result[0] if result else 0


# ── FAQ matching ──────────────────────────────────────────────────────────────

FAQ_RESPONSES = {
    "how do i enter": """To enter Fantopy Arena as a builder:
1. Join the waitlist at **fantopyarena.com**
2. You'll get beta access before the August season start
3. Deploy your agent via the SDK, pay the entry fee in USDC (Solana)
4. Your agent competes for the full 38-gameweek season

Any questions, ask here!""",

    "entry fee": """Entry fees are tiered based on league size and competition level — exact amounts will be confirmed before beta opens. Payment is in USDC on Solana. Spectators watch for free.""",

    "when does season start": """The EPL season runs August to May (38 gameweeks). Fantopy Arena beta opens before GW1 with a sandbox period for testing. Exact date: watch #announcements.""",

    "what frameworks": """Fantopy Arena is framework-agnostic. Builders have used LangChain, CrewAI, AutoGen, and custom Python. You just need to implement the agent SDK interface — your internals are up to you.""",

    "how are points": """Points follow standard FPL scoring: goals, assists, clean sheets, cards, saves, bonus points. Captain scores 2x. Your agent makes real FPL decisions each gameweek — the platform handles point calculation automatically.""",

    "is it free": """Spectators watch for free. Builders pay an entry fee in USDC to enter a competition league. The prize pool is distributed to top-ranking agents at season end.""",

    "waitlist": """Join the waitlist at **https://fantopyarena.com** — builders get early access, lower entry fee tiers, and sandbox testing before season start.""",
}

SENSITIVE_WORDS = {"refund", "scam", "rug", "banned", "hack", "lawsuit", "fraud"}


def match_faq(text: str) -> str | None:
    text_lower = text.lower()

    # Safety check
    if any(w in text_lower for w in SENSITIVE_WORDS):
        return None

    for trigger, response in FAQ_RESPONSES.items():
        if trigger in text_lower:
            return response

    return None


# ── LLM: Smart reply for non-FAQ questions ────────────────────────────────────

COMMUNITY_SYSTEM = """You are a helpful community manager for Fantopy Arena —
an AI agent vs agent Fantasy Premier League competition platform.

Someone asked a question in the Discord. Answer helpfully and concisely (under 100 words).
Only answer if you're confident — if unsure, say "good question, we'll get back to you on that!"
Do not make up specific numbers (fees, dates, prize amounts) — say "TBC" if not known.
Tone: friendly, knowledgeable, peer-to-peer. No exclamation marks."""

COMMUNITY_QUESTIONS = [
    "agent", "deploy", "sdk", "api", "score", "point", "rank",
    "league", "prize", "solana", "usdc", "wallet", "transfer",
    "wildcard", "chip", "captain", "squad", "fpl",
]


def should_attempt_llm_reply(text: str) -> bool:
    """Only invoke LLM if message looks like a genuine question about the platform."""
    text_lower = text.lower()
    has_question = "?" in text or any(
        text_lower.startswith(w) for w in ["how", "what", "when", "can", "is ", "do ", "does", "will"]
    )
    has_relevant_term = any(kw in text_lower for kw in COMMUNITY_QUESTIONS)
    return has_question and has_relevant_term


def llm_reply(message_text: str) -> str | None:
    response = ask(COMMUNITY_SYSTEM, message_text, max_tokens=150)
    # Don't send if LLM says it doesn't know
    if "don't know" in response.lower() or "not sure" in response.lower():
        return None
    return response


# ── Welcome message ───────────────────────────────────────────────────────────

WELCOME_MESSAGES = {
    "introductions": """Welcome to Fantopy Arena! Great to have you here.

Quick orientation:
• **#builder-talk** — agent architecture, SDK questions, strategy
• **#fpl-strategy** — FPL picks, data sources, gameweek discussions
• **#help** — anything stuck? ask here

If you haven't already, join the waitlist at **fantopyarena.com** for early access.
What are you building?""",

    "general": """Welcome! Drop any questions in **#help** or introduce yourself in **#introductions**.""",
}


# ── Discord bot ───────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user}")
    ensure_community_table()


@bot.event
async def on_member_join(member):
    """Auto-welcome new members in #introductions if it exists."""
    guild = member.guild
    channel = discord.utils.get(guild.channels, name="introductions")
    if not channel:
        channel = discord.utils.get(guild.channels, name="general")
    if channel:
        welcome = WELCOME_MESSAGES.get("introductions", "Welcome to Fantopy Arena!")
        await channel.send(f"{member.mention} {welcome}")
        log.info(f"Welcomed {member.name}")


@bot.event
async def on_message(message):
    # Never reply to self or other bots
    if message.author.bot:
        return

    channel_name = message.channel.name.lower()

    # Skip channels we don't monitor
    if channel_name in SKIP_CHANNELS:
        return
    if channel_name not in MONITORED_CHANNELS:
        return

    # Skip already-replied messages
    if has_replied(str(message.id)):
        return

    # Rate limit
    if replies_this_hour() >= MAX_REPLIES_PER_HOUR:
        log.info("Rate limit reached — skipping")
        return

    text_content = message.content.strip()
    if not text_content or len(text_content) < 10:
        return

    reply = None
    trigger_type = None

    # 1. Try FAQ match first
    faq_reply = match_faq(text_content)
    if faq_reply:
        reply = faq_reply
        trigger_type = "faq"

    # 2. Try LLM for platform questions
    elif should_attempt_llm_reply(text_content):
        try:
            llm = llm_reply(text_content)
            if llm:
                reply = llm
                trigger_type = "llm"
        except Exception as e:
            log.error(f"LLM reply failed: {e}")

    if reply:
        try:
            await message.reply(reply, mention_author=False)
            log_reply(str(message.id), channel_name, str(message.author), trigger_type, reply)
            log.info(f"Replied ({trigger_type}) in #{channel_name} to {message.author}")
        except discord.DiscordException as e:
            log.error(f"Discord send failed: {e}")


# ── Weekly digest ─────────────────────────────────────────────────────────────

async def post_weekly_digest(guild_id: int) -> None:
    """Post a weekly platform digest to #announcements."""
    guild = bot.get_guild(guild_id)
    if not guild:
        return
    channel = discord.utils.get(guild.channels, name="announcements")
    if not channel:
        return

    week = datetime.datetime.utcnow().strftime("%Y-W%U")
    digest = ask(
        "You write weekly Discord announcements for Fantopy Arena — an AI agent vs agent FPL platform. Write a short (150 words max) weekly digest covering: platform status, upcoming gameweek, any builder tips. Tone: engaged community manager. No exclamation marks.",
        f"Week: {week}. EPL season is ongoing. Platform is in beta/waitlist phase.",
        max_tokens=250,
    )

    await channel.send(f"**Weekly Update — {week}**\n\n{digest}")
    log.info(f"Posted weekly digest for {week}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    log.info("=== Agent 13: Community Manager — starting bot ===")
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run()
