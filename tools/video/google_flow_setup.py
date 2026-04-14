"""One-time Google Flow OAuth setup.

Run this ONCE to log in with your Google account and save the session:

    python3 -m tools.video.google_flow_setup

This opens a visible Chromium browser. Complete the Google sign-in,
navigate to https://labs.google/flow, then press ENTER in this terminal.
The session cookies are saved to ~/.openmontage/google_flow_session.json
and reused automatically by google_flow_video on all future runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SESSION_DIR = Path.home() / ".openmontage"
_SESSION_FILE = _SESSION_DIR / "google_flow_session.json"
_PROFILE_DIR = _SESSION_DIR / "google_flow_profile"  # persistent Chrome profile
_FLOW_URL = "https://labs.google/fx/tools/flow"


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    print("=" * 60)
    print("Google Flow — One-time login setup")
    print("=" * 60)
    print()
    print("A browser window will open. Sign in with your Google account")
    print("that has Google Flow access, then press ENTER here.")
    print()
    input("Press ENTER to open the browser...")

    # Use a PERSISTENT profile dir — reused on every run so full browser state
    # (localStorage, service workers, auth tokens) is preserved across sessions.
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    _PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(_PROFILE_DIR),
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_default_args=["--enable-automation"],
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.goto(_FLOW_URL)

        print()
        print(f"Browser opened at {_FLOW_URL}")
        print("Sign in with Google if prompted, then wait until you see the Flow generation UI.")
        print()
        input("Once you are inside Google Flow (can see the prompt box), press ENTER here...")

        # Save cookies alongside the profile as a quick validity marker
        cookies = context.cookies()
        _SESSION_FILE.write_text(json.dumps({"cookies": cookies}, indent=2))

        context.close()

    if cookies:
        print()
        print(f"Session saved ({len(cookies)} cookies) to {_SESSION_FILE}")
        print("google_flow_video will use this session automatically.")
    else:
        print("WARNING: No cookies captured. Make sure you completed login.")
        sys.exit(1)


if __name__ == "__main__":
    main()
