# Browser Tools Setup — Meta Skill

## When to Use

Read this skill when a user wants to use browser-based tools (`heygen_browser_video`, `google_flow_video`, `google_flow_image`) or when setting up OpenMontage for the first time.

## What Browser Tools Are

These tools use Playwright to automate the provider web UI directly — no API key required. They consume your existing subscription plan credits (no per-call cost).

Session cookies are saved to `~/.openmontage/` after first login and reused automatically on subsequent runs:

| Tool | Session File |
|------|-------------|
| `heygen_browser_video` | `~/.openmontage/heygen_session.json` |
| `google_flow_video`, `google_flow_image` | `~/.openmontage/google_flow_session.json` + `google_flow_profile/` |

---

## Setup Steps

### Step 1 — Fill in credentials in `.env`

```
HEYGEN_EMAIL=your@heygenemail.com
HEYGEN_PASSWORD=yourpassword
GOOGLE_FLOW_EMAIL=your@gmail.com
```

Note: `MAGICHOUR_API_KEY` and `GIPHY_API_KEY` are separate — set them when prompted by the registry.

### Step 2 — Verify Playwright is installed

```bash
python3 -c "from playwright.sync_api import sync_playwright; print('OK')"
```

If it fails:

```bash
pip install playwright && playwright install chromium
```

### Step 3 — First-time HeyGen login

The first use of `heygen_browser_video` opens a browser, logs in with your email/password, and saves the session to `~/.openmontage/heygen_session.json`. Subsequent runs reuse that session automatically — no action needed.

### Step 4 — First-time Google Flow login (requires user action)

Google uses OAuth, which cannot be fully automated. On first run:

1. The tool launches a **visible** browser (not headless)
2. You must click "Sign in with Google" and complete the OAuth flow
3. Session is saved — future runs are headless and automatic

### Step 5 — Verify all new tools

```bash
python3 -c "
from tools.tool_registry import registry
registry.discover()
for name in ['magic_hour_video', 'giphy_search', 'heygen_browser_video', 'google_flow_video', 'google_flow_image']:
    t = registry.get(name)
    print(f'{name}: {t.get_status().value if t else \"not found\"}')"
```

Expected output when fully configured:

```
magic_hour_video: available
giphy_search: available
heygen_browser_video: available
google_flow_video: available
google_flow_image: available
```

### Step 6 — Optional: faster transcription

```bash
pip install faster-whisper
```

Unlocks the `talking-head`, `clip-factory`, and `podcast-repurpose` pipelines.

### Step 7 — Optional: video download from URLs

```bash
pip install yt-dlp
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Session expired" error | Delete the session file (`~/.openmontage/heygen_session.json` or `google_flow_session.json`), then re-run — the tool will log in again |
| Google OAuth loop | The tool runs with `headless=False` automatically on first run; complete the sign-in manually in the browser window that opens |
| `heygen_browser_video` falls back to `heygen_video` | Expected when the browser session is stale — delete the session file to force a fresh login |
