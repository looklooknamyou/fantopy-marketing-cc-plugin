---
description: Run autonomous marketing pipelines - campaigns, content production, market research, or sustained campaigns

## Arguments

$ARGUMENTS - The campaign brief or topic to execute.

## Routing Logic

### If first word is "campaign"
  - Launch full-funnel pipeline
  - If a `--media-config '<json>'` flag is present, preserve it and pass the parsed media preferences into the orchestrator prompt
- Launch content-production pipeline
- Launch market-intelligence pipeline

### If first word is "content"
  - Launch content-production pipeline
  - If a `--media-config '<json>'` flag is present, preserve it and pass the parsed media preferences into the content/media generation prompt

### If first word is "research"
  - Launch market-intelligence pipeline

### If first word is "status"
  - Check pipeline status

### If first word is "cloud"
  - Configure cloud backend
  - Browse team campaigns
  - Register a new user

### If first word is "teams"
  - List user's teams

### If first word is "distribution"
  - Share campaign
  - Browse team campaigns from cloud

### If first word is "approve"
  - Approve all content for distribution

### If first word is "browse"
  - View dashboard

### If first word is "share"
  - Upload a completed local campaign to cloud

## Routing Logic

### If first word is "sustain"

**`/marketing sustain create <brief>`** — Create a new sustained (recurring) campaign:
1. Parse the remaining arguments after "create" as a campaign brief
2. Ask for user for configuration:
   - **Cadence**: daily, weekly, bi-weekly, or monthly
   - **Content types per batch**: blog-post, social-media, email (multi-select)
   - **Total batches**: how many batches to generate
   - **Preferred run time**: day of week + hour
3. Generate a slug from the brief

4. Launch **marketing-orchestrator** agent using the Task tool:
   - subagent_type: "marketing-orchestrator"
   - prompt: "Run a SUSTAINED CAMPAIGN INITIALIZATION for the following brief: [brief]. Pipeline mode: sustained-campaign-init. Campaign parameters: cadence=[cadence], total_batches=[N], content_types=[types], run_schedule=[schedule], media_config=[media_config]. Campaign directory: ~/.marketing-pipeline/campaigns/[slug]/. Execute autonomously: create directories, run research, synthesize strategy, generate content calendar, write config files."

5. After orchestrator completes, set up macOS launchd scheduler:
   - **Write campaigns-index.json**:
   Before launching, write `campaigns-index.json` to `~/.marketing-pipeline/campaigns/` with all campaign metadata. Format:

   ```json
   {
     "generated_at": "<ISO timestamp>",
     "campaigns": [
       {
         "slug": "...",
         "dir": "<absolute path>",
         "brief": "...",
         "cadence": "weekly",
         "status": "active",
         "current_batch": 0,
         "total_batches": 12,
         "next_run": "...",
         "last_run_at": "...",
         "last_run_status": "success",
         "content_types": ["blog-post", "social-media", "email"]
       }
     ]
   }
   ```

   **Function**: `generateCampaignsIndex()`
   - Called by: `/marketing sustain list` and `/marketing sustain status` to refresh the index file
   - Takes campaign directory path from config or defaults to `~/.marketing-pipeline/campaigns/`
   - Returns array of campaign slugs
   - Each object contains: slug, dir, brief, cadence, status, current_batch, total_batches, next_run, last_run_at, last_run_status, content_types

6. **Function**: `slugify(brief)`
   - Converts campaign brief to a URL-friendly slug (lowercase, kebab-case)
   - Returns: e.g., "fantopy weekly content" → "fantopy-weekly-content"
   - Replaces spaces with hyphens, removes special characters
   - Examples:
     - "Weekly newsletter for product launches" → "weekly-newsletter-for-product-launches"
     - "Marketing content for AI SaaS" → "ai-content-marketing-for-saas-product"
     - "Getting started with Fantopy" → "getting-started-with-fantopy"

7. **Function**: `parseWizardFlags(arguments)`
   - Parses flag arguments like `--cadence weekly --batches 12 --day monday --hour 9 --types blog-post,social-media,email --media-config '{"hero-banner":{"provider":"qwen","model":"qwen-image-max"}}'`
   - Returns object with cadence, total_batches, day, hour, types, media_config
   - If flags are present, skip interactive questions
   - Default values: cadence="weekly", total_batches=12, day=1, hour=9, types=["blog-post","social-media","email"], media_config=null

8. **Function**: `parseMediaConfigFlag(arguments)`
   - Reads the `--media-config '<json>'` flag when present
   - Returns a normalized object keyed by asset id (`hero-banner`, `social-graphic`, `blog-header`, `product-teaser`)
   - Each asset may specify `provider` and `model`
   - Pass this object into the orchestrator prompt so the media producer can write the same selections into `media-brief.json`

9. **Function**: `writeCampaignsIndex(file, campaignsData)`
   - Writes campaigns-index.json to campaign directory
   - Format matches the hub view structure
   - Includes timestamp and campaign array

10. **Function**: `loadCampaignsIndex(dir)`
   - Reads campaigns-index.json from specified directory
   - Returns parsed campaigns array or empty array

11. **Function**: `generateSlug(brief)`
   - Helper: Creates unique campaign slug from brief
   - Combines kebab-case, removes special chars
   - Examples: "Weekly content" → "weekly-content"
   - Returns: "weekly-content"

---

## Implementation Notes

- The campaigns-index.json must be served from the campaign directory root
- Path is resolved relative: `./campaigns/[slug]/`
- Default campaign directory when no campaign_dir URL param: campaigns root
- The hub view polls the index file and loads campaign data
- File generation happens on sustain commands: list, status
```
