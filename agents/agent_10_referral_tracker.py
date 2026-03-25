"""
================================================================================
AGENT 10: REFERRAL TRACKER
================================================================================
TRIGGER:      Event-driven — fires when a new waitlist signup includes a
              referral code  OR  run in batch mode daily at 06:00 UTC
INPUTS:       Postgres `waitlist_signups` table (referral_code field),
              Postgres `referral_codes` table
OUTPUTS:      USDC payout instruction queued in `referral_payouts` table.
              Actual on-chain transfer executed when threshold met.
HUMAN REVIEW: NO — fully autonomous
BLOCKCHAIN:   Solana — USDC SPL token transfers via HTTP RPC
              Uses Solana JSON-RPC API (no heavy SDK needed)
SAFETY:       Payouts only execute after N referrals (configurable).
              All txns logged. Failed txns flagged to Discord for manual review.
BLOCKED ON:   Solana RPC endpoint, platform wallet private key (from Marcus),
              USDC token mint address (standard: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v)
================================================================================

REFERRAL SYSTEM DESIGN:
  - Each registered builder gets a unique referral code (e.g. REF-abc123)
  - When a new signup uses their code: +1 referral count
  - Reward tiers (configurable via env):
      REFERRAL_REWARD_USDC=5        per confirmed referral
      REFERRAL_MIN_PAYOUT=10        minimum balance before payout triggers
  - Payout is queued, then executed in batch
  - Each payout is idempotent (checked against referral_payouts table)

TABLE SCHEMAS ASSUMED:
  referral_codes: id, code TEXT UNIQUE, owner_email, owner_wallet TEXT,
                  referral_count INT DEFAULT 0, total_paid_usdc DECIMAL(10,2) DEFAULT 0
  waitlist_signups: (existing) + referral_code TEXT nullable
  referral_payouts: id, referral_code, owner_wallet, amount_usdc,
                    status (PENDING|SENT|FAILED), solana_tx_sig, created_at, sent_at
================================================================================
"""

import os
import sys
import logging
import datetime
import secrets
import string
import httpx
import base64
import json
from decimal import Decimal
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.db import Session

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent_10_referral")

SOLANA_RPC_URL = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
PLATFORM_WALLET_KEYPAIR_B58 = os.environ.get("PLATFORM_WALLET_KEYPAIR_B58", "")  # base58 private key
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

REWARD_PER_REFERRAL = Decimal(os.environ.get("REFERRAL_REWARD_USDC", "5"))
MIN_PAYOUT = Decimal(os.environ.get("REFERRAL_MIN_PAYOUT", "10"))

# ── DB helpers ────────────────────────────────────────────────────────────────

