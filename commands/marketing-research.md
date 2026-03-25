---
description: Run a market intelligence pipeline (Market Analysis + Competitive Intel + Trends)
argument-hint: "<topic>"
---

# Market Intelligence Pipeline

Launch the **marketing-orchestrator** agent using the Task tool:

- subagent_type: "marketing-orchestrator"
- prompt: "Run a MARKET INTELLIGENCE pipeline for the following topic: $ARGUMENTS. Pipeline mode: market-intelligence. Execute autonomously and deliver all outputs to ./marketing-output/[create a slugified name from the topic]/"

The orchestrator will handle everything autonomously — spawning market research, competitive analysis, and trend analysis agents in parallel. Report back when it completes with a summary of all deliverables produced.
