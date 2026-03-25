# Installation Guide

## Prerequisites

1. **Claude Code** installed and working
2. **Python 3** available (for dashboard server) — run `python3 --version` to check
3. **Marketing subagents** installed in `~/.claude/agents/`. You need these agent definition files:
   - `market-researcher.md`
   - `competitive-analyst.md`
   - `trend-analyst.md`
   - `content-marketer.md`
   - `seo-specialist.md`
   - `business-analyst.md`
   - `sales-engineer.md`

   If you don't have these, install them from the [awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) repo:
   ```bash
   cd /tmp && git clone https://github.com/VoltAgent/awesome-claude-code-subagents.git
   cp awesome-claude-code-subagents/categories/**/*.md ~/.claude/agents/
   rm -rf /tmp/awesome-claude-code-subagents
   ```

## Step 1: Copy Plugin Files

```bash
# Create plugin directory
mkdir -p ~/.claude/plugins/local/marketing-pipeline

# Copy all plugin files (run from the directory containing this INSTALL.md)
cp -r .claude-plugin agents commands assets ~/.claude/plugins/local/marketing-pipeline/
```

Verify the structure:
```bash
find ~/.claude/plugins/local/marketing-pipeline -type f
```

Expected output:
```
.claude-plugin/plugin.json
agents/marketing-orchestrator.md
commands/marketing.md
commands/marketing-campaign.md
commands/marketing-content.md
commands/marketing-research.md
commands/marketing-status.md
assets/pipeline-dashboard.html
```

## Step 2: Register the Plugin

Edit `~/.claude/plugins/installed_plugins.json`. If the file doesn't exist, create it.

Add the `marketing-pipeline@local` entry:

```json
{
  "marketing-pipeline@local": [
    {
      "scope": "user",
      "installPath": "/YOUR/HOME/.claude/plugins/local/marketing-pipeline",
      "version": "1.0.0",
      "installedAt": "2026-01-01T00:00:00.000Z",
      "lastUpdated": "2026-01-01T00:00:00.000Z"
    }
  ]
}
```

Replace `/YOUR/HOME/` with your actual home directory path (e.g., `/Users/yourname/`).

If the file already has other plugins, add the `marketing-pipeline@local` key alongside them.

## Step 3: Enable the Plugin

Edit `~/.claude/settings.json` and add the plugin to `enabledPlugins`:

```json
{
  "enabledPlugins": {
    "marketing-pipeline@local": true
  }
}
```

If `enabledPlugins` already exists with other entries, just add the new line.

## Step 4: Restart Claude Code

Close and reopen Claude Code for the plugin to load.

## Step 5: Verify

Type `/marketing` in Claude Code. You should see:

```
Marketing Pipeline - Autonomous Marketing Orchestration

Usage:
  /marketing campaign <brief>   - Full funnel: Research -> Strategy -> Content -> SEO -> Review
  /marketing content <topic>    - Content production: Blog posts, social media, landing pages, emails
  /marketing research <topic>   - Market intelligence: Market analysis, competitive intel, trends
  /marketing status             - Check pipeline progress
```

## Quick Test

Run a quick test:
```
/marketing research The AI code assistant market in 2026
```

This runs the shortest pipeline (market intelligence — 3 research agents + synthesis) and should complete in a few minutes.

## Troubleshooting

### "/marketing" command not recognized
- Check that the plugin is registered in `installed_plugins.json`
- Check that it's enabled in `settings.json`
- Restart Claude Code

### Dashboard doesn't open
- Check if port 8847 is available: `lsof -i :8847`
- Check if Python 3 is installed: `python3 --version`
- Manually open: `http://localhost:8847/pipeline-dashboard.html`

### Agents can't write files
- Some subagent types (market-researcher, etc.) are read-only
- The orchestrator handles this by using `general-purpose` subagent type for writing tasks
- If you still see issues, check that the output directory exists and is writable

### Pipeline seems stuck
- Run `/marketing status` to check progress
- Check the dashboard for the current stage and agent status
- The Content + SEO stage is typically the longest (can take several minutes per agent)

## Uninstall

```bash
# Remove plugin files
rm -rf ~/.claude/plugins/local/marketing-pipeline

# Remove from installed_plugins.json — delete the "marketing-pipeline@local" entry
# Remove from settings.json — delete the "marketing-pipeline@local": true line
```
