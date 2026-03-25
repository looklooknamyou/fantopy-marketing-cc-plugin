# Credentials needed

## Fill in NOW (agents can run with just these)

| Key | Where to get it | Used by |
|-----|-----------------|---------|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys | All agents |
| `DATABASE_URL` | Your existing Fantopy Postgres connection string | All agents |

Format: `postgresql://USER:PASSWORD@HOST:PORT/DATABASE`

---

## Fill in when colleague hands over platform credentials

| Key | Notes | Used by |
|-----|-------|---------|
| `GITHUB_TOKEN` | Personal access token, scopes: `public_repo`, `read:user` | Agent 3, 9 |
| `TWITTER_BEARER_TOKEN` | App-only bearer token from developer.twitter.com | Agent 3, 9, 2 |
| `TWITTER_API_KEY` | OAuth 1.0a key (needed only for posting tweets — Agent 1) | Agent 1 |
| `TWITTER_API_SECRET` | OAuth 1.0a secret | Agent 1 |
| `TWITTER_ACCESS_TOKEN` | OAuth 1.0a access token | Agent 1 |
| `TWITTER_ACCESS_SECRET` | OAuth 1.0a access secret | Agent 1 |
| `REDDIT_CLIENT_ID` | Script app at reddit.com/prefs/apps | Agent 2 |
| `REDDIT_CLIENT_SECRET` | Same app | Agent 2 |
| `RESEND_API_KEY` | resend.com → API Keys | Agent 15 |
| `FROM_EMAIL` | Verified sender in Resend (e.g. hello@fantopyarena.com) | Agent 15 |
| `DISCORD_BOT_TOKEN` | discord.com/developers → Bot tab | Agent 13 |
| `DISCORD_WEBHOOK_URL` | Channel settings → Integrations → Webhooks | Agents 3,2,4,9,10 |
| `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON` | GCP Console → IAM → Service Accounts → JSON key | Agents 3,2,4 |
| `RECRUITER_SHEET_ID` | The spreadsheet ID from the URL of the review sheet | Agents 3,2,4 |

---

## Fill in when Marcus provides (Phase 2)

| Key | Notes | Used by |
|-----|-------|---------|
| `FANTOPY_API_KEY` | Read-only key from Marcus | Agent 1 |
| `FANTOPY_API_BASE_URL` | Base URL of the Fantopy API | Agent 1 |
| `MOLTBOOK_API_KEY` | For posting to competing agent profiles | Agent 1 |
| `SOLANA_RPC_URL` | Can use `https://api.mainnet-beta.solana.com` for now | Agent 10 |
| `PLATFORM_WALLET_KEYPAIR_B58` | Base58-encoded private key of the payout wallet | Agent 10 |

---

## Optional

| Key | Notes |
|-----|-------|
| `SLACK_WEBHOOK_URL` | If you want intel reports in Slack as well as Discord |
| `DISCORD_INTEL_CHANNEL_ID` | If Agent 9 should post to a specific channel (not just webhook) |
