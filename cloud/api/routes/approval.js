const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');
const { authMiddleware } = require('../middleware/auth');

// All approval routes require authentication
router.use(authMiddleware);

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const VALID_PLATFORMS = ['reddit', 'twitter', 'telegram', 'discord'];
const MAX_COMMENT_LENGTH = 5000;

// Helper: validate campaignId and verify team membership
async function validateCampaignAccess(req, res, fields) {
  const { campaignId } = req.params;
  if (!UUID_RE.test(campaignId)) {
    res.status(400).json({ error: 'Invalid campaign ID format' });
    return null;
  }

  const selectFields = ['id', 'team_id', ...fields].join(', ');
  const { data, error } = await req.supabase
    .from('campaigns')
    .select(selectFields)
    .eq('id', campaignId)
    .single();

  if (error || !data) {
    res.status(404).json({ error: 'Campaign not found' });
    return null;
  }

  // Verify user is a member of the campaign's team
  const { data: membership, error: memErr } = await req.supabase
    .from('team_members')
    .select('role')
    .eq('team_id', data.team_id)
    .eq('user_id', req.user.id)
    .single();

  if (memErr || !membership) {
    res.status(403).json({ error: 'Not a member of this campaign\'s team' });
    return null;
  }

  return data;
}

// GET /api/approval/:campaignId — get approval state
router.get('/:campaignId', async (req, res) => {
  try {
    const campaign = await validateCampaignAccess(req, res, ['slug', 'status', 'approval_status']);
    if (!campaign) return;

    return res.json({
      campaignId: campaign.id,
      slug: campaign.slug,
      campaignStatus: campaign.status,
      approvalStatus: campaign.approval_status || null
    });
  } catch (e) {
    console.error('[approval] GET error:', e.message);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// PUT /api/approval/:campaignId — update approval decisions
router.put('/:campaignId', async (req, res) => {
  try {
    const { action, deliverable, platform, comment } = req.body;

    const validActions = ['approve_all', 'reject_all', 'approve_item', 'reject_item'];
    if (!validActions.includes(action)) {
      return res.status(400).json({ error: 'Invalid action. Must be: ' + validActions.join(', ') });
    }

    const campaign = await validateCampaignAccess(req, res, ['approval_status']);
    if (!campaign) return;

    let approval = campaign.approval_status || { status: 'pending', deliverables: {} };

    if (action === 'approve_all') {
      approval.status = 'approved';
      approval.decidedAt = new Date().toISOString();
      approval.decidedBy = req.user.id;
      for (const deliv of Object.values(approval.deliverables || {})) {
        if (deliv.platforms) {
          for (const p of Object.keys(deliv.platforms)) {
            deliv.platforms[p] = 'approved';
          }
        }
      }
    } else if (action === 'reject_all') {
      approval.status = 'rejected';
      approval.decidedAt = new Date().toISOString();
      approval.decidedBy = req.user.id;
      for (const deliv of Object.values(approval.deliverables || {})) {
        if (deliv.platforms) {
          for (const p of Object.keys(deliv.platforms)) {
            deliv.platforms[p] = 'rejected';
          }
        }
      }
    } else if (action === 'approve_item' || action === 'reject_item') {
      if (!deliverable || typeof deliverable !== 'string') {
        return res.status(400).json({ error: 'deliverable path required (string) for per-item actions' });
      }
      const decision = action === 'approve_item' ? 'approved' : 'rejected';

      if (!approval.deliverables[deliverable]) {
        return res.status(404).json({ error: 'Deliverable not found in approval status' });
      }

      if (platform) {
        if (!VALID_PLATFORMS.includes(platform)) {
          return res.status(400).json({ error: 'Invalid platform' });
        }
        if (approval.deliverables[deliverable].platforms) {
          approval.deliverables[deliverable].platforms[platform] = decision;
        }
      } else {
        if (approval.deliverables[deliverable].platforms) {
          for (const p of Object.keys(approval.deliverables[deliverable].platforms)) {
            approval.deliverables[deliverable].platforms[p] = decision;
          }
        }
      }

      if (comment && typeof comment === 'string' && approval.deliverables[deliverable]) {
        approval.deliverables[deliverable].comment = comment.slice(0, MAX_COMMENT_LENGTH);
      }

      // Check if all items are now decided
      const allDecided = Object.values(approval.deliverables).every(d =>
        d.platforms && Object.values(d.platforms).every(v => v !== 'pending')
      );
      if (allDecided) {
        const hasApproved = Object.values(approval.deliverables).some(d =>
          d.platforms && Object.values(d.platforms).some(v => v === 'approved')
        );
        approval.status = hasApproved ? 'approved' : 'rejected';
        approval.decidedAt = new Date().toISOString();
        approval.decidedBy = req.user.id;
      }
    }

    const { error: updateErr } = await req.supabase
      .from('campaigns')
      .update({ approval_status: approval })
      .eq('id', req.params.campaignId);

    if (updateErr) {
      console.error('[approval] PUT update error:', updateErr.message);
      return res.status(500).json({ error: 'Failed to update approval status' });
    }

    return res.json({ success: true, approvalStatus: approval });
  } catch (e) {
    console.error('[approval] PUT error:', e.message);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// POST /api/approval/:campaignId/sync-local — write approval state to local file
router.post('/:campaignId/sync-local', async (req, res) => {
  try {
    const { slug } = req.body;

    if (!slug || typeof slug !== 'string') {
      return res.status(400).json({ error: 'slug required (string)' });
    }

    // Validate slug format (no path traversal)
    if (/[\/\\]|\.\./.test(slug)) {
      return res.status(400).json({ error: 'Invalid slug format' });
    }

    const campaign = await validateCampaignAccess(req, res, ['approval_status', 'slug']);
    if (!campaign) return;

    if (!campaign.approval_status) {
      return res.status(404).json({ error: 'No approval status found' });
    }

    // Resolve output dir relative to marketing-output
    const outputDir = path.resolve('./marketing-output', campaign.slug);

    // Verify the resolved path is within marketing-output
    const baseDir = path.resolve('./marketing-output');
    if (!outputDir.startsWith(baseDir + path.sep) && outputDir !== baseDir) {
      return res.status(400).json({ error: 'Invalid output directory' });
    }

    const filePath = path.join(outputDir, 'approval-status.json');

    if (!fs.existsSync(outputDir)) {
      return res.status(404).json({ error: 'Campaign output directory not found' });
    }

    fs.writeFileSync(filePath, JSON.stringify(campaign.approval_status, null, 2));
    return res.json({ success: true, path: filePath });
  } catch (e) {
    console.error('[approval] sync-local error:', e.message);
    return res.status(500).json({ error: 'Failed to sync approval locally' });
  }
});

module.exports = router;
