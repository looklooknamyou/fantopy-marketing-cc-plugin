---
description: Run autonomous marketing pipelines - campaigns, content production, or market research
argument-hint: "<campaign|content|research|status> <brief or topic>"
---

# Marketing Pipeline

You are the entry point for the marketing pipeline system. Parse the user's command and route to the appropriate pipeline mode.

## Arguments

Raw arguments: $ARGUMENTS

## Routing Logic

Parse the first word of $ARGUMENTS to determine the mode:

### If first word is "campaign"
Launch the **marketing-orchestrator** agent using the Task tool:
- subagent_type: "marketing-orchestrator"
- prompt: "Run a FULL FUNNEL marketing pipeline for the following campaign brief: [remaining arguments after 'campaign']. Pipeline mode: full-funnel. Execute autonomously and deliver all outputs to ./marketing-output/[slugified-campaign-name]/"

### If first word is "content"
Launch the **marketing-orchestrator** agent using the Task tool:
- subagent_type: "marketing-orchestrator"
- prompt: "Run a CONTENT PRODUCTION marketing pipeline for the following topic: [remaining arguments after 'content']. Pipeline mode: content-production. Execute autonomously and deliver all outputs to ./marketing-output/[slugified-topic-name]/"

### If first word is "research"
Launch the **marketing-orchestrator** agent using the Task tool:
- subagent_type: "marketing-orchestrator"
- prompt: "Run a MARKET INTELLIGENCE pipeline for the following topic: [remaining arguments after 'research']. Pipeline mode: market-intelligence. Execute autonomously and deliver all outputs to ./marketing-output/[slugified-topic-name]/"

### If first word is "status"
Check pipeline status:
1. Look for any `./marketing-output/` directories and list them
2. For each, check which files exist to determine progress
3. Report which stages are complete vs pending

### If no arguments or unrecognized
Display this help:

```
Marketing Pipeline - Autonomous Marketing Orchestration

Usage:
  /marketing campaign <brief>   - Full funnel: Research -> Strategy -> Content -> SEO -> Review
  /marketing content <topic>    - Content production: Blog posts, social media, landing pages, emails
  /marketing research <topic>   - Market intelligence: Market analysis, competitive intel, trends
  /marketing status             - Check pipeline progress

Examples:
  /marketing campaign Launch our new AI-powered analytics product targeting enterprise CTOs
  /marketing content How zero-trust architecture is transforming cloud security
  /marketing research The enterprise observability platform market in 2026
  /marketing status
```

## Important
- Always launch the marketing-orchestrator agent for campaign, content, and research modes
- Pass the full brief/topic text exactly as provided
- The orchestrator handles all agent coordination autonomously
- Do not attempt to run the pipeline yourself — delegate entirely to the orchestrator
