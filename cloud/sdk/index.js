/**
 * Marketing Pipeline Cloud SDK
 *
 * Lightweight wrapper for syncing pipeline state and deliverables to Supabase.
 * Used by the orchestrator after each pipeline-status.json write.
 *
 * Usage:
 *   const cloud = require('./cloud/sdk');
 *   const ok = await cloud.init();
 *   if (ok) {
 *     const id = await cloud.createCampaign(teamId, slug, name, mode);
 *     await cloud.syncStatus(id, pipelineStatusJson);
 *     await cloud.uploadDeliverable(id, localPath, relativePath);
 *   }
 */

const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');
const path = require('path');

let supabase = null;
let currentUser = null;
let config = null;

const CONFIG_DIR = path.join(process.env.HOME || process.env.USERPROFILE, '.marketing-pipeline');
const CONFIG_PATH = path.join(CONFIG_DIR, 'cloud.json');

function loadConfig() {
  if (!fs.existsSync(CONFIG_PATH)) return null;
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
  } catch (e) {
    console.error('[cloud] Failed to read config:', e.message);
    return null;
  }
}

async function init() {
  const apiKey = process.env.MARKETING_CLOUD_API_KEY;
  config = loadConfig();

  if (!apiKey || !config || !config.supabase_url || !config.supabase_anon_key) {
    return false;
  }

  supabase = createClient(config.supabase_url, config.supabase_anon_key, {
    global: {
      headers: { 'x-api-key': apiKey }
    }
  });

  const { data, error } = await supabase
    .from('users')
    .select('id, email, display_name')
    .single();

  if (error || !data) {
    console.error('[cloud] Invalid API key or connection failed');
    supabase = null;
    return false;
  }

  currentUser = data;
  console.log(`[cloud] Connected as ${data.display_name} (${data.email})`);
  return true;
}

function isEnabled() {
  return supabase !== null && currentUser !== null;
}

function getActiveTeamId() {
  return config ? config.active_team_id : null;
}

function getConfig() {
  return config;
}

async function createCampaign(teamId, slug, name, mode) {
  if (!isEnabled()) return null;

  const { data, error } = await supabase
    .from('campaigns')
    .insert({
      team_id: teamId,
      created_by: currentUser.id,
      slug,
      name,
      mode: mode || 'full-funnel'
    })
    .select('id')
    .single();

  if (error) {
    console.error('[cloud] Failed to create campaign:', error.message);
    return null;
  }

  console.log(`[cloud] Campaign created: ${data.id}`);
  return data.id;
}

async function syncStatus(campaignId, pipelineStatus) {
  if (!isEnabled() || !campaignId) return false;

  let statusObj = pipelineStatus;
  if (typeof pipelineStatus === 'string') {
    try {
      statusObj = JSON.parse(fs.readFileSync(pipelineStatus, 'utf-8'));
    } catch (e) {
      console.error('[cloud] Failed to read pipeline-status.json:', e.message);
      return false;
    }
  }

  const status = statusObj.status === 'complete' || statusObj.status === 'done'
    ? 'done'
    : statusObj.status === 'failed' ? 'failed' : 'running';

  const updateData = {
    pipeline_status: statusObj,
    status,
    updated_at: new Date().toISOString()
  };

  if (statusObj.startTime) updateData.started_at = statusObj.startTime;
  if (statusObj.endTime) updateData.completed_at = statusObj.endTime;

  const { error } = await supabase
    .from('campaigns')
    .update(updateData)
    .eq('id', campaignId);

  if (error) {
    console.error('[cloud] Failed to sync status:', error.message);
    return false;
  }

  return true;
}

async function uploadDeliverable(campaignId, localFilePath, relativePath) {
  if (!isEnabled() || !campaignId) return false;

  if (!fs.existsSync(localFilePath)) {
    console.error(`[cloud] File not found: ${localFilePath}`);
    return false;
  }

  const { data: campaign } = await supabase
    .from('campaigns')
    .select('team_id, slug')
    .eq('id', campaignId)
    .single();

  if (!campaign) return false;

  const fileBuffer = fs.readFileSync(localFilePath);
  const fileName = path.basename(localFilePath);
  const ext = path.extname(localFilePath).toLowerCase();
  const mimeTypes = {
    '.md': 'text/markdown',
    '.json': 'application/json',
    '.html': 'text/html',
    '.mp4': 'video/mp4',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg'
  };
  const mimeType = mimeTypes[ext] || 'application/octet-stream';
  const storagePath = `${campaign.team_id}/${campaign.slug}/${relativePath}`;

  const { error: storageError } = await supabase.storage
    .from('campaign-deliverables')
    .upload(storagePath, fileBuffer, {
      contentType: mimeType,
      upsert: true
    });

  if (storageError) {
    console.error('[cloud] Upload failed:', storageError.message);
    return false;
  }

  const { error: dbError } = await supabase
    .from('deliverables')
    .upsert({
      campaign_id: campaignId,
      name: fileName,
      path: relativePath,
      storage_path: storagePath,
      size_bytes: fileBuffer.length,
      mime_type: mimeType
    }, { onConflict: 'campaign_id,path' });

  if (dbError) {
    console.error('[cloud] Deliverable record failed:', dbError.message);
    return false;
  }

  console.log(`[cloud] Uploaded: ${relativePath} (${(fileBuffer.length / 1024).toFixed(1)} KB)`);
  return true;
}

async function listCampaigns(teamId) {
  if (!isEnabled()) return [];

  const tid = teamId || getActiveTeamId();
  const { data, error } = await supabase
    .from('campaigns')
    .select('id, slug, name, mode, status, started_at, completed_at, created_at')
    .eq('team_id', tid)
    .order('created_at', { ascending: false });

  if (error) {
    console.error('[cloud] Failed to list campaigns:', error.message);
    return [];
  }

  return data;
}

module.exports = {
  init,
  isEnabled,
  getActiveTeamId,
  getConfig,
  createCampaign,
  syncStatus,
  uploadDeliverable,
  listCampaigns
};
