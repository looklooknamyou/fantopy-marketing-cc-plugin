const { Router } = require('express');
const path = require('path');
const multer = require('multer');
const { authMiddleware, teamMemberMiddleware } = require('../middleware/auth');
const router = Router();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 25 * 1024 * 1024 } });

const VALID_MODES = ['full-funnel', 'content-production', 'market-intelligence'];

router.use(authMiddleware);

// Helper: check team membership for a campaign, returns { campaign, membership } or sends error
async function requireCampaignAccess(req, res, opts = {}) {
  const { data: campaign } = await req.supabase
    .from('campaigns')
    .select(opts.select || 'team_id, slug')
    .eq('id', opts.campaignId || req.params.id)
    .single();

  if (!campaign) { res.status(404).json({ error: 'Campaign not found' }); return null; }

  const { data: membership } = await req.supabase
    .from('team_members')
    .select('role')
    .eq('team_id', campaign.team_id)
    .eq('user_id', req.user.id)
    .single();

  if (!membership) { res.status(403).json({ error: 'Not a member of this team' }); return null; }

  return { campaign, membership };
}

// Helper: sanitize file path — reject traversal and absolute paths
function sanitizePath(filePath) {
  if (!filePath) return null;
  const normalized = path.posix.normalize(filePath);
  if (normalized.startsWith('/') || normalized.startsWith('..') || normalized.includes('/../')) return null;
  return normalized;
}

// GET /api/campaigns?team_id=xxx
router.get('/', async (req, res) => {
  const teamId = req.query.team_id;
  if (!teamId) return res.status(400).json({ error: 'team_id query param required' });

  const { data: membership } = await req.supabase
    .from('team_members')
    .select('role')
    .eq('team_id', teamId)
    .eq('user_id', req.user.id)
    .single();

  if (!membership) return res.status(403).json({ error: 'Not a member' });

  const { data: campaigns, error } = await req.supabase
    .from('campaigns')
    .select('id, slug, name, mode, status, started_at, completed_at, created_at, users!created_by(display_name)')
    .eq('team_id', teamId)
    .order('created_at', { ascending: false });

  if (error) return res.status(500).json({ error: error.message });

  res.json({ campaigns });
});

// GET /api/campaigns/:id
router.get('/:id', async (req, res) => {
  const access = await requireCampaignAccess(req, res, { select: '*, users!created_by(display_name)' });
  if (!access) return;

  const { data: deliverables } = await req.supabase
    .from('deliverables')
    .select('*')
    .eq('campaign_id', access.campaign.id)
    .order('created_at');

  res.json({ campaign: access.campaign, deliverables: deliverables || [] });
});

// POST /api/campaigns
router.post('/', async (req, res) => {
  const { team_id, slug, name, mode } = req.body;
  if (!team_id || !slug || !name) {
    return res.status(400).json({ error: 'team_id, slug, and name required' });
  }

  const campaignMode = mode || 'full-funnel';
  if (!VALID_MODES.includes(campaignMode)) {
    return res.status(400).json({ error: 'Invalid mode. Must be one of: ' + VALID_MODES.join(', ') });
  }

  const { data: membership } = await req.supabase
    .from('team_members')
    .select('role')
    .eq('team_id', team_id)
    .eq('user_id', req.user.id)
    .single();

  if (!membership) return res.status(403).json({ error: 'Not a member' });
  if (membership.role === 'viewer') return res.status(403).json({ error: 'Viewers cannot create campaigns' });

  const { data, error } = await req.supabase
    .from('campaigns')
    .insert({
      team_id,
      created_by: req.user.id,
      slug,
      name,
      mode: campaignMode
    })
    .select()
    .single();

  if (error) {
    if (error.code === '23505') {
      return res.status(409).json({ error: 'Campaign slug already exists in this team' });
    }
    return res.status(500).json({ error: error.message });
  }

  res.status(201).json({ campaign: data });
});

// PUT /api/campaigns/:id/status  [C3 fix: added team membership check]
router.put('/:id/status', async (req, res) => {
  const { pipeline_status } = req.body;
  if (!pipeline_status) return res.status(400).json({ error: 'pipeline_status required' });

  const access = await requireCampaignAccess(req, res);
  if (!access) return;
  if (access.membership.role === 'viewer') {
    return res.status(403).json({ error: 'Viewers cannot update campaign status' });
  }

  const status = pipeline_status.status === 'complete' || pipeline_status.status === 'done'
    ? 'done'
    : pipeline_status.status === 'failed' ? 'failed' : 'running';

  const updateData = { pipeline_status, status };

  if (status === 'running' && pipeline_status.startTime) {
    updateData.started_at = pipeline_status.startTime;
  }
  if (status === 'done' && pipeline_status.endTime) {
    updateData.completed_at = pipeline_status.endTime;
  }

  const { data, error } = await req.supabase
    .from('campaigns')
    .update(updateData)
    .eq('id', req.params.id)
    .select()
    .single();

  if (error) return res.status(500).json({ error: error.message });

  res.json({ campaign: data });
});

// POST /api/campaigns/:id/deliverables  [C4 fix: added team membership check + H8: path sanitization]
router.post('/:id/deliverables', upload.single('file'), async (req, res) => {
  const campaignId = req.params.id;
  const { name, path: filePath } = req.body;

  if (!req.file || !name || !filePath) {
    return res.status(400).json({ error: 'file, name, and path required' });
  }

  const safePath = sanitizePath(filePath);
  if (!safePath) {
    return res.status(400).json({ error: 'Invalid file path' });
  }

  const access = await requireCampaignAccess(req, res, { campaignId });
  if (!access) return;
  if (access.membership.role === 'viewer') {
    return res.status(403).json({ error: 'Viewers cannot upload deliverables' });
  }

  const storagePath = `${access.campaign.team_id}/${access.campaign.slug}/${safePath}`;

  const { error: storageError } = await req.supabase.storage
    .from('campaign-deliverables')
    .upload(storagePath, req.file.buffer, {
      contentType: req.file.mimetype,
      upsert: true
    });

  if (storageError) return res.status(500).json({ error: storageError.message });

  const { data, error } = await req.supabase
    .from('deliverables')
    .upsert({
      campaign_id: campaignId,
      name,
      path: safePath,
      storage_path: storagePath,
      size_bytes: req.file.size,
      mime_type: req.file.mimetype
    }, { onConflict: 'campaign_id,path' })
    .select()
    .single();

  if (error) return res.status(500).json({ error: error.message });

  res.status(201).json({ deliverable: data });
});

// GET /api/campaigns/:id/deliverables/:deliverableId/download  [C5 fix: added team membership check + H9: header injection fix]
router.get('/:id/deliverables/:deliverableId/download', async (req, res) => {
  const access = await requireCampaignAccess(req, res);
  if (!access) return;

  const { data: deliverable } = await req.supabase
    .from('deliverables')
    .select('storage_path, name, mime_type')
    .eq('id', req.params.deliverableId)
    .eq('campaign_id', req.params.id)
    .single();

  if (!deliverable) return res.status(404).json({ error: 'Deliverable not found' });

  const { data, error } = await req.supabase.storage
    .from('campaign-deliverables')
    .download(deliverable.storage_path);

  if (error) return res.status(500).json({ error: error.message });

  const safeName = deliverable.name.replace(/["\\\r\n]/g, '_');
  res.setHeader('Content-Type', deliverable.mime_type);
  res.setHeader('Content-Disposition', `attachment; filename="${safeName}"`);
  const buffer = Buffer.from(await data.arrayBuffer());
  res.send(buffer);
});

module.exports = router;
