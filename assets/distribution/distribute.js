#!/usr/bin/env node
// ============================================================
// distribute.js — Marketing Pipeline Distribution Helper
// Zero npm dependencies. Uses only Node.js built-in modules.
// Posts campaign content to Reddit, Twitter/X, Telegram, Discord.
// ============================================================

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { URL } = require('url');

// ============================================================
// UTILITIES
// ============================================================

function loadJSON(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeJSON(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
}

function log(platform, msg) {
  const ts = new Date().toISOString().slice(11, 19);
  console.log(`[${ts}] [${platform.toUpperCase()}] ${msg}`);
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

/**
 * Safe JSON parse with descriptive error context.
 */
function parseJSON(body, context) {
  try {
    return JSON.parse(body);
  } catch (e) {
    throw new Error(`${context}: Expected JSON but got: ${body.slice(0, 500)}`);
  }
}

/**
 * Strip sensitive tokens from URLs for safe error logging.
 */
function sanitizeUrl(url) {
  return url.replace(/\/bot[A-Za-z0-9:_-]+\//, '/bot<REDACTED>/');
}

/**
 * Validate that a media file path resolves within the allowed base directory.
 * Returns the absolute path if valid, or null if path traversal detected.
 */
function validateMediaPath(filePath, baseDir) {
  if (!filePath) return null;
  const absPath = path.resolve(filePath);
  const absBase = path.resolve(baseDir);
  if (!absPath.startsWith(absBase + path.sep) && absPath !== absBase) {
    log('security', `Blocked path traversal: ${filePath} resolves outside ${baseDir}`);
    return null;
  }
  return absPath;
}

/**
 * Check HTTP status code and throw descriptive error for failures.
 */
function checkHttpStatus(resp, context) {
  if (resp.statusCode === 429) {
    const retryAfter = resp.headers['retry-after'] || 'unknown';
    throw new Error(`${context}: Rate limited (429). Retry after: ${retryAfter}s. Body: ${resp.body.slice(0, 300)}`);
  }
  if (resp.statusCode === 401 || resp.statusCode === 403) {
    throw new Error(`${context}: Authentication failed (${resp.statusCode}). Check credentials. Body: ${resp.body.slice(0, 300)}`);
  }
  if (resp.statusCode >= 400) {
    throw new Error(`${context}: HTTP ${resp.statusCode}. Body: ${resp.body.slice(0, 500)}`);
  }
}

/**
 * Make an HTTPS/HTTP request. Returns { statusCode, headers, body }.
 * Includes a configurable timeout (default 30s).
 */
function request(url, opts = {}) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
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
      res.on('end', () => {
        const body = Buffer.concat(chunks).toString('utf8');
        resolve({ statusCode: res.statusCode, headers: res.headers, body });
      });
    });

    // H1: Request timeout (default 30 seconds)
    const timeout = opts.timeout || 30000;
    req.setTimeout(timeout, () => {
      req.destroy(new Error(`Request timed out after ${timeout}ms: ${opts.method || 'GET'} ${sanitizeUrl(url)}`));
    });

    req.on('error', (err) => {
      // Sanitize any URLs in error messages to avoid leaking tokens
      const safeMsg = sanitizeUrl(err.message);
      reject(new Error(safeMsg));
    });
    if (opts.body) req.write(opts.body);
    req.end();
  });
}

/**
 * Build multipart/form-data body from fields and files.
 * Returns { boundary, body: Buffer }.
 */
