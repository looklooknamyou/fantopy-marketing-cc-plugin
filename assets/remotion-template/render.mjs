/**
 * Render script for marketing videos.
 * Reads props from ./props.json (written by the Video Producer agent),
 * bundles the Remotion project, and renders all 3 compositions to MP4.
 *
 * Usage: node render.mjs
 * Output: ../product-hero.mp4, ../social-clip.mp4, ../stats-video.mp4
 */

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { createRequire } from "module";
import path from "path";
import fs from "fs";

const require = createRequire(import.meta.url);

const OUTPUT_DIR = path.resolve("..");

// Read props from props.json if it exists
let props = {};
const propsPath = path.resolve("props.json");
if (fs.existsSync(propsPath)) {
  props = JSON.parse(fs.readFileSync(propsPath, "utf-8"));
  console.log("[render] Loaded props from props.json");
} else {
  console.log("[render] No props.json found, using default props");
}

const compositions = [
  {
    id: "ProductHero",
    output: path.join(OUTPUT_DIR, "product-hero.mp4"),
    props: props.productHero || undefined,
  },
  {
    id: "SocialClip",
    output: path.join(OUTPUT_DIR, "social-clip.mp4"),
    props: props.socialClip || undefined,
  },
  {
    id: "StatsVideo",
    output: path.join(OUTPUT_DIR, "stats-video.mp4"),
    props: props.statsVideo || undefined,
  },
];

async function main() {
  console.log("[render] Bundling Remotion project...");

  const bundleLocation = await bundle({
    entryPoint: path.resolve("src/index.ts"),
    webpackOverride: (config) => config,
  });

  console.log(`[render] Bundle created at: ${bundleLocation}`);

  for (const comp of compositions) {
    console.log(`\n[render] Rendering ${comp.id}...`);

    const composition = await selectComposition({
      serveUrl: bundleLocation,
      id: comp.id,
      inputProps: comp.props || {},
    });

    await renderMedia({
      composition,
      serveUrl: bundleLocation,
      codec: "h264",
      outputLocation: comp.output,
      inputProps: comp.props || {},
      onProgress: ({ progress }) => {
        if (Math.round(progress * 100) % 25 === 0) {
          process.stdout.write(
            `\r[render] ${comp.id}: ${Math.round(progress * 100)}%`
          );
        }
      },
    });

    const stat = fs.statSync(comp.output);
    const sizeMB = (stat.size / (1024 * 1024)).toFixed(1);
    console.log(`\n[render] ${comp.id} → ${comp.output} (${sizeMB} MB)`);
  }

  console.log("\n[render] All videos rendered successfully!");
}

main().catch((err) => {
  console.error("[render] Error:", err);
  process.exit(1);
});
