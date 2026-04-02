# Marketing Pipeline Architecture

## Overview

The Marketing Pipeline is an autonomous multi-agent system that orchestrates 10+ specialized AI agents to produce complete marketing campaigns from a single command. Agents run in parallel where possible and sequentially where dependencies exist, coordinated by a central Orchestrator running on Opus.

```
/marketing campaign "Launch an AI-powered project management tool for remote teams"
```

One command. Six stages. Ten agents. ~22 deliverables.

---

## Pipeline Flow

```
                              ┌─────────────┐
                              │    USER      │
                              │  Campaign    │
                              │   Brief      │
                              └──────┬───────┘
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │     MARKETING ORCHESTRATOR      │
                    │          (opus model)           │
                    │  Coordinates all agents & stages │
                    └────────────────┬───────────────┘
                                     │
                                     ▼
              ┌──────────────────────────────────────────┐
              │  STAGE 1: SETUP                          │
              │  • Create output directories              │
              │  • Write campaign brief                   │
              │  • Start dashboard HTTP server             │
              │  • Open browser dashboard                 │
              │  • Write initial pipeline-status.json      │
              └──────────────────┬───────────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────────┐
              │  STAGE 2: RESEARCH  ▸▸▸ 4 IN PARALLEL    │
              │                                          │
              │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
              │  │  Market    │ │Competitive │ │  Trend     │ │  Social    │
              │  │ Researcher │ │  Analyst   │ │  Analyst   │ │ Researcher │
              │  │  (haiku)   │ │  (haiku)   │ │  (haiku)   │ │ (sonnet)   │
              │  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
              │        ▼              ▼              ▼              ▼       │
              │  market-analysis competitive-  trend-analysis social-      │
              │      .md        intelligence.md    .md      listening.md   │
              └──────────────────┬─────────────────────────────────────────┘
                                 │
                          ░░ WAIT ALL ░░
                                 │
                                 ▼
              ┌──────────────────────────────────────────┐
              │  STAGE 3: STRATEGY  ▸▸▸ SEQUENTIAL       │
              │                                          │
              │  Orchestrator reads all 4 research files   │
              │  and synthesizes:                         │
              │                                          │
              │  → marketing-strategy.md                  │
              │  → target-audience.md                     │
              └──────────────────┬───────────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────────┐
              │  STAGE 4: CONTENT + SEO + VIDEO + MEDIA  │
              │  ▸▸▸ 4 IN PARALLEL                       │
              │                                          │
              │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
              │  │ Content  │ │   SEO    │ │  Video   │ │  Media   │
              │  │ Marketer │ │Specialist│ │ Producer │ │ Producer │
              │  │ (haiku)  │ │ (haiku)  │ │(sonnet)  │ │(sonnet)  │
              │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
              │       ▼            ▼            ▼            ▼      │
              │  blog.md      keyword-    product-hero  hero-banner │
              │  social.md    research.md   .mp4         .png       │
              │  email.md     seo-recs.md social-clip   social-     │
              │  landing.md                .mp4        graphic.png  │
              │                          stats-video   blog-header  │
              │                            .mp4          .png       │
              │                                       product-     │
              │                                       teaser.mp4   │
              └──────────────────┬───────────────────────────────┘
                                 │
                          ░░ WAIT ALL ░░
                                 │
                                 ▼
              ┌──────────────────────────────────────────┐
              │  STAGE 5: REVIEW  ▸▸▸ 2 IN PARALLEL      │
              │                                          │
              │  ┌────────────────┐ ┌────────────────┐   │
              │  │   Business     │ │    Sales       │   │
              │  │   Analyst      │ │   Engineer     │   │
              │  │   (sonnet)     │ │   (sonnet)     │   │
              │  └───────┬────────┘ └───────┬────────┘   │
              │          ▼                  ▼             │
              │   quality-review.md  sales-alignment.md   │
              └──────────────────┬───────────────────────┘
                                 │
                          ░░ WAIT ALL ░░
                                 │
                                 ▼
              ┌──────────────────────────────────────────┐
              │  STAGE 6: FINAL  ▸▸▸ SEQUENTIAL          │
              │                                          │
              │  Orchestrator compiles all deliverables:   │
              │                                          │
              │  → executive-summary.md                   │
              │  → README.md (table of contents)          │
              │  → Final pipeline-status.json              │
              │  → Stop dashboard server                  │
              └──────────────────┬───────────────────────┘
                                 │
                                 ▼
                          ✅ COMPLETE
```

