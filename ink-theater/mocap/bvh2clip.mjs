// bvh2clip.mjs — convert a 3D BVH mocap file into a compact 2D "clip" the
// Ink Theater puppet can play. Offline, run once per motion.
//
//   node bvh2clip.mjs <in.bvh> <out.json> [--axis auto|xy|zy] [--fps 30] [--lockx]
//
// Output: { name, fps, height, groundY, frames:[ {hips,chest,neck,head,
//   shR,elR,haR, shL,elL,haL, hipR,knR,ftR, hipL,knL,ftL, rootY} ] } in px,
// hips-relative pose + separate rootY for vertical root motion (jumps).
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const [, , inPath, outPath, ...rest] = process.argv;
const opt = { axis: "auto", fps: 30, lockx: true };
for (let i = 0; i < rest.length; i++) {
  if (rest[i] === "--axis") opt.axis = rest[++i];
  else if (rest[i] === "--fps") opt.fps = +rest[++i];
  else if (rest[i] === "--nolockx") opt.lockx = false;
  else if (rest[i] === "--max") opt.max = +rest[++i];
  else if (rest[i] === "--name") opt.name = rest[++i];
}

// ---- parse BVH ----
const text = readFileSync(inPath, "utf8");
const tokens = text.replace(/\r/g, "").split("\n");
let li = 0;
const joints = [];
function parseJoint(parent) {
  // current line: "ROOT name" or "JOINT name" or "End Site"
  const line = tokens[li++].trim();
  const isEnd = line.startsWith("End");
  const name = isEnd ? parent.name + "_end" : line.split(/\s+/)[1];
  const j = { name, parent, offset: [0, 0, 0], channels: [], children: [], isEnd };
  joints.push(j);
  tokens[li++]; // {
  while (li < tokens.length) {
    const t = tokens[li].trim();
    if (t.startsWith("OFFSET")) { j.offset = t.split(/\s+/).slice(1, 4).map(Number); li++; }
    else if (t.startsWith("CHANNELS")) { j.channels = t.split(/\s+/).slice(2); li++; }
    else if (t.startsWith("JOINT") || t.startsWith("End")) { j.children.push(parseJoint(j)); }
    else if (t.startsWith("}")) { li++; break; }
    else li++;
  }
  return j;
}
while (tokens[li] !== undefined && !tokens[li].trim().startsWith("ROOT")) li++;
const root = parseJoint(null);
// motion
while (tokens[li] !== undefined && !tokens[li].trim().startsWith("Frames:")) li++;
const nFrames = +tokens[li++].split(":")[1];
const frameTime = +tokens[li++].split(":")[1];
const motion = [];
for (let f = 0; f < nFrames && li < tokens.length; f++) {
  const vals = tokens[li++].trim().split(/\s+/).map(Number);
  if (vals.length > 1) motion.push(vals);
}

// channel layout: DFS order == joints[] order (excluding End Sites)
const chanJoints = joints.filter((j) => !j.isEnd);

// ---- math ----
const d2r = Math.PI / 180;
function rotAxis(ax, deg) {
  const a = deg * d2r, c = Math.cos(a), s = Math.sin(a);
  if (ax === "X") return [[1, 0, 0], [0, c, -s], [0, s, c]];
  if (ax === "Y") return [[c, 0, s], [0, 1, 0], [-s, 0, c]];
  return [[c, -s, 0], [s, c, 0], [0, 0, 1]];
}
function mm(a, b) {
  const r = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++)
    r[i][j] = a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j];
  return r;
}
function mv(m, v) {
  return [m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
          m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
          m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2]];
}
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];

function fk(frame) {
  const pos = {};
  let ci = 0;
  const chanVals = chanJoints.map((j) => { const n = j.channels.length; const v = frame.slice(ci, ci + n); ci += n; return v; });
  function recur(j, pR, pT) {
    const worldPos = add(mv(pR, j.offset), pT);
    pos[j.name] = worldPos;
    const idx = chanJoints.indexOf(j);
    let localR = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    let rootT = null;
    if (idx >= 0) {
      const ch = j.channels, v = chanVals[idx];
      const rotPart = [];
      for (let k = 0; k < ch.length; k++) {
        if (ch[k].endsWith("position")) { if (!rootT) rootT = [0, 0, 0]; rootT[ch[k][0] === "X" ? 0 : ch[k][0] === "Y" ? 1 : 2] = v[k]; }
        else rotPart.push([ch[k][0], v[k]]);
      }
      for (const [ax, deg] of rotPart) localR = mm(localR, rotAxis(ax, deg));
    }
    const myT = rootT ? add(rootT, j.offset) : worldPos; // root uses its position channels
    const myPos = rootT ? add(rootT, j.offset) : worldPos;
    if (rootT) pos[j.name] = myPos;
    const gR = mm(pR, localR);
    for (const c of j.children) recur(c, gR, rootT ? myPos : worldPos);
  }
  recur(root, [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0]);
  return pos;
}