function buildMultipart(fields = {}, files = {}) {
  const boundary = '----FormBoundary' + crypto.randomBytes(16).toString('hex');
  const parts = [];

  for (const [key, val] of Object.entries(fields)) {
    // M3: Escape double quotes in field names
    const safeKey = key.replace(/"/g, '\\"');
    parts.push(
      `--${boundary}\r\nContent-Disposition: form-data; name="${safeKey}"\r\n\r\n${val}\r\n`
    );
  }

  for (const [key, file] of Object.entries(files)) {
    // M3: Escape double quotes in key and filename
    const safeKey = key.replace(/"/g, '\\"');
    const rawFilename = file.filename || path.basename(file.path || 'file');
    const safeFilename = rawFilename.replace(/"/g, '\\"');
    const contentType = file.contentType || 'application/octet-stream';
    const data = file.data || fs.readFileSync(file.path);
    parts.push(
      `--${boundary}\r\nContent-Disposition: form-data; name="${safeKey}"; filename="${safeFilename}"\r\nContent-Type: ${contentType}\r\n\r\n`
    );
    parts.push(data);
    parts.push('\r\n');
  }

  parts.push(`--${boundary}--\r\n`);

  const buffers = parts.map(p => typeof p === 'string' ? Buffer.from(p) : p);
  return { boundary, body: Buffer.concat(buffers) };
}

// ============================================================
// REDDIT
// ============================================================

async function postToReddit(config, brief) {
  const { client_id, client_secret, username, password, user_agent, default_subreddit } = config;
  const reddit = brief.reddit;
  if (!reddit || !reddit.enabled) return { status: 'skipped', reason: 'disabled' };

  log('reddit', 'Obtaining OAuth2 token...');

  // Step 1: Get access token via password grant
  const authBody = `grant_type=password&username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`;
  const authHeader = 'Basic ' + Buffer.from(`${client_id}:${client_secret}`).toString('base64');

  const tokenResp = await request('https://www.reddit.com/api/v1/access_token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': authHeader,
      'User-Agent': user_agent || 'MarketingPipeline/1.0'
    },
    body: authBody
  });

  checkHttpStatus(tokenResp, 'Reddit OAuth');
  const tokenData = parseJSON(tokenResp.body, 'Reddit OAuth response');
  if (!tokenData.access_token) {
    throw new Error('Reddit auth failed: ' + (tokenData.error || tokenResp.body.slice(0, 300)));
  }

  log('reddit', 'Token obtained. Submitting post...');

  // M4: Validate content size (Reddit limit is 40000 chars for self posts)
  if (reddit.body && reddit.body.length > 40000) {
    throw new Error(`Reddit body exceeds 40000 character limit (got ${reddit.body.length})`);
  }
  if (reddit.title && reddit.title.length > 300) {
    throw new Error(`Reddit title exceeds 300 character limit (got ${reddit.title.length})`);
  }

  // Step 2: Submit post
  const subreddit = reddit.subreddit || default_subreddit || 'test';
  const submitBody = [
    'api_type=json',
    'kind=self',
    `sr=${encodeURIComponent(subreddit)}`,
    `title=${encodeURIComponent(reddit.title)}`,
    `text=${encodeURIComponent(reddit.body)}`
  ];
  if (reddit.flair) submitBody.push(`flair_text=${encodeURIComponent(reddit.flair)}`);

  const submitResp = await request('https://oauth.reddit.com/api/submit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': `Bearer ${tokenData.access_token}`,
      'User-Agent': user_agent || 'MarketingPipeline/1.0'
    },
    body: submitBody.join('&')
  });

  checkHttpStatus(submitResp, 'Reddit submit');
  const submitData = parseJSON(submitResp.body, 'Reddit submit response');
  const postUrl = submitData?.json?.data?.url;
  const postId = submitData?.json?.data?.id;

  if (!postUrl && submitData?.json?.errors?.length) {
    throw new Error('Reddit submit failed: ' + JSON.stringify(submitData.json.errors));
  }

  log('reddit', `Post submitted: ${postUrl || 'URL pending'}`);

  return {
    status: 'success',
    url: postUrl || `https://www.reddit.com/r/${subreddit}/`,
    postId: postId || null,
    subreddit,
    timestamp: new Date().toISOString()
  };
}

// ============================================================
// TWITTER/X — OAuth 1.0a
// ============================================================

function percentEncode(str) {
  return encodeURIComponent(str).replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
}

function generateOAuthParams(consumerKey, accessToken) {
  return {
    oauth_consumer_key: consumerKey,
    oauth_nonce: crypto.randomBytes(16).toString('hex'),
    oauth_signature_method: 'HMAC-SHA1',
    oauth_timestamp: Math.floor(Date.now() / 1000).toString(),
    oauth_token: accessToken,
    oauth_version: '1.0'
  };
}

function signRequest(method, url, params, consumerSecret, tokenSecret) {
  const paramString = Object.keys(params).sort()
    .map(k => `${percentEncode(k)}=${percentEncode(params[k])}`)
    .join('&');

  const baseString = [
    method.toUpperCase(),
    percentEncode(url),
    percentEncode(paramString)
  ].join('&');

  const signingKey = `${percentEncode(consumerSecret)}&${percentEncode(tokenSecret)}`;
  return crypto.createHmac('sha1', signingKey).update(baseString).digest('base64');
}

