# Fantopy Marketing Agents

Autonomous marketing agent fleet for [Fantopy Arena](https://fantopyarena.com) — an AI agent vs agent Fantasy Premier League competition platform by Benchwarmers Pte Ltd.

Each agent has one job. Together they handle builder recruitment, waitlist nurturing, content broadcasting, community monitoring, and growth — with minimal human input.

---

## Quick start

### Prerequisites
- Python 3.11+
- Docker Desktop (for local Postgres)
- Git

### 1. Clone and install

```bash
git clone https://github.com/looklooknamyou/fantopy-marketing-cc-plugin.git
cd fantopy-marketing-cc-plugin
pip install -r requirements.txt
```

### 2. Start the database

```bash
docker run -d \
  --name fantopy-marketing-db \
  --restart unless-stopped \
  -e POSTGRES_USER=fantopy \
  -e POSTGRES_PASSWORD=changeme \
  -e POSTGRES_DB=fantopy \
  -p 5432:5432 \
  postgres:15
```

### 3. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in at minimum:

```env
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://fantopy:changeme@localhost:5432/fantopy
```

See [CREDENTIALS.md](CREDENTIALS.md) for the full list of what each agent needs.

### 4. Create all database tables

```bash
python db/create_tables.py
```

This creates all 20 marketing agent tables and seeds 10 starter blog topics for Agent 4.

### 5. Launch the dashboard

```bash
python -m streamlit run dashboard/Home.py
```

Opens at `http://localhost:8501`

---

## The Agent Fleet

| Agent | Name | Trigger | Human review | Phase |
|-------|------|---------|--------------|-------|
| 1 | [Broadcaster](agents/agent_01_broadcaster.py) | `contest.scored` SSE event | No | 2 |
| 2 | [Scout](agents/agent_02_scout.py) | Every 6h | Yes | 3 |
| 3 | [Recruiter](agents/agent_03_recruiter.py) | Monday 08:00 UTC | Yes | 1 ✅ |
| 4 | [Content Writer](agents/agent_04_content_writer.py) | Wednesday 07:00 UTC | Yes | 3 |
| 6 | [SEO Farmer](agents/agent_06_seo_farmer.py) | Tuesday 06:00 UTC | Yes | Bench |
| 7 | [Reddit Persona](agents/agent_07_reddit_persona.py) | Every 48h | Yes (always) | Bench |
| 8 | [Partnership Scout](agents/agent_08_partnership_scout.py) | Monday 09:00 UTC | Yes | Bench |
| 9 | [Competitor Monitor](agents/agent_09_competitor_monitor.py) | Friday 08:00 UTC | No | 1 ✅ |
| 10 | [Referral Tracker](agents/agent_10_referral_tracker.py) | Daily 06:00 UTC | No | 3 |
| 11 | [Influencer Identifier](agents/agent_11_influencer_identifier.py) | Sunday 08:00 UTC | Yes | Bench |
| 12 | [Press Pitcher](agents/agent_12_press_pitcher.py) | Milestone-triggered | Yes | Bench |
| 13 | [Community Manager](agents/agent_13_community_manager.py) | Always-on Discord bot | No | 3 |
| 14 | [Beat the Bot](agents/agent_14_beat_the_bot.py) | Pre/post gameweek | Tweets only | 1 ✅ |
| 15 | [Waitlist Nurturer](agents/agent_15_waitlist_nurturer.py) | Signup event / daily | No | 1 ✅ |

**Phase 1** agents are built and ready to run as soon as credentials are supplied.
**Agent 5** (Moltbook Native) is pending Moltbook API access.

---

## Architecture

Every agent follows the same 7-step pattern:

```
TRIGGER → DISCOVERY → RESEARCH → DRAFT → REVIEW → SEND → TRACK
```

- **Triggers:** GitHub Actions cron jobs or event webhooks
- **LLM:** Claude Sonnet via Anthropic API (`shared/llm.py`)
- **Storage:** Postgres for deduplication and logging (`shared/db.py`)
- **Review queue:** Google Sheets for any agent that touches external people (`shared/sheets.py`)
- **Notifications:** Discord webhook when drafts are ready for review

Agents that touch external people (outreach, press, Reddit) **never send automatically**. They write drafts to Google Sheets and ping Discord. A human approves before anything goes out.

---

## Repository structure

```
├── agents/                   # One file per agent
│   ├── agent_01_broadcaster.py
│   ├── agent_03_recruiter.py
│   ├── agent_14_beat_the_bot.py
│   ├── agent_15_waitlist_nurturer.py
│   └── ...
├── shared/
│   ├── db.py                 # SQLAlchemy helpers, dedup checks
│   ├── llm.py                # Anthropic Claude client
│   └── sheets.py             # Google Sheets queue writer
├── db/
│   └── create_tables.py      # One-time DB setup script
├── dashboard/
│   ├── Home.py               # Streamlit dashboard entry point
│   └── pages/
│       ├── 1_Agent_Runner.py     # Manually trigger any agent
│       ├── 2_Queue_Monitor.py    # Review pending queue items
│       ├── 3_Beat_The_Bot.py     # Register participants + leaderboard
│       ├── 4_Waitlist.py         # Test signups + email previews
│       └── 5_Database.py         # Browse any DB table
├── .github/workflows/        # GitHub Actions cron schedules
├── .env.example              # Credential template
├── CREDENTIALS.md            # What each agent needs and where to get it
├── MARCUS_SPEC.md            # What is still needed from the platform team
└── requirements.txt
```

---

## Dashboard

Run `python -m streamlit run dashboard/Home.py` to open the ops dashboard:

| Page | Purpose |
|------|---------|
| **Home** | DB status, credential checker, table sizes, recent activity |
| **Agent Runner** | Trigger any agent manually, stream live output |
| **Queue Monitor** | View and approve/reject items from all review queues |
| **Beat the Bot** | Register participants, enter results, live leaderboard |
| **Waitlist** | Add test signups, preview email sequences, view nurturer log |
| **Database** | Browse any table, run read-only SQL queries |

---

## Running agents manually

```bash
# Agent 3 — Recruiter
python agents/agent_03_recruiter.py

# Agent 15 — Waitlist Nurturer (batch)
python agents/agent_15_waitlist_nurturer.py --batch

# Agent 15 — Nurturer for a specific signup ID
python agents/agent_15_waitlist_nurturer.py --signup-id 42

# Agent 14 — Beat the Bot (register participant)
python agents/agent_14_beat_the_bot.py --register email@example.com "Name" 123456 agent-id-here

# Agent 14 — Beat the Bot (process results for current GW)
python agents/agent_14_beat_the_bot.py --results

# Agent 14 — Beat the Bot (post leaderboard to Discord)
python agents/agent_14_beat_the_bot.py --leaderboard

# Agent 9 — Competitor Monitor
python agents/agent_09_competitor_monitor.py

# Agent 1 — Broadcaster (poll mode)
python agents/agent_01_broadcaster.py --poll

# Agent 1 — Broadcaster (specific contest)
python agents/agent_01_broadcaster.py --contest-id <contest_id>

# Agent 12 — Press Pitcher (milestone triggered)
python agents/agent_12_press_pitcher.py --milestone "100 agents registered"
```

---

## GitHub Actions schedules

All cron jobs are defined in `.github/workflows/`. Add secrets in **GitHub → Settings → Secrets → Actions** matching the keys in `.env.example`.

| Workflow | Schedule |
|----------|---------|
| Agent 3 Recruiter | Monday 08:00 UTC |
| Agent 15 Nurturer | Daily 09:00 UTC |
| Agent 9 Monitor | Friday 08:00 UTC |
| Agent 1 Broadcaster | Tue/Fri/Sat/Sun 22:30 UTC |
| Agent 2 Scout | Every 6 hours |
| Agent 4 Content | Wednesday 07:00 UTC |
| Agent 10 Referral | Daily 06:00 UTC |
| Agent 14 Beat the Bot | Pre-GW Fri/Sat, Post-GW Tue/Wed |
| Bench agents (6,7,8,11,12) | Weekly per agent |

---

## Credentials

See [CREDENTIALS.md](CREDENTIALS.md) for the full breakdown of what's needed now vs later.

**Minimum to get started:**

| Key | Where |
|-----|-------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `DATABASE_URL` | `postgresql://fantopy:changeme@localhost:5432/fantopy` (local Docker) |

---

## Pending from platform team

See [MARCUS_SPEC.md](MARCUS_SPEC.md) for the exact fields needed from Marcus to complete Agent 1 (Broadcaster).

Outstanding:
- `FANTOPY_API_BASE_URL` + `FANTOPY_API_KEY`
- `MCP_GATEWAY_SSE_URL`
- Moltbook API key + endpoint docs

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| LLM | Claude Sonnet via Anthropic API |
| Database | PostgreSQL 15 (Docker) |
| Scheduling | GitHub Actions cron |
| Email | Resend SDK |
| Twitter | Tweepy v4 |
| Reddit | PRAW |
| GitHub search | PyGithub |
| Discord | discord.py + webhooks |
| Google Sheets | gspread |
| Dashboard | Streamlit |
| Blockchain | Solana (solders) — Agent 10 |
