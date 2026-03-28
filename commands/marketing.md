---
description: Run autonomous marketing pipelines - campaigns, content production, or market research
argument-hint: "<campaign|content|research|status> <brief or topic>"
---

# Marketing Pipeline

You are the entry point for the marketing pipeline system. Parse the user's command and route to the appropriate pipeline mode.

## Arguments

Raw arguments: $ARGUMENTS

## Routing Logic

Parse the first word of $ARGUMENTS to determine the mode:

### If first word is "campaign"
Launch the **marketing-orchestrator** agent using the Task tool:
- subagent_type: "marketing-orchestrator"
- prompt: "Run a FULL FUNNEL marketing pipeline for the following campaign brief: [remaining arguments after 'campaign']. Pipeline mode: full-funnel. Execute autonomously and deliver all outputs to ./marketing-output/[slugified-campaign-name]/"

### If first word is "content"
Launch the **marketing-orchestrator** agent using the Task tool:
- subagent_type: "marketing-orchestrator"
- prompt: "Run a CONTENT PRODUCTION marketing pipeline for the following topic: [remaining arguments after 'content']. Pipeline mode: content-production. Execute autonomously and deliver all outputs to ./marketing-output/[slugified-topic-name]/"

### If first word is "research"
Launch the **marketing-orchestrator** agent using the Task tool:
- subagent_type: "marketing-orchestrator"
- prompt: "Run a MARKET INTELLIGENCE pipeline for the following topic: [remaining arguments after 'research']. Pipeline mode: market-intelligence. Execute autonomously and deliver all outputs to ./marketing-output/[slugified-topic-name]/"

### If first word is "status"
Check pipeline status:
1. Look for any `./marketing-output/` directories and list them
2. For each, check which files exist to determine progress
3. Report which stages are complete vs pending

### If first word is "cloud"

Parse the second word:

**`/marketing cloud setup`** — Interactive Supabase configuration:
1. Ask the user for their Supabase project URL and anon key (or check if self-hosted)
2. Ask for their API key (obtained from `/marketing cloud register` or the API server)
3. Write config to `~/.marketing-pipeline/cloud.json`:
   ```json
   {
     "supabase_url": "https://xxx.supabase.co",
     "supabase_anon_key": "eyJ...",
     "active_team_id": null
   }
   ```
4. Set `MARKETING_CLOUD_API_KEY` env var reminder
5. Test connection using the SDK: `const cloud = require('~/.claude/plugins/local/marketing-pipeline/cloud/sdk'); await cloud.init();`

**`/marketing cloud status`** — Show current cloud connection info:
1. Read `~/.marketing-pipeline/cloud.json`
2. Check if `MARKETING_CLOUD_API_KEY` is set
3. Try `cloud.init()` and report success/failure
4. Show active team ID if set

**`/marketing cloud register`** — Register a new user:
1. Ask for email and display name
2. POST to the API server `/api/auth/register`
3. Return the API key with instructions to set `MARKETING_CLOUD_API_KEY`

### If first word is "teams"

Parse the second word:

**`/marketing teams list`** — List user's teams:
1. Init cloud SDK, call API `GET /api/teams`
2. Display teams with roles

**`/marketing teams create <name>`** — Create a new team:
1. Init cloud SDK, call API `POST /api/teams` with name
2. Display team info and set as active team in config

**`/marketing teams invite <email>`** — Invite someone to active team:
1. Init cloud SDK, call API `POST /api/teams/:teamId/invite` with email
2. Display the invitation token and join command

**`/marketing teams join <token>`** — Accept a team invitation:
1. Init cloud SDK, call API `POST /api/teams/join` with token
2. Display success and team info

**`/marketing teams switch <team-id>`** — Switch active team:
1. Update `active_team_id` in `~/.marketing-pipeline/cloud.json`
2. Confirm the switch

**`/marketing teams members`** — List members of active team:
1. Init cloud SDK, call API `GET /api/teams/:teamId/members`
2. Display members with roles

### If first word is "share"

**`/marketing share <slug>`** — Upload a completed local campaign to cloud:
1. Check cloud is configured and has active team
2. Read `./marketing-output/<slug>/pipeline-status.json`
3. Create campaign record via `cloud.createCampaign()`
4. Sync status via `cloud.syncStatus()`
5. Find all deliverable files in `./marketing-output/<slug>/`
6. Upload each via `cloud.uploadDeliverable()`
7. Report upload summary

### If first word is "browse"

**`/marketing browse`** — List team campaigns from cloud:
1. Init cloud SDK
2. Call `cloud.listCampaigns()` for active team
3. Display campaigns with status, dates, and dashboard URLs
4. For each campaign, show: `http://localhost:8847/pipeline-dashboard.html?cloud=1&campaign_id=<id>&supabase_url=<url>&supabase_key=<key>`

### If no arguments or unrecognized
Display this help:

```
Marketing Pipeline - Autonomous Marketing Orchestration

Usage:
  /marketing campaign <brief>   - Full funnel: Research -> Strategy -> Content -> SEO -> Review
  /marketing content <topic>    - Content production: Blog posts, social media, landing pages, emails
  /marketing research <topic>   - Market intelligence: Market analysis, competitive intel, trends
  /marketing status             - Check pipeline progress

Cloud & Collaboration:
  /marketing cloud setup        - Configure Supabase cloud backend
  /marketing cloud status       - Show cloud connection info
  /marketing cloud register     - Register a new cloud account
  /marketing teams list         - List your teams
  /marketing teams create <n>   - Create a new team workspace
  /marketing teams invite <e>   - Invite a team member by email
  /marketing teams join <token> - Accept a team invitation
  /marketing teams switch <id>  - Switch active team
  /marketing teams members      - List team members
  /marketing share <slug>       - Upload a local campaign to cloud
  /marketing browse             - Browse team campaigns from cloud

Examples:
  /marketing campaign Launch our new AI-powered analytics product targeting enterprise CTOs
  /marketing content How zero-trust architecture is transforming cloud security
  /marketing research The enterprise observability platform market in 2026
  /marketing cloud setup
  /marketing teams create "My Agency"
  /marketing share ai-powered-analytics-launch
  /marketing browse
```

## Important
- Always launch the marketing-orchestrator agent for campaign, content, and research modes
- Pass the full brief/topic text exactly as provided
- The orchestrator handles all agent coordination autonomously
- Do not attempt to run the pipeline yourself — delegate entirely to the orchestrator
- Cloud commands (cloud, teams, share, browse) are handled directly — do NOT delegate to the orchestrator
- For cloud commands, use the SDK at `~/.claude/plugins/local/marketing-pipeline/cloud/sdk`
