# Marketing Pipeline Plugin Codebase Index

Indexed on 2026-04-05.

## Scope

This index covers the first-party code and project fixtures in this repository:

- plugin metadata and top-level docs
- slash command definitions
- agent definitions
- local asset scripts and UI
- cloud API, SDK, and database schema
- example and fixture outputs used to exercise the pipeline

This index does not expand vendored or dependency-heavy trees in detail:

- `.git/`
- `cloud/api/node_modules/`
- `cloud/sdk/node_modules/`
- `cloud/self-hosted/supabase/` (vendored upstream Supabase repo)
- binary media outputs (`.png`, `.mp4`) beyond their role in the pipeline
- `.env` secret values (only variable names were inspected)

## What The Project Is

`marketing-pipeline-plugin` is a Claude Code plugin that turns `/marketing ...` commands into autonomous marketing workflows. The core pattern is:

1. Slash command routes to `marketing-orchestrator`
2. Orchestrator creates a campaign workspace and `pipeline-status.json`
3. Research/strategy/content/review/media/distribution agents run in staged parallel batches
4. The dashboard reads local JSON files or cloud state to show progress
5. Optional cloud sync mirrors status and deliverables to Supabase

## Top-Level Map

| Path | Role |
| --- | --- |
| `README.md` | Main product overview, modes, outputs, install summary |
| `ARCHITECTURE.md` | Detailed pipeline architecture, stages, agent roster, output structure |
| `INSTALL.md` | Local plugin setup, command registration, cloud/distribution setup |
| `SESSION-NOTES.md` | Short note about dashboard redesign work |
| `.claude-plugin/plugin.json` | Plugin identity metadata |
| `commands/` | Slash command entrypoints |
| `agents/` | Agent prompts/instructions used by the pipeline |
| `assets/` | Dashboard UI, helper scripts, Remotion template, sustain templates |
| `cloud/` | Optional collaboration backend: API server, SDK, schema, docs |
| `examples/` | Small sample output snapshot |
| `test-content-gen/` | Local content-generation fixture outputs |
| `test-social-research/` | Local social research fixture output |

## Runtime Entry Points

### User-facing commands

| File | Purpose |
| --- | --- |
| `commands/marketing.md` | Main router for campaign/content/research/status/cloud/teams/distribution/approve/browse/share/sustain flows |
| `commands/marketing-campaign.md` | Full-funnel run entrypoint |
| `commands/marketing-content.md` | Content-only run entrypoint |
| `commands/marketing-research.md` | Research-only run entrypoint |
| `commands/marketing-status.md` | Local status inspection command |
| `commands/marketing-sustain.md` | Shortcut wrapper for sustained-campaign subcommands |

### Primary orchestration

| File | Purpose |
| --- | --- |
| `agents/marketing-orchestrator.md` | Main controller; defines all pipeline modes, stage order, dashboard updates, approval gate, distribution handoff, sustained campaign logic, and cloud sync hooks |

## Command And Agent Layer

### Agent definitions

| File | Purpose |
| --- | --- |
| `agents/marketing-orchestrator.md` | Core orchestrator for full-funnel, content-production, market-intelligence, sustained init, sustained batch |
| `agents/social-researcher.md` | Social listening workflow using Reddit/Twitter/Telegram scraping and sentiment synthesis |
| `agents/gemini-media-producer.md` | Builds `media-brief.json`, runs Gemini image/video generation, verifies outputs |
| `agents/distribution-agent.md` | Reads approvals, adapts content per platform, runs distribution helper, writes distribution report |
| `agents/web-scraper.md` | Generic scraping specialist for static/dynamic sites and structured extraction |

### Key orchestrator behaviors

`agents/marketing-orchestrator.md` is the highest-value file in the repo. It defines:

- full-funnel pipeline with 8 stages: setup, research, strategy, content, review, final, approval, distribution
- content-production and market-intelligence reduced pipelines
- sustained campaign initialization with content calendar generation and scheduler config
- sustained batch execution with optional strategy refresh after N batches
- local dashboard boot/shutdown behavior on port `8847`
- `pipeline-status.json` schema and update points
- optional Supabase cloud sync calls after status and deliverable writes

## Assets And Local Tooling

### Dashboard and indexing

| File | Purpose |
| --- | --- |
| `assets/pipeline-dashboard.html` | Large single-file dashboard app; renders hub, wizard, monitor, storage, review, staging, calendar, social, history, brainstorm views; supports local-file mode and Supabase-backed cloud mode |
| `assets/generate-storage-index.js` | Scans local `marketing-output/` and sustained batch directories, builds `assets/storage-index.json` for the dashboard storage/research view |
| `assets/storage-index.json` | Generated storage index snapshot for the dashboard |

`assets/pipeline-dashboard.html` contains:

