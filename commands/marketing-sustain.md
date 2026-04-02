---
description: Manage sustained (recurring) marketing campaigns with scheduled content generation
argument-hint: "<create|list|status|run|pause|resume|delete|calendar|refresh|history> [slug|brief]"
---

# Sustained Marketing Campaigns

This is a shortcut to `/marketing sustain`. Route through the same sustain logic.

Parse the first word of $ARGUMENTS to determine the subcommand, then handle it exactly as described in the `### If first word is "sustain"` section of the main `/marketing` command.

## Quick Reference

- `create <brief>` — Create recurring campaign: research + strategy + content calendar + launchd scheduler
- `list` — List all sustained campaigns with status
- `status <slug>` — Detailed view: config, progress, calendar, batch history
- `run <slug>` — Manually trigger next content batch
- `pause <slug>` — Pause scheduled execution
- `resume <slug>` — Resume scheduled execution
- `delete <slug>` — Delete campaign and scheduler
- `calendar <slug>` — View full content calendar
- `refresh <slug>` — Force strategy refresh on next batch
- `history <slug>` — View batch execution history
