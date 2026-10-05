import fs from "node:fs";
import path from "node:path";
import { Config } from "@remotion/cli/config";

function existingPath(candidate: string | undefined): string | null {
  if (!candidate) {
    return null;
  }
  return fs.existsSync(candidate) ? candidate : null;
}

function detectWindowsBrowser(): string | null {
  const roots = [
    process.env.PROGRAMFILES,
    process.env["PROGRAMFILES(X86)"],
    process.env.LOCALAPPDATA,
  ].filter(Boolean) as string[];

  const candidates = [
    process.env.OPENMONTAGE_BROWSER_EXECUTABLE,
    ...roots.flatMap((root) => [
      path.join(root, "Google", "Chrome", "Application", "chrome.exe"),
      path.join(root, "Microsoft", "Edge", "Application", "msedge.exe"),
      path.join(root, "Chromium", "Application", "chrome.exe"),
    ]),
  ];

  for (const candidate of candidates) {
    const resolved = existingPath(candidate);
    if (resolved) {
      return resolved;
    }
  }
  return null;
}

if (process.platform === "win32") {
  const browserExecutable = detectWindowsBrowser();
  if (browserExecutable) {
    Config.setBrowserExecutable(browserExecutable);
  }
}
