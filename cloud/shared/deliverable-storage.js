const fs = require('fs');
const os = require('os');
const path = require('path');

const LOCAL_PREFIX = 'localfs://';
const DEFAULT_ROOT = path.join(
  process.env.MARKETING_DELIVERABLE_FALLBACK_DIR ||
  path.join(os.homedir(), '.marketing-pipeline', 'deliverables-cloud')
);

function normalizeRelativeStoragePath(storagePath) {
  const normalized = path.posix.normalize(String(storagePath || ''));
  if (!normalized || normalized === '.' || normalized.startsWith('../') || normalized.includes('/../')) {
    throw new Error('Invalid storage path');
  }
  return normalized;
}

function toLocalRef(storagePath) {
  return LOCAL_PREFIX + normalizeRelativeStoragePath(storagePath);
}

function isLocalRef(storagePath) {
  return typeof storagePath === 'string' && storagePath.startsWith(LOCAL_PREFIX);
}

function localRefToRelativePath(storagePath) {
  if (!isLocalRef(storagePath)) return null;
  return normalizeRelativeStoragePath(storagePath.slice(LOCAL_PREFIX.length));
}

function ensureParentDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function getLocalFallbackPath(storagePath) {
  const relativePath = normalizeRelativeStoragePath(storagePath);
  return path.join(DEFAULT_ROOT, ...relativePath.split('/'));
}

function writeLocalFallback(storagePath, buffer) {
  const filePath = getLocalFallbackPath(storagePath);
  ensureParentDir(filePath);
  fs.writeFileSync(filePath, buffer);
  return { storage_path: toLocalRef(storagePath), file_path: filePath };
}

function readLocalFallback(storagePath) {
  const relativePath = localRefToRelativePath(storagePath);
  if (!relativePath) return null;
  const filePath = getLocalFallbackPath(relativePath);
  if (!fs.existsSync(filePath)) return null;
  return fs.readFileSync(filePath);
}

function shouldFallbackToLocal(error) {
  const message = String(
    error && (error.message || error.error_description || error.error || error)
  ).toLowerCase();

  return (
    message.includes('extended attributes') ||
    message.includes('feature disabled') ||
    message.includes('xattr')
  );
}

module.exports = {
  DEFAULT_ROOT,
  isLocalRef,
  localRefToRelativePath,
  readLocalFallback,
  shouldFallbackToLocal,
  toLocalRef,
  writeLocalFallback
};
