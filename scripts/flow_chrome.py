"""Start (or check) the Chrome that `flow_video` drives.

The Flow session lives in a dedicated Chrome profile, not in this repo. That
profile keeps its cookies indefinitely — but only when Chrome is launched
pointing at it. Opening Chrome from the normal shortcut uses the *default*
profile instead, which is a different browser as far as Google is concerned, and
looks exactly like "the session was lost".

Two flags matter and both are load-bearing:

  --user-data-dir   the profile that holds the Flow session. Since Chrome 136
                    the debugging port is silently ignored on the default
                    profile, so this is required, not a preference.
  --remote-debugging-port  what Playwright attaches to.

    python scripts/flow_chrome.py           # start it (no-op if already up)
    python scripts/flow_chrome.py --check    # report status, start nothing
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PORT = 9222
PROFILE = Path.home() / ".openmontage" / "chrome-flow"
FLOW_URL = "https://labs.google/fx/tools/flow"

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
]


def chrome_path() -> Path:
    override = os.environ.get("CHROME_PATH")
    if override:
        return Path(override)
    for candidate in CHROME_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "could not find chrome.exe — set CHROME_PATH to its full path and retry")


def cdp_version(port: int, timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=timeout
        ) as resp:
            return json.load(resp)
    except (urllib.error.URLError, OSError, ValueError):
        return None


def signed_in(port: int) -> bool | None:
    """True / False, or None when Playwright is not installed to check with."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            try:
                pages = [p for ctx in browser.contexts for p in ctx.pages]
                page = next((p for p in pages if "labs.google" in p.url), None)
                if page is None:
                    return None
                session = page.evaluate(
                    """async () => {
                        const r = await fetch('/fx/api/auth/session',
                                              { credentials: 'same-origin' });
                        const j = await r.json().catch(() => null);
                        return !!(j && j.access_token);
                    }"""
                )
                return bool(session)
            finally:
                browser.close()
    except Exception:
        return None


def start(port: int) -> None:
    PROFILE.mkdir(parents=True, exist_ok=True)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [str(chrome_path()),
         f"--remote-debugging-port={port}",
         f"--user-data-dir={PROFILE}",
         FLOW_URL],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, creationflags=creationflags,
    )


def report(port: int) -> int:
    version = cdp_version(port)
    print(f"profile : {PROFILE}")
    print(f"exists  : {'yes' if PROFILE.is_dir() else 'no — will be created on first start'}")
    if version is None:
        print(f"chrome  : not listening on port {port}")
        print("\nStart it with:  python scripts/flow_chrome.py")
        return 1
    print(f"chrome  : {version.get('Browser')} on port {port}")
    state = signed_in(port)
    print("flow    : " + {
        True: "signed in",
        False: "NOT signed in — sign in at " + FLOW_URL + " in that window",
        None: "unknown (open the Flow tab, or install playwright to check)",
    }[state])
    return 0 if state is not False else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--check", action="store_true",
                        help="report status without starting anything")
    args = parser.parse_args()

    if args.check:
        return report(args.port)

    if cdp_version(args.port) is not None:
        print(f"already running on port {args.port}")
        return report(args.port)

    print(f"starting Chrome with profile {PROFILE} …")
    start(args.port)
    for _ in range(20):
        time.sleep(1)
        if cdp_version(args.port) is not None:
            break
    else:
        raise SystemExit(
            f"Chrome did not open port {args.port}. If it launched but the port is "
            f"closed, another Chrome was already running on the same profile — close "
            f"every Chrome window and retry."
        )
    return report(args.port)


if __name__ == "__main__":
    sys.exit(main())
