# Marketing Pipeline Plugin for Claude Code, Codex, and OpenCode

An autonomous multi-agent marketing pipeline that orchestrates 9+ specialized AI agents to produce complete marketing campaigns — from research through content creation, motion graphics video production, AI-generated images and video clips, SEO optimization, and quality review — all from a single command. Supports both **one-shot** pipelines (run once, done) and **sustained** campaigns (auto-generate content on a recurring schedule for weeks/months).

This repo now ships client surfaces for:

- **Claude Code** via `.claude-plugin/` and `/marketing` command files
- **Codex** via `.codex-plugin/plugin.json` and `skills/marketing-pipeline/SKILL.md`
- **OpenCode** via `plugins/marketing-pipeline.js` (repo plugin auto-load) and optional global plugin registration

## What It Does

You give it a campaign brief. It autonomously:

1. **Researches** your market, competitors, and trends (3 agents in parallel)
2. **Synthesizes** a marketing strategy with detailed buyer personas
3. **Creates content** — blog posts, social media, email sequences, landing pages (4 agents in parallel)
4. **Produces videos** — product launch hero, social media clip, and animated stats video using [Remotion](https://github.com/remotion-dev/remotion)
5. **Generates AI visuals** — hero banners, social graphics, blog headers, and product teaser video using [Gemini API](https://ai.google.dev/gemini-api/docs) (Imagen + Veo 2)
6. **Optimizes for SEO** — keyword research, on-page recommendations, link building strategy
6. **Reviews everything** — quality assessment + sales alignment review (2 agents in parallel)
7. **Compiles** an executive summary with prioritized action items

All while showing real-time progress on a terminal-themed web dashboard.

## Output Example

A single `/marketing campaign` run produces **21-23 deliverables** — text content, motion graphics videos, and AI-generated visuals:

```
marketing-output/your-campaign-slug/
├── 00-brief/campaign-brief.md
├── 01-research/
│   ├── market-analysis.md          (~1,000 lines)
│   ├── competitive-intelligence.md (~560 lines)
│   └── trend-analysis.md           (~830 lines)
├── 02-strategy/
│   ├── marketing-strategy.md       (~740 lines)
│   └── target-audience.md          (~920 lines)
├── 03-content/
│   ├── blog-posts/                 (~170 lines)
│   ├── social-media/               (~310 lines)
│   ├── email-campaigns/            (~330 lines)
│   ├── landing-pages/              (~300 lines)
│   ├── videos/
│   │   ├── product-hero.mp4        (30s, 1920x1080)
│   │   ├── social-clip.mp4         (15s, 1080x1080)
│   │   └── stats-video.mp4         (20s, 1920x1080)
│   └── media/
│       ├── hero-banner.png         (1920x1080, AI-generated)
│       ├── social-graphic.png      (1080x1080, AI-generated)
│       ├── blog-header.png         (1920x1080, AI-generated)
│       └── product-teaser.mp4      (720p, 8s, AI-generated)
├── 04-seo/
│   ├── keyword-research.md         (~580 lines)
│   └── seo-recommendations.md      (~980 lines)
├── 05-review/
│   ├── quality-review.md           (~680 lines)
│   └── sales-alignment.md          (~430 lines)
├── 06-final/
│   └── executive-summary.md
├── README.md
├── pipeline-dashboard.html
└── pipeline-status.json
```

## Installation

### Client Support

| Client | Integration Surface | Notes |
|--------|---------------------|-------|
| Claude Code | `.claude-plugin/` + `commands/*.md` | Full slash-command surface |
| Codex | `.codex-plugin/plugin.json` + `skills/marketing-pipeline/` | Skill-driven plugin packaging |
| OpenCode | `plugins/marketing-pipeline.js` | Auto-loads when OpenCode runs in this repo |

### Quick Install

```bash
# 1. Copy plugin to Claude Code plugins directory
mkdir -p ~/.claude/plugins/local/
cp -r marketing-pipeline-plugin ~/.claude/plugins/local/marketing-pipeline

# 2. Register the plugin
# Add to ~/.claude/plugins/installed_plugins.json:
```

Add this entry to `~/.claude/plugins/installed_plugins.json` (create the file if it doesn't exist):

```json
{
  "marketing-pipeline@local": [
    {
      "scope": "user",
      "installPath": "~/.claude/plugins/local/marketing-pipeline",
      "version": "1.0.0",
      "installedAt": "2026-01-01T00:00:00.000Z",
      "lastUpdated": "2026-01-01T00:00:00.000Z"
    }
  ]
}
```

```bash
# 3. Enable the plugin in Claude Code settings
# Add to ~/.claude/settings.json under "enabledPlugins":
```

Add this to `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "marketing-pipeline@local": true
  }
}
```

### Verify Installation

Restart Claude Code, then type:

```
/marketing
```

You should see the help text with available commands.

### Codex

This repo includes a Codex plugin manifest at `.codex-plugin/plugin.json` and a repo-scoped skill at `skills/marketing-pipeline/SKILL.md`.

To register it as a local Codex plugin:

1. Symlink or copy the repo to `~/plugins/marketing-pipeline`
2. Add a local marketplace entry in `~/.agents/plugins/marketplace.json`
3. Restart Codex

Example marketplace entry:

```json
{
  "name": "local-plugins",
  "interface": {
    "displayName": "Local Plugins"
  },
  "plugins": [
    {
      "name": "marketing-pipeline",
      "source": {
        "source": "local",
        "path": "./plugins/marketing-pipeline"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

### OpenCode

This repo includes `plugins/marketing-pipeline.js`. OpenCode automatically scans repo plugins from `plugin/*.js` and `plugins/*.js`, so opening this repo in OpenCode is enough to load the project-specific context plugin.

Optional global registration can be added in `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": [
    "/absolute/path/to/marketing-pipeline-plugin/plugins/marketing-pipeline.js"
  ]
}
```

## Commands

### One-Shot Pipelines

| Command | Description | Agents | Stages |
|---------|-------------|--------|--------|
| `/marketing campaign <brief>` | Full-funnel campaign | 9 agents | 6 stages |
| `/marketing content <topic>` | Content production only | 4 agents | 5 stages |
| `/marketing research <topic>` | Market intelligence only | 5 agents | 4 stages |
| `/marketing status` | Check pipeline progress | — | — |

### Sustained (Long-Running) Campaigns

| Command | Description |
|---------|-------------|
| `/marketing sustain create <brief>` | Create recurring campaign with content calendar + scheduler |
| `/marketing sustain list` | List all sustained campaigns with status |
| `/marketing sustain status <slug>` | Detailed campaign status + upcoming calendar |
| `/marketing sustain run <slug>` | Manually trigger next content batch |
| `/marketing sustain pause <slug>` | Pause scheduled execution |
| `/marketing sustain resume <slug>` | Resume scheduled execution |
| `/marketing sustain delete <slug>` | Delete campaign and scheduler |
| `/marketing sustain calendar <slug>` | View full content calendar |
| `/marketing sustain refresh <slug>` | Force strategy refresh on next batch |
| `/marketing sustain history <slug>` | View batch execution history |

### Shortcut Commands

| Command | Same As |
|---------|---------|
| `/marketing-campaign <brief>` | `/marketing campaign <brief>` |
| `/marketing-content <topic>` | `/marketing content <topic>` |
| `/marketing-research <topic>` | `/marketing research <topic>` |
| `/marketing-status` | `/marketing status` |
| `/marketing-sustain <subcommand>` | `/marketing sustain <subcommand>` |

## Usage Examples

### Full Campaign

```
/marketing campaign Launch an AI-powered project management tool for remote teams
```

This runs all 6 stages with 7 agents and produces the complete deliverable set.

### Content Only

```
/marketing content How zero-trust architecture is transforming cloud security in 2026
```

Faster pipeline focused on content production — blog post, social media pack, email sequence, landing page, plus SEO optimization.

### Market Research

```
/marketing research The enterprise observability platform market in 2026
```

Deep research mode — market analysis, competitive intelligence, and trend analysis, synthesized into strategic recommendations.

### Sustained Campaign

```
/marketing sustain create Weekly content marketing for our AI SaaS product launch
```

Creates a long-running campaign: runs research + strategy once, generates a content calendar (e.g. 12 weekly batches), and installs a macOS launchd scheduler. Each week, it auto-runs Claude Code headlessly to produce a fresh content batch (blog post, social media, email) based on the calendar.

```
/marketing sustain status my-campaign-slug
```

Check detailed progress, upcoming calendar entries, and batch history.

### Check Status

```
/marketing status
```

Shows progress of any running or completed pipelines. If the dashboard server is running, provides the URL.

## Pipeline Architecture

### Full Funnel Pipeline

```
Stage 1: Setup
    └── Create directories, write brief

Stage 2: Research (PARALLEL)
    ├── Market Researcher ──────→ market-analysis.md
    ├── Competitive Analyst ────→ competitive-intelligence.md
    └── Trend Analyst ──────────→ trend-analysis.md

Stage 3: Strategy (SEQUENTIAL)
    └── Orchestrator synthesizes → marketing-strategy.md + target-audience.md

Stage 4: Content + SEO + Video + Media (PARALLEL)
    ├── Content Marketer ───────→ blog, social, email, landing page
    ├── SEO Specialist ─────────→ keyword-research.md + seo-recommendations.md
    ├── Video Producer ─────────→ product-hero.mp4, social-clip.mp4, stats-video.mp4
    └── Media Producer ─────────→ hero-banner.png, social-graphic.png, blog-header.png, product-teaser.mp4

Stage 5: Review (PARALLEL)
    ├── Business Analyst ───────→ quality-review.md
    └── Sales Engineer ─────────→ sales-alignment.md

Stage 6: Final (SEQUENTIAL)
    └── Orchestrator compiles ──→ executive-summary.md + README.md
```

Agents within the same stage run **in parallel**. Stages run **sequentially** (each stage waits for the previous to complete).

### Sustained Campaign Pipeline

```
/marketing sustain create <brief>
         │
         ▼
   ┌─────────────┐
   │  INIT PHASE  │  (runs once, interactively)
   │              │
   │  1. Setup    │  Create campaign directory tree
   │  2. Research │  4 parallel agents (market, competitive, trends, social)
   │  3. Strategy │  Synthesize marketing strategy document
   │  4. Calendar │  Generate themed content plan for all N batches
   │  5. Config   │  Write config + install macOS launchd scheduler
   └──────┬──────┘
          │
          ▼  launchd fires on schedule (daily/weekly/bi-weekly/monthly)
   ┌─────────────┐
   │ BATCH RUNS   │  (headless, unattended — repeats N times)
   │              │
   │  1. Setup    │  Create batch directory, read calendar entry
   │  2. Research │  2 agents scoped to this batch's theme
   │  3. Content  │  Blog post + social media + email from calendar brief
   │  4. SEO      │  Review and optimize content
   │  5. Compile  │  Write deliverables, update state
   └──────┬──────┘
          │
          ▼  every N batches
   Strategy refresh: re-run research, update strategy, regenerate pending calendar entries

          │
          ▼  after all batches complete
   Campaign auto-completes
```

**Campaign data structure:**

```
~/.marketing-pipeline/campaigns/{slug}/
  campaign-config.json      # Immutable settings (cadence, total batches)
  campaign-state.json       # Mutable state (current batch, status, last run)
  content-calendar.json     # Themed entries with angles, keywords, tone per batch
  batch-history.json        # Log of each batch result
  run-batch.sh              # Shell script invoked by launchd
  foundation/
    01-research/            # Initial research outputs
    02-strategy/            # Marketing strategy (refreshed every N batches)
  batches/
    batch-001/              # Content from batch 1
    batch-002/              # Content from batch 2
    ...
  logs/
    batch-001.log           # Execution log per batch
```

### Agent Roster

| Agent | Type | Model | Role |
|-------|------|-------|------|
| Market Researcher | market-researcher | haiku | Market sizing, trends, buyer behavior |
| Competitive Analyst | competitive-analyst | haiku | Competitor features, pricing, SWOT |
| Trend Analyst | trend-analyst | haiku | Macro trends, technology shifts |
| Content Marketer | content-marketer | haiku | Blog, social, email, landing pages |
| SEO Specialist | seo-specialist | haiku | Keywords, on-page SEO, link strategy |
| Video Producer | general-purpose | sonnet | Motion graphics videos via Remotion (product hero, social clip, stats) |
| Media Producer | gemini-media-producer | sonnet | AI-generated images + video via Qwen, Wan, and Gemini models |
| Business Analyst | business-analyst | sonnet | Quality review, gap analysis |
| Sales Engineer | sales-engineer | sonnet | Sales readiness, competitive positioning |
| Orchestrator | marketing-orchestrator | opus | Coordinates all agents, synthesizes strategy |

## Live Dashboard

Every pipeline run automatically opens a real-time web dashboard in your browser.

**Features:**
- Terminal/hacker aesthetic with green accent
- Real-time progress bar and stage pipeline visualization
- Gantt-style timeline showing stage durations
- Agent cards with status, duration, description, and deliverable tracking
- File tree of all deliverables with completion status
- Color-coded activity log
- System stats footer
- Completion celebration with confetti effect

The dashboard polls `pipeline-status.json` every 2.5 seconds and requires no external dependencies — it's a single self-contained HTML file served by Python's built-in HTTP server.

**Dashboard URL:** `http://localhost:8847/pipeline-dashboard.html`

## File Structure

```
marketing-pipeline/
├── .codex-plugin/
│   └── plugin.json              # Codex plugin metadata
├── .claude-plugin/
│   └── plugin.json              # Plugin metadata and registration
├── agents/
│   ├── marketing-orchestrator.md # Core orchestrator (opus model)
│   └── gemini-media-producer.md  # AI media generation agent (Qwen + Wan + Gemini)
├── skills/
│   └── marketing-pipeline/
│       └── SKILL.md             # Codex skill surface for repo workflows
├── plugins/
│   └── marketing-pipeline.js    # OpenCode repo plugin
├── commands/
│   ├── marketing.md             # Main router command
│   ├── marketing-campaign.md    # Full funnel shortcut
│   ├── marketing-content.md     # Content production shortcut
│   ├── marketing-research.md    # Market intelligence shortcut
│   ├── marketing-status.md      # Pipeline status checker
│   └── marketing-sustain.md     # Sustained campaign shortcut
└── assets/
    ├── pipeline-dashboard.html  # Real-time monitoring dashboard (sustained panel included)
    ├── sustain/                  # Sustained campaign templates
    │   ├── plist-template.xml   # macOS launchd schedule template
    │   └── run-batch-template.sh # Headless batch runner template
    ├── gemini-media/             # AI media generation via Qwen + Wan + Gemini
    │   ├── generate_media.py    # Image + video generation script
    │   └── requirements.txt     # Python deps (google-genai)
    └── remotion-template/       # Video generation template project
        ├── package.json
        ├── tsconfig.json
        ├── render.mjs           # Render script (bundles & renders all 3 videos)
        └── src/
            ├── index.ts
            ├── Root.tsx         # 3 compositions: ProductHero, SocialClip, StatsVideo
            ├── types.ts
            └── components/
                ├── ProductHero.tsx
                ├── SocialClip.tsx
                ├── StatsVideo.tsx
                └── common/      # AnimatedText, ProgressBar, Background
```

## Requirements

- **Claude Code**, **Codex**, or **OpenCode**
- **Python 3** (for the dashboard HTTP server — pre-installed on macOS/Linux)
- **Node.js 18+** (for Remotion video rendering)
- **`GEMINI_API_KEY`** environment variable (for AI image/video generation via Gemini API — get one at [ai.google.dev](https://ai.google.dev/))
- **Subagent types** must be available: market-researcher, competitive-analyst, trend-analyst, content-marketer, seo-specialist, business-analyst, sales-engineer. These come from the [awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) collection or can be custom `.md` files in `~/.claude/agents/`.
- **macOS** (for sustained campaigns — uses launchd for scheduling. Linux users can substitute cron.)

## How It Works Internally

1. You run `/marketing campaign <brief>`
2. The `marketing.md` command parses your input and launches the `marketing-orchestrator` agent via the Task tool
3. The orchestrator (running on Opus) executes the pipeline autonomously:
   - Creates output directories and campaign brief
   - Copies the dashboard HTML and starts an HTTP server
   - Writes `pipeline-status.json` and opens the dashboard in your browser
   - Spawns specialized agents in parallel where possible using multiple Task tool calls
   - Waits for each stage to complete before starting the next
   - Updates `pipeline-status.json` at every stage transition (dashboard polls this)
   - After all stages complete, writes the executive summary and kills the HTTP server
4. You get a completion report with all deliverables listed

## Customization

### Adding New Agent Types

Edit `agents/marketing-orchestrator.md` to add new agents to specific stages. For example, to add a PR specialist:

1. Create `~/.claude/agents/pr-specialist.md` with the agent definition
2. Add the agent to a stage in the orchestrator's pipeline instructions
3. Update the pipeline-status.json schema if adding new stages

### Changing Models

Agent models are configured in `agents/marketing-orchestrator.md`. The orchestrator uses Opus for complex synthesis tasks; sub-agents use Haiku (faster/cheaper) or Sonnet (for review tasks requiring more judgment).

### Custom Output Structure

Modify the output directory structure in `agents/marketing-orchestrator.md` under the "OUTPUT DIRECTORY STRUCTURE" section.

## Known Limitations

- **Read-only agents**: Some subagent types (market-researcher, competitive-analyst, trend-analyst) may not have Write tool access. The orchestrator works around this by using `general-purpose` subagent type when file writing is required.
- **Long-running**: A full-funnel campaign takes significant time due to the depth of content produced. Content + SEO + Video stage is typically the longest.
- **Video rendering**: Remotion requires Node.js 18+ and will auto-download Chromium on first run (~180MB). Video rendering is CPU-intensive and may take several minutes per video.
- **Port 8847**: The dashboard uses a fixed port. If it's already in use, the server won't start.
- **Single pipeline**: Only one pipeline can run at a time (due to the fixed dashboard port).

## License

MIT
