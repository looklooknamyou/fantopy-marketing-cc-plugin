# Installation Guide

## Prerequisites

1. **Claude Code** installed and working
2. **Python 3** available (for dashboard server) — run `python3 --version` to check
3. **Node.js 18+** available (for cloud backend and scripts) — run `node --version` to check
4. **Marketing subagents** installed in `~/.claude/agents/`. You need these agent definition files:
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
cp -r .claude-plugin agents commands assets cloud ~/.claude/plugins/local/marketing-pipeline/
```

Verify the structure:
```bash
find ~/.claude/plugins/local/marketing-pipeline -maxdepth 3 -type f | head -30
```

Expected key files:
```
.claude-plugin/plugin.json
agents/marketing-orchestrator.md
agents/distribution-agent.md
agents/gemini-media-producer.md
agents/web-scraper.md
commands/marketing.md
commands/marketing-campaign.md
commands/marketing-content.md
commands/marketing-research.md
commands/marketing-status.md
assets/pipeline-dashboard.html
assets/distribution/distribute.js
assets/distribution/approval-poll.js
cloud/api/server.js
cloud/api/routes/approval.js
cloud/sdk/index.js
cloud/supabase/migrations/001_initial.sql
cloud/supabase/migrations/002_approval.sql
```

## Step 2: Register the Slash Commands

Plugin commands are namespaced by default (e.g., `/marketing-pipeline:marketing`). To use the shorter `/marketing` format, symlink the commands to your global commands directory:

```bash
# Create global commands directory
mkdir -p ~/.claude/commands