function buildOAuthHeader(oauthParams) {
  const parts = Object.keys(oauthParams).sort()
    .filter(k => k.startsWith('oauth_'))
    .map(k => `${percentEncode(k)}="${percentEncode(oauthParams[k])}"`)
    .join(', ');
  return `OAuth ${parts}`;
}

async function twitterRequest(method, url, body, config) {
  const { api_key, api_secret, access_token, access_token_secret } = config;
  const oauthParams = generateOAuthParams(api_key, access_token);

  // JSON body requests: only OAuth params go into the signature base string
  const sigParams = { ...oauthParams };
  const signature = signRequest(method, url, sigParams, api_secret, access_token_secret);
  oauthParams.oauth_signature = signature;

  const headers = {
    'Authorization': buildOAuthHeader(oauthParams),
    'Content-Type': 'application/json',
    'User-Agent': 'MarketingPipeline/1.0'
  };

  return request(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
}

/**
 * Upload media to Twitter using multipart/form-data.
 * C1 fix: Uses multipart instead of URL-encoded form to handle larger files.
 */
async function uploadTwitterMedia(filePath, config) {
  const { api_key, api_secret, access_token, access_token_secret } = config;
  const url = 'https://upload.twitter.com/1.1/media/upload.json';

  const fileData = fs.readFileSync(filePath);

  // For multipart uploads, only OAuth params go into the signature
  const oauthParams = generateOAuthParams(api_key, access_token);
  const sigParams = { ...oauthParams };
  const signature = signRequest('POST', url, sigParams, api_secret, access_token_secret);
  oauthParams.oauth_signature = signature;

  // Build multipart body with the file
  const ext = path.extname(filePath).toLowerCase();
  const mimeTypes = { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.mp4': 'video/mp4' };
  const contentType = mimeTypes[ext] || 'application/octet-stream';

  const { boundary, body } = buildMultipart(
    {},
    { media: { data: fileData, filename: path.basename(filePath), contentType } }
  );

  const resp = await request(url, {
    method: 'POST',
    headers: {
      'Authorization': buildOAuthHeader(oauthParams),
      'Content-Type': `multipart/form-data; boundary=${boundary}`,
      'User-Agent': 'MarketingPipeline/1.0'
    },
    body,
    timeout: 60000 // 60s timeout for media uploads
  });

  checkHttpStatus(resp, 'Twitter media upload');
  const data = parseJSON(resp.body, 'Twitter media upload response');
  if (!data.media_id_string) throw new Error('Media upload failed: ' + resp.body.slice(0, 300));
  return data.media_id_string;
}

async function postToTwitter(config, brief) {
  const twitter = brief.twitter;
  if (!twitter || !twitter.enabled) return { status: 'skipped', reason: 'disabled' };
  if (!twitter.thread || !twitter.thread.length) return { status: 'skipped', reason: 'no content' };

  // M4: Validate tweet lengths before posting any
  for (let i = 0; i < twitter.thread.length; i++) {
    const text = twitter.thread[i].text;
    if (!text) {
      return { status: 'failed', error: `Tweet ${i + 1} has no text`, timestamp: new Date().toISOString() };
    }
    if (text.length > 280) {
      return { status: 'failed', error: `Tweet ${i + 1} exceeds 280 character limit (got ${text.length})`, timestamp: new Date().toISOString() };
    }
  }

  log('twitter', `Posting thread of ${twitter.thread.length} tweets...`);

  const urls = [];
  let previousTweetId = null;

  for (let i = 0; i < twitter.thread.length; i++) {
    const tweet = twitter.thread[i];
    const body = { text: tweet.text };

    // Reply to previous tweet for thread
    if (previousTweetId) {
      body.reply = { in_reply_to_tweet_id: previousTweetId };
    }

    // Handle media attachment (M2: validate path within campaign dir)
    if (tweet.media && tweet.media.length > 0) {
      const mediaIds = [];
      for (const mediaPath of tweet.media) {
        const absPath = validateMediaPath(mediaPath, process.cwd());
        if (absPath && fs.existsSync(absPath)) {
          log('twitter', `Uploading media: ${path.basename(absPath)}`);
          try {
            const mediaId = await uploadTwitterMedia(absPath, config);
            mediaIds.push(mediaId);
          } catch (e) {
            log('twitter', `Media upload failed: ${e.message} — posting without media`);
          }
        } else if (!absPath) {
          log('twitter', `Media path rejected (outside campaign dir): ${mediaPath}`);
        }
      }
      if (mediaIds.length > 0) {
        body.media = { media_ids: mediaIds };
      }
    }

    const resp = await twitterRequest('POST', 'https://api.twitter.com/2/tweets', body, config);

    // H5: Check HTTP status before parsing
    if (resp.statusCode === 429) {
      const retryAfter = resp.headers['retry-after'] || '60';
      log('twitter', `Rate limited after tweet ${i + 1}. Retry after ${retryAfter}s. Waiting...`);
      // L1: Wait and retry once for rate limits
      await sleep(Math.min(parseInt(retryAfter, 10) || 60, 120) * 1000);
      const retryResp = await twitterRequest('POST', 'https://api.twitter.com/2/tweets', body, config);
      if (retryResp.statusCode === 429) {
        // H3: Return partial result with already-posted tweets
        return {
          status: urls.length > 0 ? 'partial' : 'failed',
          urls,
          failedAt: i + 1,
          error: `Rate limited on tweet ${i + 1} after retry`,
          threadLength: twitter.thread.length,
          timestamp: new Date().toISOString()
        };
      }
      Object.assign(resp, retryResp);
    }

    if (resp.statusCode >= 400) {
      // H3: Return partial result with already-posted tweets
      log('twitter', `Tweet ${i + 1} failed (HTTP ${resp.statusCode}): ${resp.body.slice(0, 300)}`);
      return {
        status: urls.length > 0 ? 'partial' : 'failed',
        urls,
        failedAt: i + 1,
        error: `Tweet ${i + 1} failed (HTTP ${resp.statusCode}): ${resp.body.slice(0, 300)}`,
        threadLength: twitter.thread.length,
        timestamp: new Date().toISOString()
      };
    }

    const data = parseJSON(resp.body, `Twitter tweet ${i + 1} response`);

    if (data.data && data.data.id) {
      previousTweetId = data.data.id;
      urls.push(`https://twitter.com/i/status/${data.data.id}`);
      log('twitter', `Tweet ${i + 1}/${twitter.thread.length} posted: ${data.data.id}`);
    } else {
      // H3: Return partial result with already-posted tweets
      log('twitter', `Tweet ${i + 1} unexpected response: ${resp.body.slice(0, 300)}`);
      return {
        status: urls.length > 0 ? 'partial' : 'failed',
        urls,
        failedAt: i + 1,
        error: `Tweet ${i + 1} failed: unexpected response format`,
        threadLength: twitter.thread.length,
        timestamp: new Date().toISOString()
      };
    }

    // Rate limit delay between tweets
    if (i < twitter.thread.length - 1) await sleep(3000);
  }

  return {
    status: 'success',
    urls,
    threadLength: twitter.thread.length,
    timestamp: new Date().toISOString()
  };
}

// ============================================================
// TELEGRAM
// ============================================================

async function postToTelegram(config, brief) {
  const { bot_token, chat_id } = config;
  const telegram = brief.telegram;
  if (!telegram || !telegram.enabled) return { status: 'skipped', reason: 'disabled' };

  // C3: Build base URL but never include it in error messages directly
  const baseUrl = `https://api.telegram.org/bot${bot_token}`;
  let photoMessageId = null;

  // M4: Validate Telegram message length
  if (telegram.text && telegram.text.length > 4096) {
    throw new Error(`Telegram message exceeds 4096 character limit (got ${telegram.text.length})`);
  }

  // Step 1: Send photo if specified (M2: validate path)
  if (telegram.photo) {
    const absPath = validateMediaPath(telegram.photo, process.cwd());
    if (absPath && fs.existsSync(absPath)) {
      log('telegram', 'Sending photo...');
      const caption = telegram.photo_caption || '';
      const { boundary, body } = buildMultipart(
        { chat_id, caption, parse_mode: 'HTML' },
        { photo: { path: absPath, contentType: 'image/png' } }
      );

      try {
        const resp = await request(`${baseUrl}/sendPhoto`, {
          method: 'POST',
          headers: { 'Content-Type': `multipart/form-data; boundary=${boundary}` },
          body,
          timeout: 60000 // 60s for photo uploads
        });

        checkHttpStatus(resp, 'Telegram sendPhoto');
        const data = parseJSON(resp.body, 'Telegram sendPhoto response');
        if (data.ok) {
          photoMessageId = data.result.message_id;
          log('telegram', `Photo sent: message_id ${photoMessageId}`);
        } else {
          log('telegram', `Photo failed: ${data.description}`);
        }
      } catch (e) {
        // C3: Sanitize error message to avoid leaking bot token
        log('telegram', `Photo failed: ${sanitizeUrl(e.message)}`);
      }
    } else if (!absPath) {
      log('telegram', `Photo path rejected (outside campaign dir): ${telegram.photo}`);
    }
  }

  // Step 2: Send text message with optional inline keyboard
  log('telegram', 'Sending message...');
  const msgBody = {
    chat_id,
    text: telegram.text,
    parse_mode: 'HTML',
    disable_web_page_preview: true
  };

  if (telegram.buttons && telegram.buttons.length > 0) {
    msgBody.reply_markup = { inline_keyboard: telegram.buttons };
  }

  try {
    const resp = await request(`${baseUrl}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(msgBody)
    });

    checkHttpStatus(resp, 'Telegram sendMessage');
    const data = parseJSON(resp.body, 'Telegram sendMessage response');
    if (!data.ok) throw new Error('Telegram sendMessage failed: ' + (data.description || 'unknown error'));

    log('telegram', `Message sent: message_id ${data.result.message_id}`);

    return {
      status: 'success',
      messageId: data.result.message_id,
      photoMessageId,
      chatId: chat_id,
      timestamp: new Date().toISOString()
    };
  } catch (e) {
    // C3: Sanitize error message to avoid leaking bot token
    throw new Error(sanitizeUrl(e.message));
  }
}

// ============================================================
// DISCORD
// ============================================================

const DISCORD_WEBHOOK_PATTERN = /^https:\/\/(discord\.com|discordapp\.com)\/api\/webhooks\/\d+\/.+$/;

async function postToDiscord(config, brief) {
  const { webhook_url } = config;
  const discord = brief.discord;
  if (!discord || !discord.enabled) return { status: 'skipped', reason: 'disabled' };

  // H4: Validate webhook URL format
  if (!webhook_url || !DISCORD_WEBHOOK_PATTERN.test(webhook_url)) {
    throw new Error('Invalid Discord webhook URL. Expected format: https://discord.com/api/webhooks/<id>/<token>');
  }

  // H4: Construct URL properly to avoid double question marks
  const webhookUrl = new URL(webhook_url);
  webhookUrl.searchParams.set('wait', 'true');
  const fullUrl = webhookUrl.toString();

  log('discord', 'Sending webhook...');

  const payload = {};
  if (discord.content) payload.content = discord.content;

  // M4: Validate Discord content limits
  if (discord.embed) {
    if (discord.embed.description && discord.embed.description.length > 4096) {
      throw new Error(`Discord embed description exceeds 4096 character limit (got ${discord.embed.description.length})`);
    }
    if (discord.embed.fields) {
      for (let i = 0; i < discord.embed.fields.length; i++) {
        if (discord.embed.fields[i].value && discord.embed.fields[i].value.length > 1024) {
          throw new Error(`Discord embed field ${i + 1} value exceeds 1024 character limit`);
        }
      }
      if (discord.embed.fields.length > 25) {
        throw new Error(`Discord embed has ${discord.embed.fields.length} fields (max 25)`);
      }
    }
  }

  // Build embed
  if (discord.embed) {
    const embed = {
      title: discord.embed.title,
      description: discord.embed.description,
      color: discord.embed.color || 0x00ff41,
      timestamp: new Date().toISOString()
    };
    if (discord.embed.fields) embed.fields = discord.embed.fields;
    if (discord.embed.footer) embed.footer = { text: discord.embed.footer };
    payload.embeds = [embed];
  }

  // Check if we need to upload a thumbnail file (M2: validate path)
  const thumbnailPath = discord.embed && discord.embed.thumbnail_file
    ? validateMediaPath(discord.embed.thumbnail_file, process.cwd())
    : null;

  let resp;
  if (thumbnailPath && fs.existsSync(thumbnailPath)) {
    // Use multipart to attach file + embed
    log('discord', 'Attaching thumbnail...');
    if (payload.embeds && payload.embeds[0]) {
      payload.embeds[0].thumbnail = { url: 'attachment://thumbnail.png' };
    }

    const { boundary, body } = buildMultipart(
      { payload_json: JSON.stringify(payload) },
      { 'files[0]': { path: thumbnailPath, filename: 'thumbnail.png', contentType: 'image/png' } }
    );

    resp = await request(fullUrl, {
      method: 'POST',
      headers: { 'Content-Type': `multipart/form-data; boundary=${boundary}` },
      body
    });
  } else {
    // Simple JSON post
    resp = await request(fullUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  }

  checkHttpStatus(resp, 'Discord webhook');
  const data = parseJSON(resp.body, 'Discord webhook response');
  log('discord', `Message sent: id ${data.id}`);

  return {
    status: 'success',
    messageId: data.id,
    channelId: data.channel_id,
    timestamp: new Date().toISOString()
  };
}

// ============================================================
// MAIN
// ============================================================

async function main() {
  const configPath = path.join(process.env.HOME, '.marketing-pipeline', 'distribution.json');
  const briefPath = path.resolve('distribution-brief.json');
  const resultsPath = path.resolve('distribution-results.json');

  // Load config
  if (!fs.existsSync(configPath)) {
    console.error('[ERROR] Distribution config not found at ' + configPath);
    console.error('Run /marketing distribution setup to configure platform credentials.');
    writeJSON(resultsPath, { error: 'Config not found', timestamp: new Date().toISOString() });
    process.exit(1);
  }

  // Load brief
  if (!fs.existsSync(briefPath)) {
    console.error('[ERROR] distribution-brief.json not found in current directory');
    process.exit(1);
  }

  const config = loadJSON(configPath);
  const brief = loadJSON(briefPath);

  // L5: Validate brief structure
  if (!brief.platforms && !brief.reddit && !brief.twitter && !brief.telegram && !brief.discord) {
    console.error('[ERROR] distribution-brief.json has no "platforms" key and no platform entries at top level');
    writeJSON(resultsPath, { error: 'Invalid brief structure: missing platforms', timestamp: new Date().toISOString() });
    process.exit(1);
  }

  const platformData = brief.platforms || brief;

  console.log('============================================================');
  console.log('  MARKETING PIPELINE — CONTENT DISTRIBUTION');
  console.log(`  Campaign: ${brief.campaign || 'Unknown'}`);
  console.log('============================================================\n');

  const results = {};
  const platforms = ['reddit', 'twitter', 'telegram', 'discord'];
  const platformFns = { reddit: postToReddit, twitter: postToTwitter, telegram: postToTelegram, discord: postToDiscord };
  let succeeded = 0;
  let failed = 0;
  let skipped = 0;

  for (const platform of platforms) {
    const platformConfig = config[platform];
    if (!platformConfig || !platformConfig.enabled) {
      log(platform, 'Skipped (not configured or disabled)');
      results[platform] = { status: 'skipped', reason: 'not configured' };
      skipped++;
      continue;
    }

    try {
      results[platform] = await platformFns[platform](platformConfig, platformData);
      if (results[platform].status === 'skipped') {
        skipped++;
      } else if (results[platform].status === 'partial') {
        // H3: Partial success counts as success but logged distinctly
        succeeded++;
        log(platform, `Partial success: ${results[platform].urls?.length || 0} items posted, failed at step ${results[platform].failedAt}`);
      } else {
        succeeded++;
      }
    } catch (err) {
      log(platform, `FAILED: ${err.message}`);
      results[platform] = { status: 'failed', error: err.message, timestamp: new Date().toISOString() };
      failed++;
    }

    // Delay between platforms
    await sleep(2000);
  }

  const output = {
    timestamp: new Date().toISOString(),
    campaign: brief.campaign || 'Unknown',
    results,
    summary: { total: platforms.length, succeeded, failed, skipped }
  };

  writeJSON(resultsPath, output);

  console.log('\n============================================================');
  console.log(`  DISTRIBUTION COMPLETE`);
  console.log(`  Succeeded: ${succeeded} | Failed: ${failed} | Skipped: ${skipped}`);
  console.log(`  Results: ${resultsPath}`);
  console.log('============================================================\n');
}

main().catch(err => {
  console.error('[FATAL]', err.message);
  process.exit(1);
});
