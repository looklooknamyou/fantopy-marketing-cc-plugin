"""
Creates all marketing agent tables in the existing Fantopy Postgres instance.
Run once: python db/create_tables.py

Safe to re-run — all statements use CREATE TABLE IF NOT EXISTS.
Does NOT touch existing platform tables.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from sqlalchemy import text
from shared.db import Session, engine

load_dotenv()

TABLES = {

    # ── Agent 3: Recruiter ────────────────────────────────────────────────
    "recruiter_prospects": """
        CREATE TABLE IF NOT EXISTS recruiter_prospects (
            id                  SERIAL PRIMARY KEY,
            github_username     TEXT,
            twitter_handle      TEXT,
            source              TEXT NOT NULL,          -- 'github' | 'twitter'
            profile_url         TEXT,
            queued_at           TIMESTAMPTZ DEFAULT NOW(),
            status              TEXT DEFAULT 'PENDING', -- PENDING | APPROVED | REJECTED | SENT
            UNIQUE (github_username),
            UNIQUE (twitter_handle)
        )
    """,

    # ── Agent 15: Waitlist Nurturer ───────────────────────────────────────
    "nurturer_log": """
        CREATE TABLE IF NOT EXISTS nurturer_log (
            id              SERIAL PRIMARY KEY,
            email           TEXT NOT NULL,
            sequence_name   TEXT,                       -- 'builder_sequence' | 'spectator_sequence'
            email_index     INT,                        -- 0-3
            sent_at         TIMESTAMPTZ DEFAULT NOW(),
            resend_id       TEXT,
            status          TEXT DEFAULT 'sent'
        )
    """,

    # waitlist_signups is an existing platform table.
    # This stub creates it for local dev/testing only.
    # In production, the real platform table is used — do not overwrite.
    "waitlist_signups": """
        CREATE TABLE IF NOT EXISTS waitlist_signups (
            id                  SERIAL PRIMARY KEY,
            email               TEXT NOT NULL UNIQUE,
            name                TEXT,
            user_type           TEXT DEFAULT 'builder', -- 'builder' | 'spectator'
            builder_framework   TEXT,                   -- 'LangChain'|'CrewAI'|'AutoGen'|'Custom'
            referral_code       TEXT,                   -- code they used when signing up
            discord_handle      TEXT,
            signed_up_at        TIMESTAMPTZ DEFAULT NOW()
        )
    """,

    # ── Agent 9: Competitor Monitor ───────────────────────────────────────
    "intel_log": """
        CREATE TABLE IF NOT EXISTS intel_log (
            id              SERIAL PRIMARY KEY,
            url             TEXT UNIQUE NOT NULL,
            source          TEXT,                       -- 'twitter' | 'github' | 'product_hunt'
            seen_at         TIMESTAMPTZ DEFAULT NOW(),
            classification  TEXT                        -- 'DIRECT_COMPETITOR'|'ADJACENT'|'NOISE'
        )
    """,

    # ── Agent 2: Scout ────────────────────────────────────────────────────
    "scout_replied": """
        CREATE TABLE IF NOT EXISTS scout_replied (
            id              SERIAL PRIMARY KEY,
            platform_id     TEXT UNIQUE NOT NULL,       -- tweet ID or 'reddit_<post_id>'
            source          TEXT,
            url             TEXT,
            queued_at       TIMESTAMPTZ DEFAULT NOW(),
            status          TEXT DEFAULT 'PENDING'      -- PENDING | APPROVED | SENT | SKIPPED
        )
    """,

    # ── Agent 4: Content Writer ───────────────────────────────────────────
    "content_topics": """
        CREATE TABLE IF NOT EXISTS content_topics (
            id          SERIAL PRIMARY KEY,
            title       TEXT NOT NULL,
            type        TEXT NOT NULL,  -- builder_technical|builder_strategy|
                                        -- spectator_narrative|platform_explainer|fpl_primer
            notes       TEXT,
            used        BOOLEAN DEFAULT FALSE,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """,

    "content_log": """
        CREATE TABLE IF NOT EXISTS content_log (
            id              SERIAL PRIMARY KEY,
            topic_id        INT,
            topic_title     TEXT,
            written_at      TIMESTAMPTZ DEFAULT NOW(),
            status          TEXT DEFAULT 'PENDING'      -- PENDING | PUBLISHED | REJECTED
        )
    """,

    # ── Agent 13: Community Manager ───────────────────────────────────────
    "community_replies": """
        CREATE TABLE IF NOT EXISTS community_replies (
            id              SERIAL PRIMARY KEY,
            message_id      TEXT UNIQUE NOT NULL,
            channel         TEXT,
            author          TEXT,
            trigger_type    TEXT,                       -- 'faq' | 'llm'
            reply_sent      TEXT,
            sent_at         TIMESTAMPTZ DEFAULT NOW()
        )
    """,

    # ── Agent 1: Broadcaster ─────────────────────────────────────────────────
    "broadcaster_history": """
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
    """,

    "broadcaster_log": """
        CREATE TABLE IF NOT EXISTS broadcaster_log (
            id              SERIAL PRIMARY KEY,
            contest_id      TEXT NOT NULL UNIQUE,
            narrative_type  TEXT,
            tweet_text      TEXT,
            tweet_id        TEXT,
            processed_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """,

    # ── Agent 10: Referral Tracker ────────────────────────────────────────
    "referral_codes": """
        CREATE TABLE IF NOT EXISTS referral_codes (
            id                  SERIAL PRIMARY KEY,
            code                TEXT UNIQUE NOT NULL,   -- e.g. REF-abc12345
            owner_email         TEXT NOT NULL,
            owner_wallet        TEXT,                   -- Solana wallet address (set later)
            referral_count      INT DEFAULT 0,
            total_paid_usdc     DECIMAL(10,2) DEFAULT 0,
            created_at          TIMESTAMPTZ DEFAULT NOW()
        )
    """,

    "referral_payouts": """
        CREATE TABLE IF NOT EXISTS referral_payouts (
            id              SERIAL PRIMARY KEY,
            referral_code   TEXT NOT NULL,
            owner_wallet    TEXT NOT NULL,
            amount_usdc     DECIMAL(10,2) NOT NULL,
            status          TEXT DEFAULT 'PENDING',     -- PENDING | SENT | FAILED
            solana_tx_sig   TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            sent_at         TIMESTAMPTZ
        )
    """,

    # ── Agent 14: Beat the Bot ────────────────────────────────────────────────
    "challenge_participants": """
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
    """,

    "challenge_results": """
        CREATE TABLE IF NOT EXISTS challenge_results (
            id              SERIAL PRIMARY KEY,
            participant_id  INT NOT NULL REFERENCES challenge_participants(id),
            gameweek        INT NOT NULL,
            human_points    INT,
            agent_points    INT,
            outcome         TEXT,                       -- WIN | LOSS | DRAW
            recorded_at     TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (participant_id, gameweek)
        )
    """,

    # ── Agent 6: SEO Farmer ───────────────────────────────────────────────────
    "seo_log": """
        CREATE TABLE IF NOT EXISTS seo_log (
            id SERIAL PRIMARY KEY,
            keyword TEXT UNIQUE NOT NULL,
            queued_at TIMESTAMPTZ DEFAULT NOW(),
            status TEXT DEFAULT 'PENDING'
        )
    """,

    # ── Agent 7: Reddit Persona ───────────────────────────────────────────────
    "reddit_drafts": """
        CREATE TABLE IF NOT EXISTS reddit_drafts (
            id SERIAL PRIMARY KEY,
            post_id TEXT UNIQUE NOT NULL,
            subreddit TEXT,
            draft_type TEXT,
            fantopy_mention BOOLEAN DEFAULT FALSE,
            queued_at TIMESTAMPTZ DEFAULT NOW(),
            status TEXT DEFAULT 'PENDING'
        )
    """,

    # ── Agent 8: Partnership Scout ────────────────────────────────────────────
    "partnership_log": """
        CREATE TABLE IF NOT EXISTS partnership_log (
            id SERIAL PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            target_name TEXT,
            opportunity_type TEXT,
            queued_at TIMESTAMPTZ DEFAULT NOW(),
            status TEXT DEFAULT 'PENDING'
        )
    """,

    # ── Agent 11: Influencer Identifier ──────────────────────────────────────
    "influencer_log": """
        CREATE TABLE IF NOT EXISTS influencer_log (
            id SERIAL PRIMARY KEY,
            twitter_handle TEXT UNIQUE NOT NULL,
            fit_score FLOAT,
            pitched_at TIMESTAMPTZ,
            status TEXT DEFAULT 'IDENTIFIED'
        )
    """,

    # ── Agent 12: Press Pitcher ───────────────────────────────────────────────
    "milestone_log": """
        CREATE TABLE IF NOT EXISTS milestone_log (
            id SERIAL PRIMARY KEY,
            milestone TEXT NOT NULL,
            detail TEXT,
            logged_at TIMESTAMPTZ DEFAULT NOW(),
            pitched BOOLEAN DEFAULT FALSE
        )
    """,

    "press_log": """
        CREATE TABLE IF NOT EXISTS press_log (
            id SERIAL PRIMARY KEY,
            journalist_handle TEXT NOT NULL,
            milestone TEXT,
            queued_at TIMESTAMPTZ DEFAULT NOW(),
            status TEXT DEFAULT 'PENDING',
            UNIQUE (journalist_handle, milestone)
        )
    """,
}

# ── Seed content_topics with starter topics ───────────────────────────────────

SEED_TOPICS = [
    ("How to use xG data in your FPL agent", "builder_technical", "Walk through Understat xG/xA APIs and how to weight them in transfer decisions"),
    ("When should your agent play the wildcard?", "builder_strategy", "Decision framework for chip timing — expected value vs optionality"),
    ("Why watching AI agents fail is the best part of Fantopy", "spectator_narrative", "The drama angle: spectacular misses, stubborn degens, and streaks broken at GW37"),
    ("How Fantopy Arena works: a complete guide", "platform_explainer", "End-to-end explainer for new visitors — builders and spectators"),
    ("FPL for non-football people: everything you need to know to follow along", "fpl_primer", "Zero football knowledge assumed — analogies to other games/sports"),
    ("Fixture difficulty ratings: how top agents think about scheduling", "builder_technical", "FDR data sources, how to model upcoming runs, rotation risk"),
    ("The four agent personalities of Fantopy Arena", "spectator_narrative", "Quant vs Degen vs Contrarian vs Grinder — why personality = strategy"),
    ("Double gameweeks and why they break bad agents", "builder_strategy", "DGW detection, player stacking, and the trap of over-rotating"),
    ("Building a captain selector: the hardest decision in FPL", "builder_technical", "Modelling captain variance, form, home/away splits, ownership %"),
    ("What makes a great Fantopy spectator season", "spectator_narrative", "Narrative hooks: who to follow, what to watch for across 38 gameweeks"),
]


def run():
    print("Creating marketing agent tables...\n")

    with Session() as session:
        for name, ddl in TABLES.items():
            try:
                session.execute(text(ddl))
                session.commit()
                print(f"  OK {name}")
            except Exception as e:
                session.rollback()
                print(f"  FAIL {name}: {e}")

        # Seed content topics if table is empty
        count = session.execute(text("SELECT COUNT(*) FROM content_topics")).scalar()
        if count == 0:
            print("\nSeeding content_topics...")
            for title, type_, notes in SEED_TOPICS:
                session.execute(text("""
                    INSERT INTO content_topics (title, type, notes)
                    VALUES (:title, :type, :notes)
                    ON CONFLICT DO NOTHING
                """), {"title": title, "type": type_, "notes": notes})
            session.commit()
            print(f"  OK {len(SEED_TOPICS)} starter topics seeded")
        else:
            print(f"\n  content_topics already has {count} rows — skipping seed")

    print("\nDone.")


if __name__ == "__main__":
    run()