- Obsidian-style workspace shell with sidebar/tab/status bars
- local and cloud data adapters
- campaign hub and wizard UI
- monitor/history/staging/review/storage flows
- approval actions hitting `/api/approval/...`
- distribution config/test actions hitting `/api/distribution/...`
- brainstorm view that reuses stored research/media as input context

### Distribution helpers

| File | Purpose |
| --- | --- |
| `assets/distribution/distribute.js` | Node-only poster for Reddit, Twitter/X, Telegram, Discord; validates content, signs OAuth requests, uploads media, writes `distribution-results.json` |
| `assets/distribution/approval-poll.js` | Polls `approval-status.json` until approved/rejected/timeout and returns machine-readable result |

`assets/distribution/distribute.js` includes:

- zero-dependency HTTP helpers
- safe JSON parsing and URL/token sanitization
- media path traversal protection
- Reddit OAuth password grant + self-post submission
- Twitter OAuth 1.0a signing, thread posting, multipart media upload, partial-failure handling
- Telegram photo + HTML message send flow
- Discord webhook embed/file posting

### Media generation

| File | Purpose |
| --- | --- |
| `assets/gemini-media/generate_media.py` | Reads `media-brief.json`, calls Gemini models, writes images/videos plus `media-manifest.json` |
| `assets/gemini-media/requirements.txt` | Python dependency hint |

`generate_media.py`:

- reads `GEMINI_API_KEY` or `GOOGLE_API_KEY`
- generates images with `gemini-2.0-flash-exp`
- generates videos with `veo-2.0-generate-001`
- polls long-running video operations
- writes outputs into the parent media directory

### Social research utilities

| File | Purpose |
| --- | --- |
| `assets/social-research/social_scrape_utils.py` | Standard-library-only helpers for Reddit, Twitter/X, and Telegram scraping plus credential loading |

`social_scrape_utils.py` provides:

- resilient HTTP helpers with retry/backoff
- `RedditScraper` for OAuth or public JSON API search/comments/hot posts
- `TwitterScraper` for OAuth 1.0a recent search or public search hints
- `TelegramScraper` for public channel scraping via `t.me/s/...`
- `load_credentials()` for `~/.marketing-pipeline/distribution.json`

### Sustained campaign templates

| File | Purpose |
| --- | --- |
| `assets/sustain/run-batch-template.sh` | Headless batch runner template for macOS `launchd`; reads campaign config/state, skips paused/completed runs, handles bi-weekly cadence, invokes Claude Code |
| `assets/sustain/plist-template.xml` | `launchd` plist template for scheduling recurring runs |

### Remotion video template

| File | Purpose |
| --- | --- |
| `assets/remotion-template/package.json` | Remotion project dependencies and render scripts |
| `assets/remotion-template/render.mjs` | Bundles the template and renders three videos from `props.json` |
| `assets/remotion-template/src/index.ts` | Remotion root registration |
| `assets/remotion-template/src/Root.tsx` | Declares three compositions and default props |
| `assets/remotion-template/src/types.ts` | Shared prop types |
| `assets/remotion-template/src/components/ProductHero.tsx` | 30s widescreen product hero sequence |
| `assets/remotion-template/src/components/SocialClip.tsx` | 15s square social clip sequence |
| `assets/remotion-template/src/components/StatsVideo.tsx` | 20s stats-driven sequence |
| `assets/remotion-template/src/components/common/AnimatedText.tsx` | Text animation primitive |
| `assets/remotion-template/src/components/common/Background.tsx` | Animated glow/grid background |
| `assets/remotion-template/src/components/common/ProgressBar.tsx` | Animated stats progress bar |

## Cloud Subsystem

### Docs and shell

| File | Purpose |
| --- | --- |
| `cloud/README.md` | Cloud architecture, setup, API reference, CLI flows |
| `cloud/test-cloud.sh` | Local cloud testing helper script |

### API server

| File | Purpose |
| --- | --- |
| `cloud/api/server.js` | Express app bootstrap, Supabase client init, CORS, security headers, route mounting, health endpoint, graceful shutdown |
| `cloud/api/middleware/auth.js` | API key auth and team-membership middleware |
| `cloud/api/routes/auth.js` | user registration, identity lookup, API key rotation |
| `cloud/api/routes/teams.js` | team creation, listing, membership, invites, join, remove-member |
| `cloud/api/routes/campaigns.js` | campaign CRUD-lite, status sync, deliverable upload/download |
| `cloud/api/routes/distribution.js` | read/write/test local distribution credentials through API |
| `cloud/api/routes/approval.js` | approval state read/update and sync back to local `approval-status.json` |
| `cloud/api/package.json` | API dependencies |

Important API behaviors:

