import {Config} from "@remotion/cli/config";
import {existsSync} from "fs";

const envBrowserPath =
  process.env.REMOTION_BROWSER_EXECUTABLE ||
  process.env.CHROME_PATH ||
  process.env.EDGE_PATH;

const windowsBrowserPaths = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
];

let browserExecutable: string | null = null;

if (envBrowserPath) {
  browserExecutable = envBrowserPath;
} else if (process.platform === "win32") {
  browserExecutable = windowsBrowserPaths.find((p) => existsSync(p)) ?? null;
}

if (browserExecutable) {
  Config.setBrowserExecutable(browserExecutable);
}

export default Config;