---

## Agent Roster

| Agent | Subagent Type | Model | Stage | Role |
|-------|--------------|-------|-------|------|
| **Orchestrator** | `marketing-orchestrator` | opus | ALL | Coordinates agents, synthesizes strategy, compiles final report |
| **Market Researcher** | `market-researcher` | haiku | 2 | Market size, growth trends, buyer behavior, segments |
| **Competitive Analyst** | `competitive-analyst` | haiku | 2 | Competitor features, pricing, SWOT, positioning |
| **Trend Analyst** | `trend-analyst` | haiku | 2 | Macro trends, technology shifts, forecasts |
| **Social Researcher** | `social-researcher` | sonnet | 2 | Reddit, Twitter/X, Telegram scraping, sentiment analysis |
| **Content Marketer** | `content-marketer` | haiku | 4 | Blog posts, social media, email sequences, landing pages |
| **SEO Specialist** | `seo-specialist` | haiku | 4 | Keyword research, on-page SEO, link building strategy |
| **Video Producer** | `general-purpose` | sonnet | 4 | Motion graphics via Remotion (React-based video) |
| **Media Producer** | `gemini-media-producer` | sonnet | 4 | AI-generated images + video via Gemini API (Imagen + Veo 2) |
| **Business Analyst** | `business-analyst` | sonnet | 5 | Quality scoring, gap analysis, ROI assessment |
| **Sales Engineer** | `sales-engineer` | sonnet | 5 | Sales readiness, competitive positioning, objection handling |
| **Web Scraper** | `web-scraper` | sonnet | On-demand | Structured data extraction, JS page scraping (Playwright) |

---

## Execution Pattern

```
Stage 1      Stage 2           Stage 3      Stage 4                     Stage 5        Stage 6
[setup]      [4 parallel]      [sequential] [4 parallel]                [2 parallel]   [sequential]

 ████         ████████████       ██████████   ████████████████████████    ████████████    ████
 ~5s          ~4-5 min           ~10 min      ~30-60 min                 ~13 min         ~5 min
                                              ▲ longest stage
```

**Total estimated time**: ~60-80 minutes for a full-funnel campaign

**Parallelism**: Agents within the same stage run simultaneously. Stages run sequentially (each waits for the previous to complete).

---

## Output Structure

```
marketing-output/{campaign-slug}/
│
├── 00-brief/
│   └── campaign-brief.md ..................... Original brief + expanded objectives
│
├── 01-research/
│   ├── market-analysis.md .................... ~1,000 lines
│   ├── competitive-intelligence.md ........... ~560 lines
│   ├── trend-analysis.md .................... ~830 lines
│   └── social-listening.md .................. ~400 lines (Reddit/Twitter/Telegram)
│
├── 02-strategy/
│   ├── marketing-strategy.md ................. ~740 lines
│   └── target-audience.md .................... ~920 lines
│
├── 03-content/
│   ├── blog-posts/{topic}-blog.md ............ ~170 lines
│   ├── social-media/social-media-pack.md ..... ~310 lines
│   ├── email-campaigns/email-sequence.md ..... ~330 lines
│   ├── landing-pages/landing-page-copy.md .... ~300 lines
│   ├── videos/
│   │   ├── product-hero.mp4 .................. 30s, 1920x1080 (Remotion)
│   │   ├── social-clip.mp4 ................... 15s, 1080x1080 (Remotion)
│   │   └── stats-video.mp4 ................... 20s, 1920x1080 (Remotion)
│   └── media/
│       ├── hero-banner.png ................... 1920x1080 (Gemini Imagen)
│       ├── social-graphic.png ................ 1080x1080 (Gemini Imagen)
│       ├── blog-header.png ................... 1920x1080 (Gemini Imagen)
│       └── product-teaser.mp4 ................ 720p, 8s (Gemini Veo 2)
│
├── 04-seo/
│   ├── keyword-research.md ................... ~580 lines
│   └── seo-recommendations.md ................ ~980 lines
│
├── 05-review/
│   ├── quality-review.md ..................... ~680 lines  (score: X/10)
│   └── sales-alignment.md .................... ~430 lines  (score: X/10)
│
├── 06-final/
│   └── executive-summary.md .................. Campaign overview + action items
│
├── README.md .................................. Table of contents
├── pipeline-dashboard.html ................... Live monitoring dashboard
└── pipeline-status.json ...................... Machine-readable pipeline state
```

