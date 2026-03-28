-- ============================================================
-- 001_initial.sql - Marketing Pipeline Cloud Schema
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    api_key TEXT UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(32), 'hex'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_api_key ON users(api_key);
CREATE INDEX idx_users_email ON users(email);

-- ============================================================
-- TEAMS (workspaces)
-- ============================================================
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_teams_slug ON teams(slug);

-- ============================================================
-- TEAM MEMBERS
-- ============================================================
CREATE TYPE team_role AS ENUM ('owner', 'admin', 'member', 'viewer');

CREATE TABLE team_members (
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role team_role NOT NULL DEFAULT 'member',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (team_id, user_id)
);

CREATE INDEX idx_team_members_user ON team_members(user_id);

-- ============================================================
-- CAMPAIGNS
-- ============================================================
CREATE TYPE campaign_status AS ENUM ('pending', 'running', 'done', 'failed');

CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'full-funnel',
    status campaign_status NOT NULL DEFAULT 'pending',
    pipeline_status JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(team_id, slug)
);

CREATE INDEX idx_campaigns_team ON campaigns(team_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);

-- ============================================================
-- DELIVERABLES
-- ============================================================
CREATE TABLE deliverables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    storage_path TEXT,
    size_bytes BIGINT,
    mime_type TEXT DEFAULT 'text/markdown',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_deliverables_campaign ON deliverables(campaign_id);
CREATE UNIQUE INDEX idx_deliverables_campaign_path ON deliverables(campaign_id, path);

-- ============================================================
-- INVITATIONS
-- ============================================================
CREATE TYPE invitation_status AS ENUM ('pending', 'accepted', 'expired', 'revoked');

CREATE TABLE invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    invited_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(24), 'hex'),
    role team_role NOT NULL DEFAULT 'member',
    status invitation_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '7 days')
);

CREATE INDEX idx_invitations_token ON invitations(token);
CREATE INDEX idx_invitations_token_status ON invitations(token, status);
CREATE INDEX idx_invitations_email ON invitations(email);

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Get user_id from API key (set via request header)
CREATE OR REPLACE FUNCTION public.user_id_from_api_key()
RETURNS UUID AS $$
    SELECT id FROM public.users
    WHERE api_key = current_setting('request.headers', true)::json->>'x-api-key'
    LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- Check team membership
CREATE OR REPLACE FUNCTION public.is_team_member(p_team_id UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS(
        SELECT 1 FROM public.team_members
        WHERE team_id = p_team_id
        AND user_id = public.user_id_from_api_key()
    );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE deliverables ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;

-- Users: can only see/update themselves; insert/delete via service role only
CREATE POLICY users_select ON users FOR SELECT
    USING (id = public.user_id_from_api_key());
CREATE POLICY users_update ON users FOR UPDATE
    USING (id = public.user_id_from_api_key());

-- Teams: visible to members; only owners/admins can update
CREATE POLICY teams_select ON teams FOR SELECT
    USING (public.is_team_member(id));
CREATE POLICY teams_insert ON teams FOR INSERT
    WITH CHECK (created_by = public.user_id_from_api_key());
CREATE POLICY teams_update ON teams FOR UPDATE
    USING (EXISTS(
        SELECT 1 FROM team_members tm
        WHERE tm.team_id = id
        AND tm.user_id = public.user_id_from_api_key()
        AND tm.role IN ('owner', 'admin')
    ));

-- Team members: visible to fellow members; only owners/admins can insert/delete
CREATE POLICY team_members_select ON team_members FOR SELECT
    USING (public.is_team_member(team_id));
CREATE POLICY team_members_insert ON team_members FOR INSERT
    WITH CHECK (EXISTS(
        SELECT 1 FROM team_members tm
        WHERE tm.team_id = team_id
        AND tm.user_id = public.user_id_from_api_key()
        AND tm.role IN ('owner', 'admin')
    ) OR user_id = public.user_id_from_api_key());
CREATE POLICY team_members_delete ON team_members FOR DELETE
    USING (EXISTS(
        SELECT 1 FROM team_members tm
        WHERE tm.team_id = team_id
        AND tm.user_id = public.user_id_from_api_key()
        AND tm.role IN ('owner', 'admin')
    ));

-- Campaigns: visible to team members; delete restricted to owners/admins
CREATE POLICY campaigns_select ON campaigns FOR SELECT
    USING (public.is_team_member(team_id));
CREATE POLICY campaigns_insert ON campaigns FOR INSERT
    WITH CHECK (public.is_team_member(team_id));
CREATE POLICY campaigns_update ON campaigns FOR UPDATE
    USING (public.is_team_member(team_id));
CREATE POLICY campaigns_delete ON campaigns FOR DELETE
    USING (EXISTS(
        SELECT 1 FROM team_members tm
        WHERE tm.team_id = campaigns.team_id
        AND tm.user_id = public.user_id_from_api_key()
        AND tm.role IN ('owner', 'admin')
    ));

-- Deliverables: visible if campaign's team member
CREATE POLICY deliverables_select ON deliverables FOR SELECT
    USING (EXISTS(
        SELECT 1 FROM campaigns c
        WHERE c.id = campaign_id AND public.is_team_member(c.team_id)
    ));
CREATE POLICY deliverables_insert ON deliverables FOR INSERT
    WITH CHECK (EXISTS(
        SELECT 1 FROM campaigns c
        WHERE c.id = campaign_id AND public.is_team_member(c.team_id)
    ));
CREATE POLICY deliverables_update ON deliverables FOR UPDATE
    USING (EXISTS(
        SELECT 1 FROM campaigns c
        WHERE c.id = campaign_id AND public.is_team_member(c.team_id)
    ));
CREATE POLICY deliverables_delete ON deliverables FOR DELETE
    USING (EXISTS(
        SELECT 1 FROM campaigns c
        WHERE c.id = campaign_id AND public.is_team_member(c.team_id)
    ));

-- Invitations: team members can see their team's invites; update for accepting
CREATE POLICY invitations_select ON invitations FOR SELECT
    USING (public.is_team_member(team_id) OR email = (
        SELECT email FROM users WHERE id = public.user_id_from_api_key()
    ));
CREATE POLICY invitations_insert ON invitations FOR INSERT
    WITH CHECK (public.is_team_member(team_id));
CREATE POLICY invitations_update ON invitations FOR UPDATE
    USING (public.is_team_member(team_id) OR email = (
        SELECT email FROM users WHERE id = public.user_id_from_api_key()
    ));

-- ============================================================
-- REALTIME
-- ============================================================
ALTER PUBLICATION supabase_realtime ADD TABLE campaigns;

-- ============================================================
-- STORAGE
-- ============================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('campaign-deliverables', 'campaign-deliverables', false);

-- Storage: scoped to team membership via path prefix (team_id/...)
CREATE POLICY storage_read ON storage.objects FOR SELECT
    USING (bucket_id = 'campaign-deliverables' AND EXISTS(
        SELECT 1 FROM team_members tm
        WHERE tm.user_id = public.user_id_from_api_key()
        AND tm.team_id::text = split_part(name, '/', 1)
    ));

CREATE POLICY storage_insert ON storage.objects FOR INSERT
    WITH CHECK (bucket_id = 'campaign-deliverables' AND EXISTS(
        SELECT 1 FROM team_members tm
        WHERE tm.user_id = public.user_id_from_api_key()
        AND tm.team_id::text = split_part(name, '/', 1)
    ));

-- ============================================================
-- UPDATED_AT TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER teams_updated_at BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER campaigns_updated_at BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
