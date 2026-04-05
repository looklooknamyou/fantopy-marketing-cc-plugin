const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { authMiddleware } = require('../middleware/auth');

const HOME_DIR = process.env.HOME || process.env.USERPROFILE;
const LEGACY_CONFIG_PATH = path.join(HOME_DIR, '.marketing-pipeline', 'staging-config.json');
const CONFIG_ROOT = path.join(HOME_DIR, '.marketing-pipeline', 'staging-cloud');
const TEAM_ID_RE = /^[0-9a-f-]{36}$/i;

router.use(authMiddleware);

function getTeamId(req) {
  return req.query.team_id || req.body.team_id || null;
}

function getConfigPath(teamId) {
  if (!TEAM_ID_RE.test(teamId || '')) return null;
  return path.join(CONFIG_ROOT, `${teamId}.json`);
}

function normalizeConfig(config) {
  const drive = config && typeof config.drive === 'object' && config.drive ? { ...config.drive } : {};
  const telegram = config && typeof config.telegram === 'object' && config.telegram ? { ...config.telegram } : {};

  const credentialsPath = drive.credentials_path || drive.key_path || '';
  if (credentialsPath) {
    drive.credentials_path = credentialsPath;
    drive.key_path = credentialsPath;
  } else {
    delete drive.credentials_path;
    delete drive.key_path;
  }

  return { drive, telegram };
}

function readJsonFile(filePath) {
  if (!filePath || !fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (err) {
    return null;
  }
}

function readConfig(teamId) {
  const configPath = getConfigPath(teamId);
  const teamConfig = readJsonFile(configPath);
  if (teamConfig) return normalizeConfig(teamConfig);

  const legacyConfig = readJsonFile(LEGACY_CONFIG_PATH);
  if (legacyConfig) return normalizeConfig(legacyConfig);

  return null;
}

function writeConfig(teamId, config) {
  const configPath = getConfigPath(teamId);
  if (!configPath) throw new Error('Invalid team ID');
  if (!fs.existsSync(CONFIG_ROOT)) fs.mkdirSync(CONFIG_ROOT, { recursive: true });
  fs.writeFileSync(configPath, JSON.stringify(normalizeConfig(config), null, 2));
  fs.chmodSync(configPath, 0o600);
}

function deleteConfig(teamId) {
  const configPath = getConfigPath(teamId);
  if (configPath && fs.existsSync(configPath)) fs.unlinkSync(configPath);
}

async function requireTeamAccess(req, res, opts = {}) {
  const teamId = getTeamId(req);
  if (!teamId) {
    res.status(400).json({ error: 'team_id is required' });
    return null;
  }
  if (!TEAM_ID_RE.test(teamId)) {
    res.status(400).json({ error: 'Invalid team_id format' });
    return null;
  }

  const { data: membership, error } = await req.supabase
    .from('team_members')
    .select('role')
    .eq('team_id', teamId)
    .eq('user_id', req.user.id)
    .single();

  if (error || !membership) {
    res.status(403).json({ error: 'Not a member of this team' });
    return null;
  }

  if (opts.write && !['owner', 'admin'].includes(membership.role)) {
    res.status(403).json({ error: 'Only owners and admins can manage staging integrations' });
    return null;
  }

  return { teamId, role: membership.role, canEdit: ['owner', 'admin'].includes(membership.role) };
}

function maskConfig(config) {
  if (!config) return { drive: {}, telegram: {} };
  const normalized = normalizeConfig(config);
  const masked = { drive: { ...normalized.drive }, telegram: { ...normalized.telegram } };

  if (masked.telegram.bot_token) {
    const token = String(masked.telegram.bot_token);
    masked.telegram.bot_token = token.length > 12 ? token.slice(0, 4) + '••••••••' + token.slice(-4) : '••••••••';
  }

  return masked;
}

function httpRequest(url, opts = {}) {
  return new Promise((resolve, reject) => {
    const parsed = new (require('url').URL)(url);
    const mod = parsed.protocol === 'https:' ? https : http;
    const reqOpts = {
      hostname: parsed.hostname,
      port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
      path: parsed.pathname + parsed.search,
      method: opts.method || 'GET',
      headers: opts.headers || {}
    };
    const req = mod.request(reqOpts, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve({ statusCode: res.statusCode, body: Buffer.concat(chunks).toString('utf8') }));
    });
    req.setTimeout(15000, () => req.destroy(new Error('Timeout')));
    req.on('error', reject);
    if (opts.body) req.write(opts.body);
    req.end();
  });
}

