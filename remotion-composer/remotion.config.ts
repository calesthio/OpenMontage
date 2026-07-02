import { Config } from "@remotion/cli/config";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";

/**
 * Browser resolution for environments that cannot download Chrome.
 *
 * Remotion normally fetches its own "Chrome Headless Shell" on first render.
 * In sandboxed/CI environments with a restricted network egress allowlist
 * (and in offline setups), that download fails with a 403/timeout. To keep
 * `npx remotion render` working everywhere, we point Remotion at an existing
 * browser when one can be found, in priority order:
 *
 *   1. REMOTION_BROWSER_EXECUTABLE — explicit override (any Chrome/Chromium).
 *   2. A Playwright-managed Chromium under PLAYWRIGHT_BROWSERS_PATH
 *      (or the conventional /opt/pw-browsers location).
 *
 * If none is found we set nothing, so a normal machine keeps Remotion's
 * default behaviour of downloading and managing its own browser.
 */
function resolveBrowserExecutable(): string | undefined {
  const explicit = process.env.REMOTION_BROWSER_EXECUTABLE;
  if (explicit && existsSync(explicit)) {
    return explicit;
  }

  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"]
    .filter((r): r is string => Boolean(r))
    .filter((r) => existsSync(r));

  // Prefer the headless shell (what Remotion downloads itself), then full Chromium.
  const prefixes: Array<[prefix: string, binary: string]> = [
    ["chromium_headless_shell", "headless_shell"],
    ["chromium", "chrome"],
  ];

  for (const [prefix, binary] of prefixes) {
    for (const root of roots) {
      let entries: string[];
      try {
        entries = readdirSync(root);
      } catch {
        continue;
      }
      for (const entry of entries) {
        if (!entry.startsWith(prefix)) {
          continue;
        }
        const candidate = join(root, entry, "chrome-linux", binary);
        if (existsSync(candidate)) {
          return candidate;
        }
      }
    }
  }

  return undefined;
}

const browserExecutable = resolveBrowserExecutable();
if (browserExecutable) {
  Config.setBrowserExecutable(browserExecutable);
  // Sandboxed/CI environments route egress through a proxy that presents its
  // own TLS CA, which the resolved Chromium does not trust. Without this,
  // otherwise-reachable https assets (Google Fonts, images) fail to load with
  // ERR_CERT_AUTHORITY_INVALID and abort the render. Scoped to the case where
  // we had to resolve a browser ourselves, so a normal machine keeps strict TLS.
  Config.setChromiumIgnoreCertificateErrors(true);
}

Config.setOverwriteOutput(true);
