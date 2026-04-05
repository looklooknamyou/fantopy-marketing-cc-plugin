import path from "node:path";
import { access } from "node:fs/promises";

const ROOT_MARKERS = [
  [".claude-plugin", "plugin.json"],
  ["commands", "marketing.md"],
  ["agents", "marketing-orchestrator.md"]
];

async function exists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function isMarketingPipelineRoot(dir) {
  for (const marker of ROOT_MARKERS) {
    if (!(await exists(path.join(dir, ...marker)))) return false;
  }
  return true;
}

async function findRepoRoot(startDir) {
  let current = path.resolve(startDir);
  while (true) {
    if (await isMarketingPipelineRoot(current)) return current;
    const parent = path.dirname(current);
    if (parent === current) return null;
    current = parent;
  }
}

function buildSystemContext(root) {
  const rel = (segments) => path.relative(root, path.join(root, ...segments));
  return [
    `This project is the Marketing Pipeline plugin. Main router: ${rel(["commands", "marketing.md"])}.`,
    `Core orchestrator: ${rel(["agents", "marketing-orchestrator.md"])}. Dashboard: ${rel(["assets", "pipeline-dashboard.html"])}.`,
    "One-shot campaign runs write under marketing-output/<slug>/. Sustained campaigns write under ~/.marketing-pipeline/campaigns/<slug>/.",
    `Cloud backend code lives in ${rel(["cloud", "api"])} and the browser client lives in ${rel(["assets", "pipeline-dashboard.html"])}.`,
    "When the user references /marketing flows, keep command routing, dashboard data contracts, and team-scoped cloud config aligned with the existing repo behavior."
  ];
}

export default async function marketingPipelinePlugin(ctx) {
  const repoRoot = await findRepoRoot(ctx.directory);
  if (!repoRoot) return {};

  return {
    "experimental.chat.system.transform": async (_input, output) => {
      output.system.push(...buildSystemContext(repoRoot));
    }
  };
}

export const MarketingPipelinePlugin = marketingPipelinePlugin;