def ensure_tables() -> None:
    with Session() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS referral_codes (
                id SERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                owner_email TEXT NOT NULL,
                owner_wallet TEXT,
                referral_count INT DEFAULT 0,
                total_paid_usdc DECIMAL(10,2) DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS referral_payouts (
                id SERIAL PRIMARY KEY,
                referral_code TEXT NOT NULL,
                owner_wallet TEXT NOT NULL,
                amount_usdc DECIMAL(10,2) NOT NULL,
                status TEXT DEFAULT 'PENDING',
                solana_tx_sig TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                sent_at TIMESTAMPTZ
            )
        """))
        session.commit()


def generate_referral_code() -> str:
    chars = string.ascii_lowercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(8))
    return f"REF-{suffix}"


def get_or_create_referral_code(email: str, wallet: str | None = None) -> str:
    with Session() as session:
        existing = session.execute(
            text("SELECT code FROM referral_codes WHERE owner_email = :email"),
            {"email": email}
        ).fetchone()
        if existing:
            return existing[0]

        code = generate_referral_code()
        # Ensure uniqueness
        while session.execute(
            text("SELECT 1 FROM referral_codes WHERE code = :code"), {"code": code}
        ).fetchone():
            code = generate_referral_code()

        session.execute(text("""
            INSERT INTO referral_codes (code, owner_email, owner_wallet)
            VALUES (:code, :email, :wallet)
        """), {"code": code, "email": email, "wallet": wallet})
        session.commit()
        log.info(f"Created referral code {code} for {email}")
        return code


# ── Process new signup ────────────────────────────────────────────────────────

def process_referral(signup_id: int) -> None:
    """Called when a new signup contains a referral code."""
    with Session() as session:
        signup = session.execute(
            text("SELECT email, referral_code FROM waitlist_signups WHERE id = :id"),
            {"id": signup_id}
        ).mappings().fetchone()

        if not signup or not signup["referral_code"]:
            return

        code = signup["referral_code"]
        ref_row = session.execute(
            text("SELECT id, owner_email, owner_wallet, referral_count FROM referral_codes WHERE code = :code"),
            {"code": code}
        ).mappings().fetchone()

        if not ref_row:
            log.warning(f"Unknown referral code: {code}")
            return

        # Prevent self-referral
        if ref_row["owner_email"] == signup["email"]:
            log.info(f"Self-referral attempted by {signup['email']} — skipping")
            return

        # Increment count
        session.execute(text("""
            UPDATE referral_codes SET referral_count = referral_count + 1 WHERE code = :code
        """), {"code": code})
        session.commit()

        log.info(f"Referral credited: {code} → {ref_row['owner_email']} (total: {ref_row['referral_count'] + 1})")

        check_and_queue_payout(code)


def check_and_queue_payout(code: str) -> None:
    """Queue a payout if the referrer has reached minimum threshold."""
    with Session() as session:
        ref_row = session.execute(
            text("SELECT owner_email, owner_wallet, referral_count, total_paid_usdc FROM referral_codes WHERE code = :code"),
            {"code": code}
        ).mappings().fetchone()

        if not ref_row or not ref_row["owner_wallet"]:
            log.info(f"  No wallet set for {code} — skipping payout")
            return

        earned = Decimal(ref_row["referral_count"]) * REWARD_PER_REFERRAL
        paid = Decimal(ref_row["total_paid_usdc"])
        unpaid = earned - paid

        if unpaid < MIN_PAYOUT:
            log.info(f"  {code}: unpaid balance {unpaid} USDC < minimum {MIN_PAYOUT} — not yet")
            return

        # Check no pending payout already in flight
        pending = session.execute(text("""
            SELECT 1 FROM referral_payouts
            WHERE referral_code = :code AND status = 'PENDING'
            LIMIT 1
        """), {"code": code}).fetchone()

        if pending:
            log.info(f"  {code}: payout already pending")
            return

        # Queue payout
        session.execute(text("""
            INSERT INTO referral_payouts (referral_code, owner_wallet, amount_usdc, status)
            VALUES (:code, :wallet, :amount, 'PENDING')
        """), {"code": code, "wallet": ref_row["owner_wallet"], "amount": float(unpaid)})
        session.commit()
        log.info(f"  Queued payout: {unpaid} USDC → {ref_row['owner_wallet']}")


# ── Solana USDC transfer ──────────────────────────────────────────────────────
# NOTE: Full Solana transaction construction requires the solders or solana-py
# library for signing. We use a lightweight approach here with the JSON-RPC API.
# Install: pip install solders
#
# BLOCKED: This section requires PLATFORM_WALLET_KEYPAIR_B58 from Marcus.
# The payout queuing above is fully functional without it.

def execute_payout(payout_id: int, wallet: str, amount_usdc: Decimal) -> str | None:
    """
    Execute a USDC transfer on Solana.
    Returns transaction signature or None on failure.

    IMPORTANT: Requires solders library and a funded platform wallet.
    This function is a stub until wallet credentials are provided.
    """
    if not PLATFORM_WALLET_KEYPAIR_B58:
        log.warning("PLATFORM_WALLET_KEYPAIR_B58 not set — payout execution blocked")
        notify_discord_failure(payout_id, wallet, amount_usdc, "Wallet keypair not configured")
        return None

    try:
        from solders.keypair import Keypair  # type: ignore
        from solders.pubkey import Pubkey    # type: ignore

        # Decode platform keypair
        keypair_bytes = base64.b58decode(PLATFORM_WALLET_KEYPAIR_B58)
        keypair = Keypair.from_bytes(keypair_bytes)
        log.info(f"Platform wallet: {keypair.pubkey()}")

        # USDC amount in micro-units (6 decimals)
        usdc_lamports = int(amount_usdc * 1_000_000)

        # Get recent blockhash
        rpc_resp = httpx.post(SOLANA_RPC_URL, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getLatestBlockhash",
            "params": [{"commitment": "confirmed"}]
        }, timeout=30)
        rpc_resp.raise_for_status()
        blockhash = rpc_resp.json()["result"]["value"]["blockhash"]

        # For SPL token transfers we need the Associated Token Account
        # This is a simplified stub — full implementation needs ATA derivation
        # and SPL token program instruction building (use solders for this).
        log.warning("SPL token transfer requires full solders implementation — queuing for manual review")
        notify_discord_failure(
            payout_id, wallet, amount_usdc,
            "SPL token transfer not yet implemented — manual payout required"
        )
        return None

    except ImportError:
        log.error("solders not installed — run: pip install solders")
        return None
    except Exception as e:
        log.error(f"Payout execution failed: {e}")
        notify_discord_failure(payout_id, wallet, amount_usdc, str(e))
        return None


def notify_discord_failure(payout_id: int, wallet: str, amount: Decimal, reason: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        httpx.post(DISCORD_WEBHOOK_URL, json={
            "content": (
                f"**Agent 10 — Referral Payout FAILED**\n"
                f"Payout ID: {payout_id}\n"
                f"Wallet: `{wallet}`\n"
                f"Amount: {amount} USDC\n"
                f"Reason: {reason}\n"
                f"Manual action required."
            )
        }, timeout=10)
    except Exception as e:
        log.error(f"Discord notify failed: {e}")


# ── Batch: process all pending payouts ───────────────────────────────────────

def run_batch_payouts() -> None:
    with Session() as session:
        pending = session.execute(text("""
            SELECT id, referral_code, owner_wallet, amount_usdc
            FROM referral_payouts
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
        """)).mappings().all()

    log.info(f"Pending payouts: {len(pending)}")

    for payout in pending:
        pid = payout["id"]
        wallet = payout["owner_wallet"]
        amount = Decimal(str(payout["amount_usdc"]))

        log.info(f"Processing payout {pid}: {amount} USDC → {wallet}")
        tx_sig = execute_payout(pid, wallet, amount)

        with Session() as session:
            if tx_sig:
                session.execute(text("""
                    UPDATE referral_payouts
                    SET status = 'SENT', solana_tx_sig = :sig, sent_at = NOW()
                    WHERE id = :id
                """), {"sig": tx_sig, "id": pid})
                # Update total paid on referral code
                session.execute(text("""
                    UPDATE referral_codes
                    SET total_paid_usdc = total_paid_usdc + :amount
                    WHERE code = :code
                """), {"amount": float(amount), "code": payout["referral_code"]})
                log.info(f"  Payout {pid} sent: {tx_sig}")
            else:
                session.execute(text("""
                    UPDATE referral_payouts SET status = 'FAILED' WHERE id = :id
                """), {"id": pid})
                log.warning(f"  Payout {pid} failed")
            session.commit()


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    import argparse
    parser = argparse.ArgumentParser(description="Agent 10: Referral Tracker")
    parser.add_argument("--signup-id", type=int, help="Process referral for a single signup")
    parser.add_argument("--batch-payouts", action="store_true", help="Execute all pending payouts")
    parser.add_argument("--create-code", type=str, help="Generate referral code for email address")
    args = parser.parse_args()

    ensure_tables()

    if args.signup_id:
        log.info(f"=== Processing referral for signup {args.signup_id} ===")
        process_referral(args.signup_id)

    elif args.batch_payouts:
        log.info("=== Agent 10: Referral Tracker — batch payouts ===")
        run_batch_payouts()

    elif args.create_code:
        code = get_or_create_referral_code(args.create_code)
        print(f"Referral code for {args.create_code}: {code}")

    else:
        # Default: scan for any unprocessed referrals + run payouts
        log.info("=== Agent 10: Referral Tracker — full run ===")
        with Session() as session:
            unprocessed = session.execute(text("""
                SELECT ws.id FROM waitlist_signups ws
                WHERE ws.referral_code IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM referral_payouts rp
                    WHERE rp.referral_code = ws.referral_code
                )
            """)).fetchall()

        for row in unprocessed:
            process_referral(row[0])

        run_batch_payouts()
        log.info("=== Done ===")


if __name__ == "__main__":
    run()
