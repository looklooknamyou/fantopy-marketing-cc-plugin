# Marketing Pipeline — Cloud Backend

Opt-in cloud backend for sharing campaigns and real-time dashboard updates across team members. Uses Supabase (free tier or self-hosted).

## Architecture

```
Local pipeline (unchanged)
  └─> SDK syncs state + files to Supabase
        └─> Supabase Realtime → remote dashboards
```

**Local-first**: The pipeline runs identically without cloud. Cloud wraps around it, syncing state after each local write.

## Quick Start (Hosted Supabase)

### 1. Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a free project
2. Note your **Project URL** and **anon key** (Settings → API)
3. Note your **service_role key** (for the API server)

### 2. Run the Database Migration

In the Supabase SQL Editor, paste and run:

```
cloud/supabase/migrations/001_initial.sql
```

This creates all tables, RLS policies, storage buckets, and realtime subscriptions.

### 3. Start the API Server

```bash
cd cloud/api
npm install

export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="eyJ..."
# Optional override if you run the API outside the repo root
# export MARKETING_OUTPUT_DIR="/absolute/path/to/marketing-output"

node server.js
# Server running on port 3847
```

### 4. Register a User

```bash
curl -X POST http://localhost:3847/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "display_name": "Your Name"}'
```

Save the returned `api_key`. Set it as an environment variable:

```bash
export MARKETING_CLOUD_API_KEY="your-api-key-here"
```

### 5. Configure the CLI

```
/marketing cloud setup
```

Enter your Supabase URL, anon key when prompted. Or manually create `~/.marketing-pipeline/cloud.json`:

```json
{
  "supabase_url": "https://your-project.supabase.co",
  "supabase_anon_key": "eyJ...",
  "active_team_id": null
}
```

### 6. Create a Team

```
/marketing teams create "My Agency"
```

### 7. Invite Team Members

```
/marketing teams invite colleague@example.com
```

They join with:

```
/marketing teams join <token>
```

### 8. Run a Campaign

```
/marketing campaign Launch our new AI analytics product
```

With cloud configured, the orchestrator automatically:
- Creates a campaign record in Supabase
- Syncs pipeline-status.json after each stage
- Uploads deliverables to Supabase Storage
- Opens the dashboard with Supabase Realtime

Team members can view live progress via the dashboard URL shown in `/marketing browse`.

## Self-Hosted Setup (Docker)

### 1. Run Supabase Locally

```bash
# Clone Supabase Docker setup
git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker
cp .env.example .env

# Start services
docker compose up -d
```

Default local URLs:
- **Supabase URL**: `http://localhost:8000`
- **Anon key**: Check `.env` file
- **Service role key**: Check `.env` file
- **Studio**: `http://localhost:3000`

### 2. Run Migration

Open Studio at `http://localhost:3000`, go to SQL Editor, paste `001_initial.sql`.

### 3. Continue from Step 3 Above

Use `http://localhost:8000` as your Supabase URL.

## API Reference

All endpoints require `x-api-key` header (except `/api/auth/register`).

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register user, get API key |
| GET | `/api/auth/me` | Current user info |
| POST | `/api/auth/rotate-key` | Generate new API key |

### Teams
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/teams` | Create team |
| GET | `/api/teams` | List user's teams |
| GET | `/api/teams/:id/members` | List team members |
| POST | `/api/teams/:id/invite` | Invite by email |
| POST | `/api/teams/join` | Accept invite token |

### Campaigns
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/campaigns?team_id=` | List team campaigns |
| GET | `/api/campaigns/:id` | Campaign detail + deliverables |
| POST | `/api/campaigns` | Create campaign |
| PUT | `/api/campaigns/:id/status` | Sync pipeline status |
| POST | `/api/campaigns/:id/deliverables` | Upload deliverable |
| GET | `/api/campaigns/:id/deliverables/:did/download` | Download deliverable |

## CLI Commands

```
/marketing cloud setup        - Configure Supabase connection
/marketing cloud status       - Check connection
/marketing cloud register     - Register new account
/marketing teams list         - List teams
/marketing teams create <n>   - Create team
/marketing teams invite <e>   - Invite member
/marketing teams join <token> - Accept invite
/marketing teams switch <id>  - Switch active team
/marketing teams members      - List members
/marketing share <slug>       - Upload local campaign to cloud
/marketing browse             - Browse team campaigns
```

## Security

- API keys are stored hashed-equivalent (plain UUID, transmitted via header)
- Row Level Security (RLS) on all tables — users only see their team data
- Storage paths scoped by team ID — cross-team access blocked by RLS
- Dashboard cloud secrets are loaded from a local `cloud-config.json` bootstrap file, not URL query params
- Service role key (API server only) must be kept secret

## Troubleshooting

**Cloud not connecting**: Check `MARKETING_CLOUD_API_KEY` is set and `~/.marketing-pipeline/cloud.json` exists with correct Supabase URL/key.

**Dashboard not updating in real-time**: Ensure the migration enabled Realtime on the campaigns table. Check browser console for WebSocket errors.

**Upload failures**: Check Supabase Storage bucket `campaign-deliverables` exists. Max file size is 100MB.
