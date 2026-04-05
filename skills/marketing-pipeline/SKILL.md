---
name: marketing-pipeline
description: Use when the user is working on the marketing-pipeline repo or wants to run, debug, review, or extend its autonomous marketing workflows.
---

# Marketing Pipeline

Use this skill when the task is about the Marketing Pipeline plugin itself or its operational flows.

## What this repo exposes

- Claude-style routing lives in `commands/marketing.md`
- Core orchestration logic lives in `agents/marketing-orchestrator.md`
- Dashboard UI lives in `assets/pipeline-dashboard.html`
- Cloud API and team features live in `cloud/api/`
- Social distribution and staging integrations live in `cloud/api/routes/distribution.js` and `cloud/api/routes/staging.js`

## Main workflow map

### One-shot campaign mode

- Entry: `/marketing campaign <brief>`
- Output root: `marketing-output/<slug>/`
- Main stages: setup, research, strategy, content/SEO/media, review, final summary

### Sustained campaign mode

- Entry: `/marketing sustain create <brief>`
- Output root: `~/.marketing-pipeline/campaigns/<slug>/`
- Key files:
  - `campaign-config.json`
  - `campaign-state.json`
  - `content-calendar.json`
  - `batch-history.json`
  - `batches/`

### Cloud mode

- Dashboard bootstrap comes from `cloud-config.json` or stored cloud bootstrap state
- Team/auth APIs live under `cloud/api/routes/auth.js` and `cloud/api/routes/teams.js`
- Campaign sync, approvals, distribution, and staging integrations are team-scoped backend features

## High-value files to inspect first

- `README.md` for product-level behavior and outputs
- `INSTALL.md` for client-specific install flows
- `ARCHITECTURE.md` for system layout
- `commands/marketing.md` for route intent
- `agents/marketing-orchestrator.md` for execution semantics

## Working rules

1. Preserve the existing `/marketing` command semantics when changing behavior.
2. Treat agent markdown files as executable business logic, not passive docs.
3. Keep dashboard data contracts aligned with orchestrator output files and cloud API responses.
4. Distinguish local-only config in `~/.marketing-pipeline/` from cloud-backed team config in `cloud/api/`.
