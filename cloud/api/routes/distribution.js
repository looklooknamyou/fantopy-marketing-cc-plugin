const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const crypto = require('crypto');
const { authMiddleware } = require('../middleware/auth');

const CONFIG_PATH = path.join(process.env.HOME, '.marketing-pipeline', 'distribution.json');
const CONFIG_DIR = path.dirname(CONFIG_PATH);

// All distribution routes require authentication
router.use(authMiddleware);

// Helper: read config file
function readConfig() {
  if (!fs.existsSync(CONFIG_PATH)) return null;
  return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
}

// Helper: write config file with restricted permissions
function writeConfig(config) {
  if (!fs.existsSync(CONFIG_DIR)) fs.mkdirSync(CONFIG_DIR, { recursive: true });
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2));
  fs.chmodSync(CONFIG_PATH, 0o600);
}

// Helper: mask sensitive values for display
function maskConfig(config) {
  if (!config) return {};
  const masked = {};
  const secretKeys = new Set([
    'client_secret', 'password', 'api_key', 'api_secret',
    'access_token', 'access_token_secret', 'bot_token', 'webhook_url'
  ]);

  for (const [platform, cfg] of Object.entries(config)) {
    if (typeof cfg !== 'object' || cfg === null) continue;
    masked[platform] = {};
    for (const [key, val] of Object.entries(cfg)) {
      if (secretKeys.has(key) && val) {
        // Show first 4 and last 4 chars for long secrets, otherwise just dots
        const s = String(val);
        masked[platform][key] = s.length > 12
          ? s.slice(0, 4) + '\u2022'.repeat(8) + s.slice(-4)
          : '\u2022'.repeat(8);
      } else {
        masked[platform][key] = val;
      }
    }
  }
  return masked;
}

// Helper: simple HTTPS/HTTP request
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

// GET /api/distribution/config — read config (secrets masked)
router.get('/config', (req, res) => {
  const config = readConfig();
  if (!config) {
    return res.json({ configured: false, platforms: {} });
  }
  return res.json({ configured: true, platforms: maskConfig(config) });
});

// GET /api/distribution/config/raw — read raw config (for pre-filling forms)
// Returns actual values — only accessible to authenticated users
router.get('/config/raw', (req, res) => {
  const config = readConfig();
  if (!config) {
    return res.json({ configured: false, platforms: {} });
  }
  return res.json({ configured: true, platforms: config });
});

// PUT /api/distribution/config/:platform — save one platform's config
router.put('/config/:platform', (req, res) => {
  const { platform } = req.params;
  const validPlatforms = ['reddit', 'twitter', 'telegram', 'discord'];
  if (!validPlatforms.includes(platform)) {
    return res.status(400).json({ error: 'Invalid platform. Must be: ' + validPlatforms.join(', ') });
  }

  const config = readConfig() || {};
  config[platform] = req.body;
  writeConfig(config);

  return res.json({ success: true, platform });
});

// DELETE /api/distribution/config/:platform — remove a platform's config
router.delete('/config/:platform', (req, res) => {
  const { platform } = req.params;
  const config = readConfig();
  if (!config || !config[platform]) {
    return res.status(404).json({ error: 'Platform not configured' });
  }
  delete config[platform];
  writeConfig(config);
  return res.json({ success: true, platform });
});

// POST /api/distribution/test/:platform — test connectivity
router.post('/test/:platform', async (req, res) => {
  const { platform } = req.params;
  const config = readConfig();
  if (!config || !config[platform]) {
    return res.status(404).json({ error: 'Platform not configured' });
  }

  const cfg = config[platform];
  try {
    switch (platform) {
      case 'reddit': {
        const authBody = `grant_type=password&username=${encodeURIComponent(cfg.username)}&password=${encodeURIComponent(cfg.password)}`;
        const authHeader = 'Basic ' + Buffer.from(`${cfg.client_id}:${cfg.client_secret}`).toString('base64');
        const resp = await httpRequest('https://www.reddit.com/api/v1/access_token', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': authHeader,
            'User-Agent': cfg.user_agent || 'MarketingPipeline/1.0'
          },
          body: authBody
        });
        const data = JSON.parse(resp.body);
        if (data.access_token) {
          return res.json({ success: true, message: `Authenticated as u/${cfg.username}`, subreddit: cfg.default_subreddit });
        }
        return res.json({ success: false, message: data.error || 'Auth failed' });
      }

      case 'twitter': {
        // OAuth 1.0a signed GET /2/users/me
        const url = 'https://api.twitter.com/2/users/me';
        const oauthParams = {
          oauth_consumer_key: cfg.api_key,
          oauth_nonce: crypto.randomBytes(16).toString('hex'),
          oauth_signature_method: 'HMAC-SHA1',
          oauth_timestamp: Math.floor(Date.now() / 1000).toString(),
          oauth_token: cfg.access_token,
          oauth_version: '1.0'
        };
        const pEnc = s => encodeURIComponent(s).replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
        const paramStr = Object.keys(oauthParams).sort().map(k => `${pEnc(k)}=${pEnc(oauthParams[k])}`).join('&');
        const baseStr = ['GET', pEnc(url), pEnc(paramStr)].join('&');
        const sigKey = `${pEnc(cfg.api_secret)}&${pEnc(cfg.access_token_secret)}`;
        oauthParams.oauth_signature = crypto.createHmac('sha1', sigKey).update(baseStr).digest('base64');
        const authHeader = 'OAuth ' + Object.keys(oauthParams).sort().filter(k => k.startsWith('oauth_')).map(k => `${pEnc(k)}="${pEnc(oauthParams[k])}"`).join(', ');

        const resp = await httpRequest(url, { headers: { 'Authorization': authHeader, 'User-Agent': 'MarketingPipeline/1.0' } });
        const data = JSON.parse(resp.body);
        if (data.data && data.data.username) {
          return res.json({ success: true, message: `Authenticated as @${data.data.username}` });
        }
        return res.json({ success: false, message: data.detail || data.title || 'Auth failed' });
      }

      case 'telegram': {
        const resp = await httpRequest(`https://api.telegram.org/bot${cfg.bot_token}/getMe`);
        const data = JSON.parse(resp.body);
        if (data.ok && data.result) {
          return res.json({ success: true, message: `Bot: @${data.result.username} (${data.result.first_name})`, chatId: cfg.chat_id });
        }
        return res.json({ success: false, message: data.description || 'Failed' });
      }

      case 'discord': {
        // Validate webhook URL format
        if (!/^https:\/\/(discord\.com|discordapp\.com)\/api\/webhooks\/\d+\/.+$/.test(cfg.webhook_url)) {
          return res.json({ success: false, message: 'Invalid webhook URL format' });
        }
        const resp = await httpRequest(cfg.webhook_url);
        if (resp.statusCode === 200) {
          const data = JSON.parse(resp.body);
          return res.json({ success: true, message: `Webhook: ${data.name || 'OK'} in #${data.channel_id || 'unknown'}` });
        }
        return res.json({ success: false, message: `HTTP ${resp.statusCode}` });
      }

      default:
        return res.status(400).json({ error: 'Unknown platform' });
    }
  } catch (err) {
    return res.json({ success: false, message: err.message });
  }
});

module.exports = router;