// ---- joint-name resolver (skeleton-agnostic via aliases: fair1 / CMU / Mixamo) ----
const present = new Set(joints.map((j) => j.name));
const ALIAS = {
  hips: ["Hips", "mixamorig:Hips", "Hip"],
  chest: ["Spine3", "Spine2", "Spine1", "Chest", "Spine", "mixamorig:Spine2", "mixamorig:Spine1"],
  neck: ["Neck", "Neck1", "mixamorig:Neck"], head: ["Head", "mixamorig:Head"],
  shR: ["RightArm", "RightShoulder", "mixamorig:RightArm"], elR: ["RightForeArm", "mixamorig:RightForeArm"], haR: ["RightHand", "mixamorig:RightHand"],
  shL: ["LeftArm", "LeftShoulder", "mixamorig:LeftArm"], elL: ["LeftForeArm", "mixamorig:LeftForeArm"], haL: ["LeftHand", "mixamorig:LeftHand"],
  hipR: ["RightUpLeg", "RightHip", "mixamorig:RightUpLeg"], knR: ["RightLeg", "mixamorig:RightLeg"], ftR: ["RightFoot", "mixamorig:RightFoot"],
  hipL: ["LeftUpLeg", "LeftHip", "mixamorig:LeftUpLeg"], knL: ["LeftLeg", "mixamorig:LeftLeg"], ftL: ["LeftFoot", "mixamorig:LeftFoot"]
};
const JN = {};
for (const k in ALIAS) JN[k] = ALIAS[k].find((n) => present.has(n)) || ALIAS[k][0];
const unmapped = Object.keys(ALIAS).filter((k) => !present.has(JN[k]));
if (unmapped.length) console.error("WARN " + inPath + ": unmapped joints " + unmapped.join(",") + " (skeleton not recognized — extend ALIAS)");

// ---- pick 2D axes ----
const p0 = fk(motion[0]);
const spread = [0, 1, 2].map((a) => Math.abs(p0[JN.head][a] - p0[JN.ftR][a]));
let upAxis = spread[1] >= spread[2] ? 1 : 2;      // Y or Z, whichever spans head→foot most
if (opt.axis === "xy") upAxis = 1; if (opt.axis === "zy") upAxis = 2;
const horizAxis = 0;                              // X = left/right (arms)
const upSign = (p0[JN.head][upAxis] - p0[JN.ftR][upAxis]) > 0 ? 1 : -1;
function proj(P) { return [P[horizAxis], -upSign * P[upAxis]]; }

// scale from the SKELETON rest height (rotation-free FK) so every clip of the
// same skeleton renders the figure at an identical size.
function fkRest() {
  const pos = {};
  (function recur(j, pT) { const wp = add(pT, j.offset); pos[j.name] = wp; for (const c of j.children) recur(c, wp); })(root, [0, 0, 0]);
  return pos;
}
const restPos = fkRest();
const restUp = Object.values(restPos).map((P) => -upSign * P[upAxis]);
const heightUnits = Math.max(...restUp) - Math.min(...restUp);
const scale = 520 / heightUnits;

const step = Math.max(1, Math.round((1 / frameTime) / opt.fps));
const hips0 = proj(p0[JN.hips]);
let frames = [];
for (let f = 0; f < motion.length; f += step) {
  const P = fk(motion[f]);
  const h = proj(P[JN.hips]);
  const rootY = (h[1] - hips0[1]) * scale;         // vertical root motion (jumps)
  const rootX = opt.lockx ? h[0] : hips0[0];       // in-place unless drift wanted
  const out = { rootY: Math.round(rootY * 10) / 10 };
  for (const key in JN) {
    const j = P[JN[key]]; if (!j) continue;
    const q = proj(j);
    out[key] = [Math.round((q[0] - rootX) * scale * 10) / 10, Math.round((q[1] - h[1]) * scale * 10) / 10];
  }
  frames.push(out);
}
if (opt.max && frames.length > opt.max) frames = frames.slice(0, opt.max);   // cap length (loops the take)
// ground = lowest foot at rest (frame 0), figure height
const f0 = frames[0];
const groundY = Math.max(f0.ftR ? f0.ftR[1] : 0, f0.ftL ? f0.ftL[1] : 0);
const name = opt.name || inPath.split(/[\\/]/).pop().replace(/\.bvh$/i, "");
const clip = { name, fps: opt.fps, height: Math.round(520), groundY: Math.round(groundY), frameCount: frames.length, frames };
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, JSON.stringify(clip));
console.log(`${name}: ${frames.length} frames @${opt.fps}fps · upAxis=${upAxis}(${upSign}) · scale=${scale.toFixed(2)} · groundY=${clip.groundY}`);
