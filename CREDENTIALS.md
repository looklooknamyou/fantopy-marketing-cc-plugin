# Credentials Reference

## Status legend
- 🔴 Blocking — agents cannot run without this
- 🟡 Needed soon — specific agents/features blocked
- 🟢 When ready — Phase 2 / platform-dependent
- ⚪ Optional — nice to have

---

## 🔴 Priority 1 — LLM (all 13 content agents blocked without this)

| Key | Purpose | Where to get |
|-----|---------|--------------|
| `GROQ_API_KEY` | LLM inference for all agents — currently blocked by network. Switch to Gemini below | console.groq.com (free) |
| `GEMINI_API_KEY` | **Recommended alternative** — free, works globally, no card needed | aistudio.google.com → Get API key |

> Set whichever works. Currently configured for Groq (`llama-3.3-70b`). To switch to Gemini, update `shared/llm.py`.

---

## 🔴 Priority 2 — Database

| Key | Purpose | Where to get |
|-----|---------|--------------|
| `DATABASE_URL` | All agents read/write prospect and campaign data | Your existing Docker Postgres: `postgresql://fantopy:changeme@localhost:5433/fantopy` |

---

## 🟡 Priority 3 — Outreach & Email (needed to send anything)

| Key | Purpose | Where to get |
|-----|---------|--------------|
| `RESEND_API_KEY` | Agent 15 waitlist email sequences (4-email builder + spectator nurture) | resend.com → API Keys (free tier: 3k emails/month) |
| `FROM_EMAIL` | Verified sender address for Resend | Must be a domain you own, verified in Resend dashboard |

---

## 🟡 Priority 4 — Developer Discovery (Agents 3, 8, 11)

| Key | Purpose | Where to get |
|-----|---------|--------------|
| `GITHUB_TOKEN` | Search GitHub for FPL/AI builders, framework repos, hackathons | github.com → Settings → Developer Settings → Personal Access Tokens → scopes: `public_repo`, `read:user` |
| `TWITTER_BEARER_TOKEN` | Search Twitter for prospect tweets, monitor keywords, find influencers | developer.twitter.com → Project → App → Keys & Tokens → Bearer Token (free Basic tier) |

---

## 🟡 Priority 5 — Publishing (Agent 1 posts results, Agent 2 replies)

| Key | Purpose | Where to get |
|-----|---------|--------------|
| `TWITTER_API_KEY` | Post tweets as @fantopy (OAuth 1.0a — needed on top of Bearer) | developer.twitter.com → same app → API Key & Secret |
| `TWITTER_API_SECRET` | As above | As above |
| `TWITTER_ACCESS_TOKEN` | As above (user-level auth) | developer.twitter.com → Access Token & Secret |
| `TWITTER_ACCESS_SECRET` | As above | As above |
| `REDDIT_CLIENT_ID` | Agent 2 Reddit monitoring | reddit.com/prefs/apps → create Script app |
| `REDDIT_CLIENT_SECRET` | As above | As above |

---

## 🟡 Priority 6 — Review Queue & Notifications

| Key | Purpose | Where to get |
|-----|---------|--------------|
| `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON` | Agents 3, 2, 4 write outreach/content drafts to a Sheets review queue | GCP Console → IAM & Admin → Service Accounts → Create → JSON key. Share the sheet with the service account email. |
| `RECRUITER_SHEET_ID` | The Google Sheets spreadsheet ID (from its URL) where outreach drafts queue | Create a blank Google Sheet, copy the ID from the URL |
| `DISCORD_WEBHOOK_URL` | Agents post alerts, intel briefs, and leaderboards to your Discord | Discord server → channel settings → Integrations → Webhooks → New Webhook |
| `DISCORD_BOT_TOKEN` | Agent 13 Community Manager — always-on Discord bot for FAQ + welcome replies | discord.com/developers → Applications → New App → Bot tab → Reset Token |

---

## 🟢 Priority 7 — Platform Integration (from Marcus)

| Key | Purpose | Notes |
|-----|---------|-------|
| `FANTOPY_API_KEY` | Agent 1 Broadcaster — authenticate against Fantopy backend to receive contest results | Request from Marcus |
| `FANTOPY_API_BASE_URL` | Base URL of the Fantopy API (e.g. `https://api.fantopyarena.com`) | Request from Marcus |
| `MCP_GATEWAY_SSE_URL` | SSE endpoint for `contest.scored` real-time events | Request from Marcus |

---

## 🟢 Priority 8 — Solana Payouts (Agent 10)

| Key | Purpose | Notes |
|-----|---------|-------|
| `SOLANA_RPC_URL` | Blockchain RPC for USDC payout transactions | Use `https://api.mainnet-beta.solana.com` for mainnet |
| `PLATFORM_WALLET_KEYPAIR_B58` | Base58-encoded private key of the wallet that sends USDC rewards | Request from Marcus — keep this extremely secure |

---

## ⚪ Optional

| Key | Purpose |
|-----|---------|
| `SLACK_WEBHOOK_URL` | Duplicate Agent 9 intel reports to Slack in addition to Discord |
| `DISCORD_INTEL_CHANNEL_ID` | Pin Agent 9 competitor reports to a specific Discord channel |
| `MCP_GATEWAY_SSE_URL` | Same as above — SSE stream for live contest events |
