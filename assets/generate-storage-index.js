#!/usr/bin/env node
// Scans marketing output directories and generates storage-index.json
const fs = require('fs');
const path = require('path');

const HOME = process.env.HOME || process.env.USERPROFILE;
const OUTPUT_DIR = path.join(HOME, 'marketing-output');
const CAMPAIGNS_DIR = path.join(HOME, '.marketing-pipeline', 'campaigns');
const OUT_FILE = path.join(__dirname, 'storage-index.json');

function mediaTypeFromName(name) {
  const ext = name.split('.').pop().toLowerCase();
  if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) return 'image';
  if (['mp4', 'webm', 'mov'].includes(ext)) return 'video';
  return null;
}

function servedPathFromFull(fullPath) {
  // Convert absolute path to path relative to marketing-output symlink
  const moIdx = fullPath.indexOf('/marketing-output/');
  if (moIdx !== -1) return fullPath.substring(moIdx + 1); // "marketing-output/slug/..."
  return null;
}

function categoryFromPath(filePath) {
  if (filePath.startsWith('00-brief/')) return 'brief';
  if (filePath.startsWith('01-research/')) return 'research';
  if (filePath.startsWith('02-strategy/')) return 'strategy';
  if (filePath.startsWith('03-content/')) return 'content';
  if (filePath.startsWith('04-seo/')) return 'seo';
  if (filePath.startsWith('05-review/')) return 'review';
  if (filePath.startsWith('06-final/')) return 'final';
  if (filePath.startsWith('07-distribution/')) return 'distribution';
  return 'other';
}

function scanDir(baseDir) {
  const campaigns = [];
  if (!fs.existsSync(baseDir)) return campaigns;

  for (const entry of fs.readdirSync(baseDir)) {
    const campaignDir = path.join(baseDir, entry);
    if (!fs.statSync(campaignDir).isDirectory()) continue;

    const statusFile = path.join(campaignDir, 'pipeline-status.json');
    if (!fs.existsSync(statusFile)) continue;

    try {
      const data = JSON.parse(fs.readFileSync(statusFile, 'utf-8'));
      const deliverables = (data.deliverables || [])
        .filter(d => d.status === 'done')
        .map(d => {
          const fp = path.join(campaignDir, d.path);
          return {
            name: d.name,
            path: d.path,
            fullPath: fp,
            size: d.size || '?',
            category: categoryFromPath(d.path),
            status: d.status,
            mediaType: mediaTypeFromName(d.name),
            servedPath: servedPathFromFull(fp)
          };
        });

      campaigns.push({
        name: data.campaign || entry,
        slug: data.slug || entry,
        mode: data.mode || 'unknown',
        status: data.status || 'unknown',
        date: data.startTime ? data.startTime.split('T')[0] : 'unknown',
        outputDir: campaignDir,
        deliverableCount: deliverables.length,
        deliverables
      });
    } catch (e) {
      // skip malformed files
    }
  }
  return campaigns;
}

function scanBatchDirs() {
  const campaigns = [];
  if (!fs.existsSync(CAMPAIGNS_DIR)) return campaigns;

  for (const campaign of fs.readdirSync(CAMPAIGNS_DIR)) {
    const batchesDir = path.join(CAMPAIGNS_DIR, campaign, 'batches');
    if (!fs.existsSync(batchesDir) || !fs.statSync(batchesDir).isDirectory()) continue;

    for (const batch of fs.readdirSync(batchesDir)) {
      const batchDir = path.join(batchesDir, batch);
      const statusFile = path.join(batchDir, 'pipeline-status.json');
      if (!fs.existsSync(statusFile)) continue;

      try {
        const data = JSON.parse(fs.readFileSync(statusFile, 'utf-8'));
        const deliverables = (data.deliverables || [])
          .filter(d => d.status === 'done')
          .map(d => {
            const fp = path.join(batchDir, d.path);
            return {
              name: d.name,
              path: d.path,
              fullPath: fp,
              size: d.size || '?',
              category: categoryFromPath(d.path),
              status: d.status,
              mediaType: mediaTypeFromName(d.name),
              servedPath: servedPathFromFull(fp)
            };
          });

        campaigns.push({
          name: `${data.campaign || campaign} (${batch})`,
          slug: `${campaign}/${batch}`,
          mode: data.mode || 'sustained-batch',
          status: data.status || 'unknown',
          date: data.startTime ? data.startTime.split('T')[0] : 'unknown',
          outputDir: batchDir,
          deliverableCount: deliverables.length,
          deliverables
        });
      } catch (e) { /* skip */ }
    }
  }
  return campaigns;
}

const allCampaigns = [...scanDir(OUTPUT_DIR), ...scanBatchDirs()];
allCampaigns.sort((a, b) => (b.date || '').localeCompare(a.date || ''));

const index = { generated: new Date().toISOString(), campaigns: allCampaigns };
fs.writeFileSync(OUT_FILE, JSON.stringify(index, null, 2));

console.log(`Storage index generated: ${allCampaigns.length} campaigns, ${allCampaigns.reduce((s, c) => s + c.deliverableCount, 0)} deliverables → ${OUT_FILE}`);
