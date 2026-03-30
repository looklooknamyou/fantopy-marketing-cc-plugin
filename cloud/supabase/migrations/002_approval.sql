-- ============================================================
-- 002_approval.sql - Content Approval/Staging Support
-- ============================================================

-- Add 'awaiting_approval' status to campaign lifecycle
ALTER TYPE campaign_status ADD VALUE IF NOT EXISTS 'awaiting_approval' AFTER 'running';

-- Store per-deliverable, per-platform approval decisions
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS approval_status JSONB;