- uses Supabase service role key on the server
- authenticates callers via `x-api-key`
- gates team and campaign access server-side even though RLS also exists
- stores distribution credentials on local disk under `~/.marketing-pipeline/distribution.json`
- supports cloud review/approval flow by storing `approval_status` on campaigns

### SDK

| File | Purpose |
| --- | --- |
| `cloud/sdk/index.js` | Local Node SDK for cloud detection, campaign creation, status sync, deliverable upload, approval sync, campaign listing |
| `cloud/sdk/package.json` | SDK dependency declaration |

### Database schema

| File | Purpose |
| --- | --- |
| `cloud/supabase/migrations/001_initial.sql` | Creates users, teams, team_members, campaigns, deliverables, invitations, helper functions, RLS policies, realtime publication, storage bucket, update triggers |
| `cloud/supabase/migrations/002_approval.sql` | Adds `awaiting_approval` status and `approval_status` JSONB to campaigns |

### Vendored self-hosted tree

`cloud/self-hosted/supabase/` is present as a vendored upstream Supabase workspace. It is not project-specific application logic and was not indexed file-by-file.

## Docs And Metadata

| File | Purpose |
| --- | --- |
| `.claude-plugin/plugin.json` | Declares plugin name and description |
| `.gitignore` | Excludes env, media outputs, tests, generated storage index, vendored/self-hosted tree |
| `README.md` | Product-level overview and quick install |
| `ARCHITECTURE.md` | Architectural deep dive |
| `INSTALL.md` | Operational install/config docs |
| `SESSION-NOTES.md` | Brief session changelog |

## Config And Secrets

| File | Purpose |
| --- | --- |
| `.env` | Local secret config; inspected key name: `GEMINI_API_KEY` |

Runtime paths outside the repo that the code expects:

- `~/.claude/plugins/local/marketing-pipeline/`
- `~/.claude/commands/`
- `~/.marketing-pipeline/distribution.json`
- `~/.marketing-pipeline/cloud.json`
- `~/.marketing-pipeline/campaigns/`
- `~/marketing-output/`

## Example And Fixture Data

### Example snapshot

| File | Purpose |
| --- | --- |
| `examples/sample-output/README.md` | Describes a representative completed campaign run |
| `examples/sample-output/pipeline-status.json` | Sample final status payload used to preview the dashboard |

### Social research fixture

| File | Purpose |
| --- | --- |
| `test-social-research/01-research/social-listening.md` | Example social listening report output |

### Content generation fixture

`test-content-gen/fantopy-ai-marketing/` is a realistic generated-output sandbox. It contains:

- `02-strategy/marketing-strategy.md`
- `03-content/` with blog, social, email, landing page, media manifest, image assets, rendered videos
- `04-seo/` with keyword research and SEO recommendations
- `approval-status.json`
- `pipeline-status.json`
- `pipeline-dashboard.html`

It also contains a nested full output bundle under:

- `test-content-gen/fantopy-ai-marketing/marketing-output/fantopy-user-onboarding/`

That nested fixture includes:

- `00-brief/`
- `01-research/`
- `02-strategy/`
- `03-content/`
- `04-seo/`
- `05-review/`
- `06-final/`
- `07-distribution/`
- `README.md`
- `approval-status.json`
- `pipeline-dashboard.html`
- `pipeline-status.json`

These fixtures are useful as reference outputs, not as executable source.

## Codebase Relationships

### Local-only flow

1. Command file routes to `marketing-orchestrator`
2. Orchestrator creates campaign directories and status JSON
3. Specialized agents write markdown/media outputs
4. Dashboard reads `pipeline-status.json`, `approval-status.json`, and `assets/storage-index.json`
5. Distribution helpers post approved content to platforms

### Cloud-enabled flow

1. Orchestrator calls `cloud/sdk/index.js`
2. SDK creates/syncs campaign records and deliverables in Supabase
3. Dashboard enters cloud mode via query params and uses Supabase realtime plus API endpoints
4. Approval/distribution UI writes decisions and config through `cloud/api/`

## Highest-Leverage Files To Read First

If you need to re-enter this repo quickly, start here:

1. `README.md`
2. `ARCHITECTURE.md`
3. `agents/marketing-orchestrator.md`
4. `assets/pipeline-dashboard.html`
5. `assets/distribution/distribute.js`
6. `cloud/api/server.js`
7. `cloud/api/routes/campaigns.js`
8. `cloud/sdk/index.js`
9. `cloud/supabase/migrations/001_initial.sql`

## Current State

- Git worktree was clean when indexed.
- Core first-party logic is concentrated in markdown agent specs, the dashboard HTML app, helper scripts, and the optional cloud layer.
- The repo mixes product code with generated output fixtures, so any future automated indexing should keep source and fixtures separate.
