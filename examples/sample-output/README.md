# Sample Output

This directory contains a sample `pipeline-status.json` from a completed full-funnel campaign run.

## Campaign Details

- **Brief:** "Launch an AI-powered project management tool for remote teams"
- **Mode:** Full-funnel
- **Agents used:** 8 (Market Researcher, Competitive Analyst, Trend Analyst, Content Marketer, SEO Specialist, Business Analyst, Sales Engineer, Orchestrator)
- **Total deliverables:** 16 files
- **Total content:** 7,843 lines (~500 KB)
- **Quality score:** 8.2/10
- **Sales readiness:** 6.5/10

## Output Structure Produced

```
ai-project-management-launch/
├── 00-brief/campaign-brief.md .............. 1.2 KB
├── 01-research/
│   ├── market-analysis.md .................. 42.5 KB   (987 lines)
│   ├── competitive-intelligence.md ......... 25.8 KB   (563 lines)
│   └── trend-analysis.md ................... 37.3 KB   (832 lines)
├── 02-strategy/
│   ├── marketing-strategy.md ............... 28.4 KB   (740 lines)
│   └── target-audience.md .................. 27.6 KB   (920 lines)
├── 03-content/
│   ├── blog-posts/ai-pm-remote-teams-blog.md  12.8 KB (166 lines)
│   ├── social-media/social-media-pack.md ...... 8.4 KB (311 lines)
│   ├── email-campaigns/email-sequence.md ..... 15.2 KB (332 lines)
│   └── landing-pages/landing-page-copy.md .... 10.6 KB (301 lines)
├── 04-seo/
│   ├── keyword-research.md ................. 28.5 KB   (577 lines)
│   └── seo-recommendations.md .............. 48.2 KB   (980 lines)
├── 05-review/
│   ├── quality-review.md ................... 18.6 KB   (682 lines)
│   └── sales-alignment.md .................. 22.4 KB   (431 lines)
├── 06-final/
│   └── executive-summary.md ................ 5.8 KB
└── README.md ............................... 3.2 KB
```

## Timeline

| Stage | Duration | Agents |
|-------|----------|--------|
| Setup | 5s | — |
| Research | 4m 24s | 3 in parallel |
| Strategy | 9m 49s | 1 (orchestrator) |
| Content + SEO | 3h 38m | 2 in parallel |
| Review | 13m | 2 in parallel |
| Final | 5m | 1 (orchestrator) |

## To Preview the Dashboard

```bash
cd examples/sample-output
python3 -m http.server 8847
# Open http://localhost:8847/pipeline-dashboard.html in your browser
```

The dashboard will render the completed pipeline from the `pipeline-status.json` file.
