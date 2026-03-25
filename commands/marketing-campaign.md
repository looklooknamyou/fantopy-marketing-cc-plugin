---
description: Run a full-funnel marketing campaign pipeline (Research -> Strategy -> Content -> SEO -> Review)
argument-hint: "<campaign brief>"
---

# Full Funnel Marketing Campaign

Launch the **marketing-orchestrator** agent using the Task tool:

- subagent_type: "marketing-orchestrator"
- prompt: "Run a FULL FUNNEL marketing pipeline for the following campaign brief: $ARGUMENTS. Pipeline mode: full-funnel. Execute autonomously and deliver all outputs to ./marketing-output/[create a slugified name from the brief]/"

The orchestrator will handle everything autonomously — spawning research, content, SEO, and review agents in the right order. Report back when it completes with a summary of all deliverables produced.
