---
description: Check the status of running or completed marketing pipelines
---

# Marketing Pipeline Status

Check the current state of marketing pipelines:

1. Use Bash to list directories under `./marketing-output/` (if any exist)
2. For each campaign directory found:
   - Check if `pipeline-status.json` exists and read it for detailed status
   - If no JSON, check which output files exist to infer progress:
     - `00-brief/` = Setup complete
     - `01-research/` = Research stage
     - `02-strategy/` = Strategy stage
     - `03-content/` = Content production stage
     - `04-seo/` = SEO optimization stage
     - `05-review/` = Review stage
     - `06-final/` = Pipeline complete
3. Report status for each pipeline found:
   - Pipeline name and mode
   - Stages complete vs pending
   - Active agents and their status
   - List of deliverables produced so far
4. Check if the dashboard server is running (check for `.server.pid` file and if process is alive)
   - If running, tell the user: "Dashboard is live at http://localhost:8847/pipeline-dashboard.html"
   - Offer to open it: run `open "http://localhost:8847/pipeline-dashboard.html"` via Bash
5. If no `./marketing-output/` directory exists, report "No marketing pipelines found. Run `/marketing campaign <brief>` to start one."
