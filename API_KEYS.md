# API Keys & Credentials

All credentials go in `.env` (never commit this file). Below is every key the fleet needs, what it's for, where to get it, and which agents require it.

---

## Priority 1 — Needed now (Phase 1 agents)

### `ANTHROPIC_API_KEY`
- **Used by:** Agents 3, 2, 4, 6, 7, 8, 9, 11, 12, 13, 14, 1
- **What it does:** Powers all LLM calls (outreach drafts, content writing, classifications, replies)
- **Model used:** `claude-sonnet-4-6`
- **How to get:** [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key
- **Billing:** Pay-per-token (separate from Claude Max subscription). Estimated cost: ~$2–10/month for this fleet.
- **Format:** `sk-ant-api03-...`

---

### `DATABASE_URL`
- **Used by:** All agents (deduplication + logging)
- **What it does:** Postgres connection string
- **Value (local Docker):** `postgresql://fantopy:changeme@localhost:5433/fantopy`
- **How to get:** Already set if running the existing platform Docker container on port 5433.

---

### `RESEND_API_KEY`
- **Used by:** Agent 15 (Waitlist Nurturer), Agent 14 (Beat the Bot result emails)
- **What it does:** Sends transactional emails via [resend.com](https://resend.com)
- **How to get:** resend.com → Sign up → API Keys → Create Key
- **Billing:** Free up to 3,000 emails/month, then paid
- **Format:** `re_...`

### `FROM_EMAIL`
- **Used by:** Agents 15, 14
- **Value:** `hello@fantopyarena.com` (or whatever sending address is verified in Resend)
- **Note:** Domain must be verified in Resend dashboard before emails will send.

---

### `GITHUB_TOKEN`
- **Used by:** Agents 3 (Recruiter), 8 (Partnership Scout)
- **What it does:** GitHub repository search API
- **How to get:** github.com → Settings → Developer Settings → Personal Access Tokens → Tokens (classic) → Generate
- **Scopes needed:** `public_repo` (read-only is fine)
- **Format:** `ghp_...`

---

### `TWITTER_BEARER_TOKEN`
- **Used by:** Agents 3, 2, 8, 9, 11
- **What it does:** Twitter/X search API (read-only)
- **How to get:** [developer.twitter.com](https://developer.twitter.com) → Projects & Apps → Your App → Keys and Tokens → Bearer Token
- **Note:** Requires a Twitter Developer account (free Basic tier works for read access)
- **Format:** `AAAA...` (long base64 string)

### `TWITTER_API_KEY` + `TWITTER_API_SECRET` + `TWITTER_ACCESS_TOKEN` + `TWITTER_ACCESS_SECRET`
- **Used by:** Agent 1 (Broadcaster — posting tweets)
- **What it does:** Write access to post tweets
- **How to get:** Same Twitter Developer app → Keys and Tokens → API Key and Secret + Access Token and Secret
- **Note:** Requires app to have Read+Write permissions (change in app settings)

---

### `DISCORD_WEBHOOK_URL`
- **Used by:** Agents 9, 3, 8, 11, 12, 14 (notifications when drafts are ready)
- **What it does:** Posts intel briefs and review notifications to a Discord channel
- **How to get:** Discord → Server Settings → Integrations → Webhooks → New Webhook → Copy URL
- **Format:** `https://discord.com/api/webhooks/...`

### `DISCORD_BOT_TOKEN`
- **Used by:** Agent 13 (Community Manager — always-on bot)
- **What it does:** Reads messages and posts replies in Discord
- **How to get:** [discord.com/developers/applications](https://discord.com/developers/applications) → New Application → Bot → Reset Token
- **Note:** Bot must be invited to your server with `bot` + `applications.commands` scopes and Message Content Intent enabled

### `DISCORD_INTEL_CHANNEL_ID`
- **Used by:** Agent 9 (Competitor Monitor)
- **What it does:** Posts weekly intel reports to a specific channel
- **How to get:** Discord → Enable Developer Mode → Right-click channel → Copy ID

---

## Priority 2 — Needed for Google Sheets review queue

### `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`
- **Used by:** Agents 3, 2, 4, 6, 7, 8, 11, 12 (any agent that writes drafts for human review)
- **What it does:** Path to a Google service account JSON file that has edit access to review spreadsheets
- **How to get:**
  1. [console.cloud.google.com](https://console.cloud.google.com) → New Project → Enable Google Sheets API + Google Drive API
  2. IAM & Admin → Service Accounts → Create → Download JSON key
  3. Share each Google Sheet with the service account email (`...@....iam.gserviceaccount.com`)
- **Value in .env:** Full file path, e.g. `C:/Users/mgiri/keys/fantopy-sheets.json`

### `RECRUITER_SHEET_ID`
- **Used by:** Agent 3
- **What it does:** ID of the Google Sheet where recruiter outreach drafts are queued
- **How to get:** Create a blank Google Sheet → copy the ID from the URL: `docs.google.com/spreadsheets/d/<THIS_PART>/edit`

### `NURTURER_SHEET_ID`
- **Used by:** Agent 15
- **What it does:** ID of the Google Sheet for nurturer email logs
- **How to get:** Same as above — create a blank sheet, copy the ID

---

## Priority 3 — Needed from Marcus (platform team)

### `FANTOPY_API_BASE_URL`
- **Used by:** Agent 1 (Broadcaster)
- **What it does:** Base URL for the Fantopy platform API (contest results, leaderboards)
- **Example:** `https://api.fantopyarena.com`

### `FANTOPY_API_KEY`
- **Used by:** Agent 1
- **What it does:** Auth header for Fantopy platform API calls

### `MCP_GATEWAY_SSE_URL`
- **Used by:** Agent 1 (listen mode — real-time `contest.scored` events)
- **What it does:** SSE stream URL that fires when a contest is scored
- **Example:** `https://mcp.fantopyarena.com/events`

### `MOLTBOOK_API_KEY`
- **Used by:** Agent 5 (not yet built — pending Moltbook API access)
- **What it does:** Posts content to Moltbook platform

---

## Priority 4 — Optional

### `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` + `REDDIT_USER_AGENT`
- **Used by:** Agents 2 (Scout), 7 (Reddit Persona)
- **How to get:** [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) → Create App → script type
- **Note:** `REDDIT_USER_AGENT` can stay as `FantopyScout/1.0`

### `SLACK_WEBHOOK_URL`
- **Used by:** Agent 9 (Competitor Monitor — optional second channel for intel reports)
- **How to get:** Slack → App Directory → Incoming Webhooks → Add to Slack

---

## GitHub Actions secrets

When running via GitHub Actions (scheduled cron jobs), add each key above as a **repository secret**:

`github.com/looklooknamyou/fantopy-marketing-cc-plugin` → Settings → Secrets and variables → Actions → New repository secret

Secret names must exactly match the `.env` key names (e.g. `ANTHROPIC_API_KEY`, `DATABASE_URL`, etc.).

> **Note:** `DATABASE_URL` for GitHub Actions should point to a hosted Postgres instance (e.g. Supabase, Railway, Neon) rather than `localhost`, since GitHub Actions runners can't reach your local Docker container.
