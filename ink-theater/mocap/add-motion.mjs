// add-motion.mjs — fetch a BVH, convert it, and add it to the shared Ink Puppet
// library (self-extending: no code changes, just data). Then copy clips.js into
// your project.
//
//   node add-motion.mjs <name> <source> [category] [description]
//
// <source> is one of:
//   • a CMU id     "05_02"  or  "005/05_02"  → fetched from una-dinosauria/cmu-mocap
//   • a URL        "https://…/foo.bvh"
//   • a local path "./something.bvh"
//
// Skeleton is auto-mapped (fair1 / CMU / Mixamo) by bvh2clip.mjs. A new skeleton
// only needs an alias added to bvh2clip.mjs's ALIAS table.
import { writeFileSync, readFileSync, readdirSync, existsSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const [, , name, source, category = "action", desc = ""] = process.argv;
if (!name || !source) { console.error("usage: node add-motion.mjs <name> <source> [category] [description]"); process.exit(1); }

async function resolveBvh(src) {
  const tmp = join(here, "src"); mkdirSync(tmp, { recursive: true });
  const out = join(tmp, name + ".bvh");
  if (existsSync(src)) { writeFileSync(out, readFileSync(src)); return out; }
  let url = src;
  const CMU = "https://raw.githubusercontent.com/una-dinosauria/cmu-mocap/master/data";
  if (/^\d{2,3}_\d+$/.test(src)) { const subj = src.split("_")[0].padStart(3, "0"); url = `${CMU}/${subj}/${src}.bvh`; }
  else if (/^\d+\/\d{2,3}_\d+$/.test(src)) { url = `${CMU}/${src}.bvh`; }
  const r = await fetch(url); if (!r.ok) throw new Error(`fetch failed ${r.status}: ${url}`);
  writeFileSync(out, Buffer.from(await r.arrayBuffer())); return out;
}

const bvh = await resolveBvh(source);
execFileSync("node", [join(here, "bvh2clip.mjs"), bvh, join(here, "clips", name + ".json"), "--fps", "30", "--max", "180", "--name", name], { stdio: "inherit" });

const clipsDir = join(here, "clips");
const clips = {};
for (const f of readdirSync(clipsDir).filter((f) => f.endsWith(".json"))) clips[f.replace(/\.json$/, "")] = JSON.parse(readFileSync(join(clipsDir, f), "utf8"));
writeFileSync(join(here, "clips.js"), "window.INK_CLIPS=" + JSON.stringify(clips) + ";");

const catPath = join(here, "catalog.json");
const cat = existsSync(catPath) ? JSON.parse(readFileSync(catPath, "utf8")) : [];
const entry = { name, category, desc: desc || name, frames: clips[name].frameCount, source };
const i = cat.findIndex((c) => c.name === name);
if (i >= 0) cat[i] = entry; else cat.push(entry);
cat.sort((a, b) => a.name.localeCompare(b.name));
writeFileSync(catPath, JSON.stringify(cat, null, 2));
console.log(`✓ added "${name}" (${category}) · ${clips[name].frameCount}f · library now ${cat.length} actions. Copy clips.js into your project.`);