function mergeServiceConfig(existingConfig, service, serviceConfig) {
  const normalized = normalizeConfig(existingConfig || {});
  normalized[service] = { ...(normalized[service] || {}), ...serviceConfig };
  return normalizeConfig(normalized);
}

router.get('/config', async (req, res) => {
  const access = await requireTeamAccess(req, res);
  if (!access) return;
  const config = readConfig(access.teamId);
  if (!config) {
    return res.json({ configured: false, integrations: { drive: {}, telegram: {} }, role: access.role, can_edit: access.canEdit });
  }
  return res.json({ configured: true, integrations: maskConfig(config), role: access.role, can_edit: access.canEdit });
});

router.get('/config/raw', async (req, res) => {
  const access = await requireTeamAccess(req, res, { write: true });
  if (!access) return;
  const config = readConfig(access.teamId);
  if (!config) {
    return res.json({ configured: false, integrations: { drive: {}, telegram: {} }, role: access.role, can_edit: access.canEdit });
  }
  return res.json({ configured: true, integrations: normalizeConfig(config), role: access.role, can_edit: access.canEdit });
});

router.put('/config/:service', async (req, res) => {
  const { service } = req.params;
  if (!['drive', 'telegram'].includes(service)) {
    return res.status(400).json({ error: 'Invalid service. Must be drive or telegram' });
  }

  const access = await requireTeamAccess(req, res, { write: true });
  if (!access) return;

  const nextConfig = { ...req.body };
  delete nextConfig.team_id;
  const merged = mergeServiceConfig(readConfig(access.teamId), service, nextConfig);
  writeConfig(access.teamId, merged);
  return res.json({ success: true, service });
});

router.delete('/config/:service', async (req, res) => {
  const { service } = req.params;
  if (!['drive', 'telegram'].includes(service)) {
    return res.status(400).json({ error: 'Invalid service. Must be drive or telegram' });
  }

  const access = await requireTeamAccess(req, res, { write: true });
  if (!access) return;

  const config = readConfig(access.teamId);
  if (!config || !config[service] || Object.keys(config[service]).length === 0) {
    return res.status(404).json({ error: 'Service not configured' });
  }

  config[service] = {};
  if (Object.keys(config.drive || {}).length === 0 && Object.keys(config.telegram || {}).length === 0) deleteConfig(access.teamId);
  else writeConfig(access.teamId, config);
  return res.json({ success: true, service });
});

router.post('/test/:service', async (req, res) => {
  const { service } = req.params;
  if (!['drive', 'telegram'].includes(service)) {
    return res.status(400).json({ error: 'Invalid service. Must be drive or telegram' });
  }

  const access = await requireTeamAccess(req, res, { write: true });
  if (!access) return;

  const config = readConfig(access.teamId);
  if (!config || !config[service] || Object.keys(config[service]).length === 0) {
    return res.status(404).json({ error: 'Service not configured' });
  }

  try {
    if (service === 'telegram') {
      const resp = await httpRequest(`https://api.telegram.org/bot${config.telegram.bot_token}/getMe`);
      const data = JSON.parse(resp.body);
      if (data.ok && data.result) {
        return res.json({ success: true, message: `Bot: @${data.result.username} (${data.result.first_name})`, chatId: config.telegram.chat_id });
      }
      return res.json({ success: false, message: data.description || 'Failed' });
    }

    const credentialsPath = config.drive.credentials_path || config.drive.key_path;
    if (!credentialsPath) return res.json({ success: false, message: 'Missing credentials_path' });
    if (!config.drive.folder_id) return res.json({ success: false, message: 'Missing folder_id' });
    if (!fs.existsSync(credentialsPath)) return res.json({ success: false, message: `Credentials file not found: ${credentialsPath}` });
    JSON.parse(fs.readFileSync(credentialsPath, 'utf8'));
    return res.json({ success: true, message: `Credentials file and folder ID look valid`, folderId: config.drive.folder_id });
  } catch (err) {
    return res.json({ success: false, message: err.message });
  }
});

module.exports = router;
