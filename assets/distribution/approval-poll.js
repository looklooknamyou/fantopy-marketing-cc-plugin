#!/usr/bin/env node
/**
 * approval-poll.js — Polls approval-status.json until all items are decided.
 *
 * Usage: node approval-poll.js <path-to-approval-status.json>
 *
 * Exits 0 when at least one item is approved (prints approved summary as JSON).
 * Exits 1 when all items are rejected or timeout reached.
 * Exits 2 on usage error.
 *
 * The orchestrator wraps this in a 10-minute external timeout.
 */

const fs = require('fs');
const path = require('path');

const POLL_INTERVAL_MS = 15000; // 15 seconds
const statusPath = process.argv[2];

if (!statusPath) {
  console.error('Usage: node approval-poll.js <approval-status.json>');
  process.exit(2);
}

const absPath = path.resolve(statusPath);

function readStatus() {
  try {
    return JSON.parse(fs.readFileSync(absPath, 'utf8'));
  } catch (e) {
    return null;
  }
}

function checkDecisions(status) {
  if (!status || !status.deliverables) return null;

  const deliverables = status.deliverables;
  let totalPlatforms = 0;
  let decidedPlatforms = 0;
  let approvedPlatforms = 0;
  const approved = {};
  const rejected = {};

  for (const [delivPath, deliv] of Object.entries(deliverables)) {
    if (!deliv.platforms) continue;
    for (const [platform, decision] of Object.entries(deliv.platforms)) {
      totalPlatforms++;
      if (decision === 'approved') {
        decidedPlatforms++;
        approvedPlatforms++;
        if (!approved[delivPath]) approved[delivPath] = { name: deliv.name, platforms: [] };
        approved[delivPath].platforms.push(platform);
      } else if (decision === 'rejected') {
        decidedPlatforms++;
        if (!rejected[delivPath]) rejected[delivPath] = { name: deliv.name, platforms: [] };
        rejected[delivPath].platforms.push(platform);
      }
      // 'pending' items are not decided yet
    }
  }

  if (totalPlatforms === 0) return null;

  // Check for bulk status override — populate maps if individual items weren't tallied
  if (status.status === 'approved' || status.status === 'rejected') {
    const bulkDecision = status.status;
    for (const [delivPath, deliv] of Object.entries(deliverables)) {
      if (!deliv.platforms) continue;
      for (const [platform] of Object.entries(deliv.platforms)) {
        const target = bulkDecision === 'approved' ? approved : rejected;
        if (!target[delivPath]) target[delivPath] = { name: deliv.name, platforms: [] };
        if (!target[delivPath].platforms.includes(platform)) target[delivPath].platforms.push(platform);
      }
    }
    return {
      decided: true,
      hasApproved: bulkDecision === 'approved',
      approved: bulkDecision === 'approved' ? approved : {},
      rejected: bulkDecision === 'rejected' ? rejected : {},
      summary: { total: totalPlatforms, approved: bulkDecision === 'approved' ? totalPlatforms : 0, rejected: bulkDecision === 'rejected' ? totalPlatforms : 0 }
    };
  }

  // All items decided?
  if (decidedPlatforms >= totalPlatforms) {
    return {
      decided: true,
      hasApproved: approvedPlatforms > 0,
      approved,
      rejected,
      summary: { total: totalPlatforms, approved: approvedPlatforms, rejected: decidedPlatforms - approvedPlatforms }
    };
  }

  return { decided: false };
}

function poll() {
  const status = readStatus();
  if (!status) {
    missingCount++;
    if (missingCount >= 10) {
      process.stderr.write(`[approval-poll] WARNING: ${absPath} not found after ${missingCount} attempts\n`);
    }
    setTimeout(poll, POLL_INTERVAL_MS);
    return;
  }
  missingCount = 0;

  const result = checkDecisions(status);
  if (!result) {
    setTimeout(poll, POLL_INTERVAL_MS);
    return;
  }

  if (!result.decided) {
    const pending = Object.values(status.deliverables || {}).reduce((n, d) =>
      n + Object.values(d.platforms || {}).filter(v => v === 'pending').length, 0);
    process.stderr.write(`[approval-poll] Waiting... ${pending} items pending\n`);
    setTimeout(poll, POLL_INTERVAL_MS);
    return;
  }

  // All decided
  if (result.hasApproved) {
    console.log(JSON.stringify(result, null, 2));
    process.exit(0);
  } else {
    // All rejected
    console.error('[approval-poll] All items rejected');
    console.log(JSON.stringify(result, null, 2));
    process.exit(1);
  }
}

var missingCount = 0;
console.error(`[approval-poll] Polling ${absPath} every ${POLL_INTERVAL_MS / 1000}s...`);
poll();
