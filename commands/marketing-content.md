---
description: Run a content production pipeline (Research -> Content Creation -> SEO Review)
argument-hint: "<topic>"
---

# Content Production Pipeline

Launch the **marketing-orchestrator** agent using the Task tool:

- subagent_type: "marketing-orchestrator"
- prompt: "Run a CONTENT PRODUCTION marketing pipeline for the following topic: $ARGUMENTS. Pipeline mode: content-production. Execute autonomously and deliver all outputs to ./marketing-output/[create a slugified name from the topic]/"

The orchestrator will handle everything autonomously — spawning research, content, and SEO agents. Report back when it completes with a summary of all deliverables produced.