**Totals**: ~21 deliverables | ~8,000+ lines of text | 6 videos | 3 AI images

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Orchestration** | Claude Code Task tool | Agent spawning, parallel execution |
| **Text Content** | Claude AI (Haiku/Sonnet/Opus) | Research, strategy, content, reviews |
| **Motion Graphics** | [Remotion](https://github.com/remotion-dev/remotion) (React) | Programmatic video rendering |
| **AI Images** | [Gemini Imagen 3](https://ai.google.dev/gemini-api/docs/imagen) | Text-to-image generation |
| **AI Video** | [Gemini Veo 2](https://ai.google.dev/gemini-api/docs/video) | Text-to-video generation |
| **Web Scraping** | Playwright + BeautifulSoup | Competitive intelligence data extraction |
| **Dashboard** | Self-contained HTML/CSS/JS | Real-time pipeline monitoring |
| **Dashboard Server** | Python `http.server` | Zero-dependency local file serving |

---

## Live Dashboard

Every pipeline run automatically opens a real-time web dashboard at `http://localhost:8847/pipeline-dashboard.html`.

```
┌────────────────────────────────────────────────────────────┐
│  marketing-pipeline // dashboard                    ⏱ 14m  │
│  Campaign: AI PM Tool Launch    Mode: Full Funnel          │
├────────────────────────────────────────────────────────────┤
│  ████████████████░░░░░░  Stage 4/6 — Content + SEO + ...   │
├────────────────────────────────────────────────────────────┤
│  ✅ Setup  ✅ Research  ✅ Strategy  🔄 Content  ⏳ Review │
├────────────────────────────────────────────────────────────┤
│  AGENTS                                                    │
│  [✅ Market Researcher 45s] [✅ Competitive Analyst 38s]   │
│  [✅ Trend Analyst 41s]     [🔄 Content Marketer 2m]      │
│  [🔄 SEO Specialist 1m]    [🔄 Video Producer 3m]         │
│  [🔄 Media Producer 1m]                                    │
├────────────────────────────────────────────────────────────┤
│  DELIVERABLES                                              │
│  📁 01-research/                                           │
│     ├── market-analysis.md ........... 42.5 KB  [✓]       │
│     ├── competitive-intelligence.md .. 25.8 KB  [✓]       │
│     └── trend-analysis.md ............ 37.3 KB  [✓]       │
│  📁 03-content/videos/                                     │
│     └── 🎬 product-hero.mp4 ......... ■■■░░░░  [▶]       │
│  📁 03-content/media/                                      │
│     └── 📷 hero-banner.png .......... ■■■■■░░  [▶]       │
├────────────────────────────────────────────────────────────┤
│  ACTIVITY LOG                                              │
│  10:30:05  Pipeline started (full-funnel)                  │
│  10:30:06  Spawning 4 research agents in parallel...       │
│  10:34:30  All research complete                           │
│  10:44:19  Strategy synthesis complete                     │
│  10:44:20  Spawning 4 content agents in parallel...        │
└────────────────────────────────────────────────────────────┘
```

**Features**: Terminal/hacker aesthetic, Gantt timeline, agent cards with deliverable tracking, file tree, color-coded activity log, confetti on completion.

---

## Data Flow

```
Campaign Brief
     │
     ▼
┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Research │ ──▶ │ Strategy │ ──▶ │ Content  │ ──▶ │  Review  │ ──▶ │  Final   │
│ (raw     │     │(synthesized    │(produced │     │(scored & │     │(compiled │
│  data)   │     │ insights)│     │ assets)  │     │ reviewed)│     │ summary) │
└─────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
  4 agents        orchestrator     4 agents         2 agents        orchestrator
  parallel        sequential       parallel         parallel        sequential
```

Each stage reads the outputs of previous stages. No stage can start until its dependencies are complete.

---

## Pipeline Modes

### One-Shot Pipelines

| Mode | Command | Agents | Stages | Use Case |
|------|---------|--------|--------|----------|
| **Full Funnel** | `/marketing campaign <brief>` | 10 | 8 | Complete campaign from research to distribution |
| **Content Production** | `/marketing content <topic>` | 5 | 5 | Blog, social, email, landing page + SEO |
| **Market Intelligence** | `/marketing research <topic>` | 6 | 4 | Deep research + strategic synthesis |

### Sustained (Long-Running) Campaigns

| Mode | Command | Agents | Stages | Use Case |
|------|---------|--------|--------|----------|
| **Sustained Init** | `/marketing sustain create <brief>` | 4 | 5 | Create recurring campaign: research + strategy + content calendar |
| **Sustained Batch** | Scheduled via launchd | 4 | 5 | Auto-generate content batch per calendar entry |

**Sustained Campaign Lifecycle:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SUSTAINED CAMPAIGN LIFECYCLE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  CREATE (/marketing sustain create)                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐│
│  │  Setup   │→ │ Research │→ │ Strategy │→ │ Calendar │→ │Config ││
│  │          │  │ (4 par.) │  │          │  │ Generate │  │      ││
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────┘│
│       ↓ installs launchd scheduler                                 │
│                                                                     │
│  BATCH (auto-triggered on schedule or /marketing sustain run)       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐│
│  │  Setup   │→ │ Research │→ │ Content  │→ │SEO Review│→ │Compile││
│  │  (brief  │  │ (2 par.) │  │ Creation │  │          │  │      ││
│  │ from cal)│  └──────────┘  └──────────┘  └──────────┘  └──────┘│
│       ↓                                                            │
│  Every N batches → STRATEGY REFRESH (re-run research + synthesis)  │
│                                                                     │
│  MANAGEMENT                                                         │
│  pause / resume / delete / calendar / refresh / history             │
└─────────────────────────────────────────────────────────────────────┘
```

**Persistent State** (at `~/.marketing-pipeline/campaigns/{slug}/`):

```
campaign-config.json    ← cadence, content types, total batches (set once)
campaign-state.json     ← current batch, status, last run (updated each batch)
content-calendar.json   ← themes + angles per batch (generated from strategy)
batch-history.json      ← append-only log of completed batches
run-batch.sh            ← shell script invoked by launchd
foundation/             ← initial research + active strategy
batches/batch-NNN/      ← output per batch (same as content-production)
logs/                   ← per-batch execution logs
```

**Scheduling**: macOS launchd plist at `~/Library/LaunchAgents/com.marketing-pipeline.sustain.{slug}.plist`. Invokes `claude -p --dangerously-skip-permissions` headlessly to run each batch.

---

## Requirements

| Requirement | Purpose | Install |
|-------------|---------|---------|
| Claude Code | Agent orchestration | [claude.ai/claude-code](https://claude.ai/claude-code) |
| Python 3 | Dashboard server | Pre-installed on macOS/Linux |
| Node.js 18+ | Remotion video rendering | [nodejs.org](https://nodejs.org) |
| `GEMINI_API_KEY` | AI image/video generation | [ai.google.dev](https://ai.google.dev/) |
| Marketing subagents | Agent definitions | Included in plugin or via [awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) |
