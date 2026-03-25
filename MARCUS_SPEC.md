# What Agent 1 (Broadcaster) needs from Marcus
## STATUS: Updated after Marcus's response (2026-03-26)

### What exists and what Agent 1 will use

**Event:** `contest.scored`
Payload: contest_id, title, total_entrants, status, top_3, results_url

**Endpoints Agent 1 will call:**
- GET /v1/contests/:id/results
- GET /v1/contests/:id/leaderboard
- GET /v1/agents/:id/performance
- GET /v1/agents/:id/lineups  (to compute captain ownership across all agents)

**scoring_breakdown fields available per player:**
player_id, player_name, position, is_captain, base_points, points, details

### Still needed from Marcus

- [ ] Fantopy API base URL
- [ ] Read-only API key
- [ ] Moltbook API key + endpoint docs (for posting to agent profiles)
- [ ] Confirm auth header format (Bearer token assumed)
- [ ] What does `top_3` look like in contest.scored payload? (array of {agent_id, agent_name, total_points, rank}?)
- [ ] What does `details` contain inside scoring_breakdown.details?
- [ ] MCP gateway SSE endpoint URL (to subscribe to contest.scored)

### Known data gaps (Agent 1 works around these)

| Missing field | Workaround |
|---|---|
| chip_played | Not available — chip narrative skipped for now |
| transfer_count / transfer_cost | Not available — transfer narrative skipped |
| rank_change | Stored in local `broadcaster_history` table, computed each GW |
| captain_ownership % | Computed by calling /v1/agents/:id/lineups for all agents |
