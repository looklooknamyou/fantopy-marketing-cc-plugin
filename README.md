# Marketing Pipeline Plugin for Claude Code

An autonomous multi-agent marketing pipeline that orchestrates 7+ specialized AI agents to produce complete marketing campaigns — from research through content creation, SEO optimization, and quality review — all from a single command.

## What It Does

You give it a campaign brief. It autonomously:

1. **Researches** your market, competitors, and trends (3 agents in parallel)
2. **Synthesizes** a marketing strategy with detailed buyer personas
3. **Creates content** — blog posts, social media, email sequences, landing pages (2 agents in parallel)
4. **Optimizes for SEO** — keyword research, on-page recommendations, link building strategy
5. **Reviews everything** — quality assessment + sales alignment review (2 agents in parallel)
6. **Compiles** an executive summary with prioritized action items

All while showing real-time progress on a terminal-themed web dashboard.

## Output Example

A single `/marketing campaign` run produces **14-16 deliverables** totaling **7,000-8,000+ lines** of content:

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
│   └── landing-pages/              (~300 lines)
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

## Commands

| Command | Description | Agents | Stages |
|---------|-------------|--------|--------|
| `/marketing campaign <brief>` | Full-funnel campaign | 7 agents | 6 stages |
| `/marketing content <topic>` | Content production only | 4 agents | 5 stages |
| `/marketing research <topic>` | Market intelligence only | 5 agents | 4 stages |
| `/marketing status` | Check pipeline progress | — | — |

### Shortcut Commands

| Command | Same As |
|---------|---------|
| `/marketing-campaign <brief>` | `/marketing campaign <brief>` |
| `/marketing-content <topic>` | `/marketing content <topic>` |
| `/marketing-research <topic>` | `/marketing research <topic>` |
| `/marketing-status` | `/marketing status` |

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

Stage 4: Content + SEO (PARALLEL)
    ├── Content Marketer ───────→ blog, social, email, landing page
    └── SEO Specialist ─────────→ keyword-research.md + seo-recommendations.md

Stage 5: Review (PARALLEL)
    ├── Business Analyst ───────→ quality-review.md
    └── Sales Engineer ─────────→ sales-alignment.md

Stage 6: Final (SEQUENTIAL)
    └── Orchestrator compiles ──→ executive-summary.md + README.md
```

Agents within the same stage run **in parallel**. Stages run **sequentially** (each stage waits for the previous to complete).

### Agent Roster

| Agent | Type | Model | Role |
|-------|------|-------|------|
| Market Researcher | market-researcher | haiku | Market sizing, trends, buyer behavior |
| Competitive Analyst | competitive-analyst | haiku | Competitor features, pricing, SWOT |
| Trend Analyst | trend-analyst | haiku | Macro trends, technology shifts |
| Content Marketer | content-marketer | haiku | Blog, social, email, landing pages |
| SEO Specialist | seo-specialist | haiku | Keywords, on-page SEO, link strategy |
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
├── .claude-plugin/
│   └── plugin.json              # Plugin metadata and registration
├── agents/
│   └── marketing-orchestrator.md # Core orchestrator (opus model)
├── commands/
│   ├── marketing.md             # Main router command
│   ├── marketing-campaign.md    # Full funnel shortcut
│   ├── marketing-content.md     # Content production shortcut
│   ├── marketing-research.md    # Market intelligence shortcut
│   └── marketing-status.md      # Pipeline status checker
└── assets/
    └── pipeline-dashboard.html  # Real-time monitoring dashboard (1,900+ lines)
```

## Requirements

- **Claude Code** with plugin support
- **Python 3** (for the dashboard HTTP server — pre-installed on macOS/Linux)
- **Subagent types** must be available: market-researcher, competitive-analyst, trend-analyst, content-marketer, seo-specialist, business-analyst, sales-engineer. These come from the [awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) collection or can be custom `.md` files in `~/.claude/agents/`.

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
- **Long-running**: A full-funnel campaign takes significant time due to the depth of content produced. Content + SEO stage is typically the longest.
- **Port 8847**: The dashboard uses a fixed port. If it's already in use, the server won't start.
- **Single pipeline**: Only one pipeline can run at a time (due to the fixed dashboard port).

## License

MIT
