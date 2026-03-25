"""
Shared database utilities for all marketing agents.
Uses SQLAlchemy with the existing Fantopy Postgres instance.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

_db_url = os.environ.get("DATABASE_URL", "")
if not _db_url:
    raise RuntimeError("DATABASE_URL is not set. See CREDENTIALS.md for format.")

engine = create_engine(_db_url, pool_pre_ping=True)
Session = sessionmaker(bind=engine)

# Allowlist: only these tables may be used via has_been_contacted / log_contact.
# Prevents accidental or malicious table/column injection.
_ALLOWED_TABLES = {
    "recruiter_prospects",
    "nurturer_log",
    "intel_log",
    "scout_replied",
    "content_topics",
    "content_log",
    "community_replies",
    "referral_codes",
    "referral_payouts",
    "broadcaster_history",
    "broadcaster_log",
    "challenge_participants",
    "challenge_results",
    "seo_log",
    "reddit_drafts",
    "partnership_log",
    "influencer_log",
    "milestone_log",
    "press_log",
    "waitlist_signups",
}

_ALLOWED_COLS = {
    "github_username", "twitter_handle", "email", "url",
    "platform_id", "keyword", "code",
}


def _validate(table: str, col: str | None = None) -> None:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Table '{table}' not in allowlist.")
    if col is not None and col not in _ALLOWED_COLS:
        raise ValueError(f"Column '{col}' not in allowlist.")


def has_been_contacted(table: str, identifier_col: str, identifier_val: str) -> bool:
    """Deduplication check — returns True if already in the outreach log."""
    _validate(table, identifier_col)
    with Session() as session:
        result = session.execute(
            text(f"SELECT 1 FROM {table} WHERE {identifier_col} = :val LIMIT 1"),
            {"val": identifier_val},
        ).fetchone()
        return result is not None


def log_contact(table: str, data: dict) -> None:
    """Insert a row into an outreach log table."""
    _validate(table)
    with Session() as session:
        cols = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        session.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"), data)
        session.commit()