# Symlink all marketing commands
for f in ~/.claude/plugins/local/marketing-pipeline/commands/*.md; do
  ln -sf "$f" ~/.claude/commands/$(basename "$f")
done
```

Verify the symlinks:
```bash
ls -la ~/.claude/commands/
```

You should see:
```
marketing.md -> ~/.claude/plugins/local/marketing-pipeline/commands/marketing.md
marketing-campaign.md -> ...
marketing-content.md -> ...
marketing-research.md -> ...
marketing-status.md -> ...
```

## Step 3: Register the Plugin

Edit `~/.claude/plugins/installed_plugins.json`. If the file doesn't exist, create it.

Add the `marketing-pipeline@local` entry to the `"plugins"` object:

```json
{
  "version": 2,
  "plugins": {
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
}
```

Replace `/YOUR/HOME/` with your actual home directory path (e.g., `/Users/yourname/`).

If the file already has other plugins, add the `"marketing-pipeline@local"` key alongside them inside the existing `"plugins"` object.

## Step 4: Restart Claude Code

Close and reopen Claude Code for the plugin to load.

## Step 5: Verify

Type `/marketing` in Claude Code. You should see the help menu:

```
Marketing Pipeline - Autonomous Marketing Orchestration

Usage:
  /marketing campaign <brief>   - Full funnel: Research -> Strategy -> Content -> SEO -> Review
  /marketing content <topic>    - Content production: Blog posts, social media, landing pages, emails
  /marketing research <topic>   - Market intelligence: Market analysis, competitive intel, trends
  /marketing status             - Check pipeline progress

Approval & Distribution:
  /marketing approve <slug>       - Review and approve content before distribution
  /marketing approve <slug> --all - Approve all content and resume pipeline
  /marketing distribution setup   - Configure Reddit, Twitter/X, Telegram, Discord APIs
  /marketing distribution status  - Show which platforms are configured
  /marketing distribution test    - Send test posts to all configured platforms

Cloud & Collaboration:
  /marketing cloud setup        - Configure Supabase cloud backend
  /marketing cloud status       - Show cloud connection info
  /marketing cloud register     - Register a new cloud account
  /marketing teams list         - List your teams
  /marketing teams create <n>   - Create a new team workspace
  /marketing share <slug>       - Upload a local campaign to cloud
  /marketing browse             - Browse team campaigns from cloud
```

---

## Optional Setup

### Environment Variables

Create a `.env` file in your project root for API keys:

```bash
# Gemini API key (for AI-powered media generation)
GEMINI_API_KEY=your_gemini_api_key_here

# Cloud API key (generated via /marketing cloud register)
MARKETING_CLOUD_API_KEY=your_cloud_api_key_here
```

Set restrictive permissions:
```bash
chmod 600 .env
```

### Distribution Setup (Social Media Posting)

To enable automated posting to social platforms after pipeline completion:

```
/marketing distribution setup
```

This will interactively prompt you for API credentials for each platform:

| Platform | Credentials Needed |
|----------|-------------------|
| **Reddit** | Client ID, Client Secret, Username, Password |
| **Twitter/X** | API Key, API Secret, Access Token, Access Secret |
| **Telegram** | Bot Token, Channel ID |
| **Discord** | Webhook URL |

Credentials are stored at `~/.marketing-pipeline/distribution.json` with `600` permissions.

### Cloud Backend Setup (Team Collaboration)

For real-time dashboards, team collaboration, and cloud sync:

1. **Self-hosted Supabase** (recommended for full control):
   ```bash
   cd ~/.claude/plugins/local/marketing-pipeline/cloud
   docker compose up -d
   ```

   Then run migrations:
   ```bash
   docker exec -i supabase-db psql -U postgres < cloud/supabase/migrations/001_initial.sql
   docker exec -i supabase-db psql -U postgres < cloud/supabase/migrations/002_approval.sql
   ```

   Start the API server:
   ```bash
   cd cloud/api && npm install && node server.js &
   ```

2. **Connect Claude Code to cloud**:
   ```
   /marketing cloud setup
   ```

3. **Create a team**:
   ```
   /marketing teams create "My Team"
   ```

### Gemini Media Generation

If you have a Gemini API key, the pipeline can generate images (Imagen 4.0) and video clips (Veo 3.0) for your campaigns. Set your key:

```bash
echo "GEMINI_API_KEY=your_key_here" >> .env
chmod 600 .env
```

The pipeline will automatically use Gemini for media generation when the key is available.

---

## Pipeline Modes

### Full Funnel Campaign (8 stages)
```
/marketing campaign Launch our new AI-powered analytics product targeting enterprise CTOs
```
Runs: Setup > Research > Strategy > Content > Review > Final > **Approval** > Distribution

### Content Production
```
/marketing content How zero-trust architecture is transforming cloud security
```
Focused on generating blog posts, social media, landing pages, and email content.

### Market Intelligence
```
/marketing research The enterprise observability platform market in 2026
```
Focused on market analysis, competitive intelligence, and trend reports.

### Content Approval
After Stage 6 completes, the pipeline pauses for your review:
```
/marketing approve <slug>       # Interactive review per deliverable
/marketing approve <slug> --all # Approve everything and resume
```

The dashboard also provides a visual staging panel where you can approve/reject content per platform with toggle controls.

---

## Dashboard

The pipeline automatically starts a dashboard at `http://localhost:8847/pipeline-dashboard.html` showing:
- Real-time pipeline progress with 8-stage timeline
- Gantt chart with stage durations
- Active agents and deliverables
- Activity log
- **Actions Bar** with Staging Review and Distribution buttons
- **Staging Panel** for content approval (auto-opens when pipeline reaches approval stage)

---

## Quick Test

Run a quick test with the shortest pipeline:
```
/marketing research The AI code assistant market in 2026
```
This runs 3 research agents + synthesis and should complete in a few minutes.

---

## Troubleshooting

### `/marketing` command not recognized
- **Most common fix**: Symlink commands to `~/.claude/commands/` (see Step 2 above)
- Alternatively, use the namespaced version: `/marketing-pipeline:marketing`
- Check that the plugin is registered in `installed_plugins.json`
- Restart Claude Code after making changes

### Dashboard doesn't open
- Check if port 8847 is available: `lsof -i :8847`
- Check if Python 3 is installed: `python3 --version`
- Manually open: `http://localhost:8847/pipeline-dashboard.html`

### Staging panel doesn't show
- The panel only appears when the pipeline reaches `awaiting_approval` status
- Click the "Staging Review" button in the Actions Bar to manually open it
- Check that `approval-status.json` exists in the campaign output directory

### Agents can't write files
- Some subagent types (market-researcher, etc.) are read-only by design
- The orchestrator handles this by using `general-purpose` subagent type for writing tasks
- If you still see issues, check that the output directory exists and is writable

### Pipeline seems stuck
- Run `/marketing status` to check progress
- Check the dashboard for the current stage and agent status
- The Content + SEO stage is typically the longest (can take several minutes per agent)
- If stuck at approval, run `/marketing approve <slug>` to review and resume

### Distribution fails
- Run `/marketing distribution status` to check configured platforms
- Run `/marketing distribution test` to send test posts
- Check `~/.marketing-pipeline/distribution.json` exists and has valid credentials

### Cloud connection issues
- Run `/marketing cloud status` to check connection
- Verify Supabase is running: `docker ps | grep supabase`
- Check the API server: `curl http://localhost:3847/health`
- Verify `~/.marketing-pipeline/cloud.json` has correct URL and keys

---

## Uninstall

```bash
# Remove plugin files
rm -rf ~/.claude/plugins/local/marketing-pipeline

# Remove command symlinks
rm -f ~/.claude/commands/marketing*.md

# Remove from installed_plugins.json — delete the "marketing-pipeline@local" entry

# Remove distribution credentials (if configured)
rm -f ~/.marketing-pipeline/distribution.json

# Remove cloud config (if configured)
rm -f ~/.marketing-pipeline/cloud.json

# Stop cloud backend (if running)
cd ~/.claude/plugins/local/marketing-pipeline/cloud && docker compose down 2>/dev/null
```
