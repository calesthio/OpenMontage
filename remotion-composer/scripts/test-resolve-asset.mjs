// Contract test for the resolveAsset() helper duplicated across compositions.
//
// The helper is intentionally copy-pasted in 7 files to keep each composition
// self-contained; this test extracts every copy from source and asserts the
// same table of cases against each one, so a future edit cannot silently
// reintroduce the file:/// root-slash bug (issue #237, Bug 1) in one copy.
//
// Run: node scripts/test-resolve-asset.mjs   (no dependencies)
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const FILES = [
  "src/Explainer.tsx",
  "src/CinematicRenderer.tsx",
  "src/LyricOverlay.tsx",
  "src/CollageBurst.tsx",
  "src/TitledVideo.tsx",
  "src/components/ScreenshotScene.tsx",
  "src/components/AnimeScene.tsx",
];

// [input, expected] — staticFile() is stubbed to "STATIC:<path>" so the
// assertion distinguishes public/-relative routing from file:// bypass.
const CASES = [
  // POSIX file URI must keep its root slash (the original bug: it became
  // relative "Users/..." and 404'd through staticFile).
  ["file:///Users/x/img.png", "file:///Users/x/img.png"],
  // Raw absolute paths bypass staticFile as file:// URIs.
  ["/Users/x/img.png", "file:///Users/x/img.png"],
  ["C:\\media\\img.png", "file:///C:/media/img.png"],
  // Windows file URIs: the slash before the drive letter is URI syntax,
  // not part of the path.
  ["file:///C:/media/img.png", "file:///C:/media/img.png"],
  ["file://C:/media/img.png", "file:///C:/media/img.png"],
  // public/-relative paths go through staticFile.
  ["proj/img.png", "STATIC:proj/img.png"],
  // Remote URLs and data URIs pass through untouched.
  ["http://x/y.png", "http://x/y.png"],
  ["https://x/y.png", "https://x/y.png"],
  ["data:image/png;base64,abc", "data:image/png;base64,abc"],
];

let failures = 0;

for (const file of FILES) {
  const source = readFileSync(join(root, file), "utf8");
  const match = source.match(
    /function resolveAsset\(src: string\): string \{[\s\S]*?\n\}/,
  );
  if (!match) {
    console.error(`FAIL ${file}: resolveAsset() not found — did it move?`);
    failures++;
    continue;
  }
  // Strip TS annotations so the extracted copy runs as plain JS.
  // Evaluating first-party source read from this repo is the same trust
  // domain as running this script itself — nothing user-supplied is
  // interpolated. This is the no-build-infra way to test an unexported
  // helper; if the composer ever gains a test runner, extract resolveAsset
  // to a shared module and import it instead.
  const fnSource = match[0].replace(/: string/g, "");
  const staticFile = (p) => `STATIC:${p}`;
  const resolveAsset = new Function(
    "staticFile",
    `return (${fnSource.replace("function resolveAsset", "function")});`,
  )(staticFile);

  for (const [input, expected] of CASES) {
    const got = resolveAsset(input);
    if (got !== expected) {
      console.error(`FAIL ${file}: ${input} -> ${got} (expected ${expected})`);
      failures++;
    }
  }
  console.log(`ok ${file}`);
}

if (failures > 0) {
  console.error(`\n${failures} failure(s)`);
  process.exit(1);
}
console.log(`\nAll ${FILES.length} copies pass ${CASES.length} cases.`);
