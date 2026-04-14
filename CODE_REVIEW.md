# OpenMontage — Code Review: All Uncommitted Changes

> Generated: 2026-04-14  
> Branch: `main` (12 commits behind origin — **DO NOT PULL before reviewing**)  
> Status: All changes on disk only, nothing committed

---

## Summary of Changes

| File | Type | What Changed |
|------|------|-------------|
| `tools/base_tool.py` | Modified | Added `execute_safe()` with auto-timeout + fallback |
| `AGENT_GUIDE.md` | Modified | Added browser tools section, new tools reference, setup guide |
| `PROJECT_CONTEXT.md` | Modified | Added browser tool pattern, `execute_safe()` note |
| `tools/video/_google_flow_base.py` | **New** | Shared Playwright automation for Google Flow |
| `tools/video/google_flow_image.py` | **New** | Image gen via Google Flow (Nano Banana / Imagen 4) |
| `tools/video/google_flow_video.py` | **New** | Video gen via Google Flow (Veo models) |
| `tools/video/magic_hour_video.py` | **New** | Video gen via Magic Hour API |
| `tools/video/heygen_browser_video.py` | **New** | Avatar video via HeyGen browser automation |
| `tools/graphics/giphy_search.py` | **New** | GIF search via Giphy API |

---

## 1. `tools/base_tool.py` — Modified

### Diff

```diff
+import concurrent.futures
+import logging
+
+logger = logging.getLogger(__name__)

+    def execute_safe(self, inputs: dict[str, Any]) -> ToolResult:
+        """Execute with automatic timeout and fallback escalation.
+
+        Timeout = max(30s, min(estimate_runtime * 2, 600s)).
+        On timeout the first available fallback tool is tried automatically.
+        """
+        expected = self.estimate_runtime(inputs)
+        timeout = max(30.0, min(expected * 2, 600.0)) if expected > 0 else 120.0
+
+        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
+            future = executor.submit(self.execute, inputs)
+            try:
+                return future.result(timeout=timeout)
+            except concurrent.futures.TimeoutError:
+                future.cancel()
+                logger.warning(
+                    "Tool %r timed out after %.0fs — trying fallbacks: %s",
+                    self.name, timeout, self.fallback_tools,
+                )
+
+        for fallback_name in self.fallback_tools:
+            try:
+                from tools.tool_registry import registry
+                registry.ensure_discovered()
+                fb_tool = registry.get(fallback_name)
+                if fb_tool is None:
+                    continue
+                if fb_tool.get_status() != ToolStatus.AVAILABLE:
+                    continue
+                logger.info("Falling back from %r to %r", self.name, fallback_name)
+                return fb_tool.execute_safe(inputs)
+            except Exception as exc:
+                logger.warning("Fallback %r failed: %s", fallback_name, exc)
+
+        return ToolResult(
+            success=False,
+            error=(
+                f"{self.name} timed out after {timeout:.0f}s "
+                f"and no fallback succeeded (tried: {self.fallback_tools})"
+            ),
+        )
```

---

## 2. `tools/video/_google_flow_base.py` — New File (Shared Base)

```python
"""Shared browser automation helpers for Google Flow tools.

Used by both google_flow_image and google_flow_video.
Internal module — do not import directly from outside tools/video/.

## UI Structure (discovered via live Playwright probe)

The settings panel is opened by clicking the combined model+aspect-ratio button
in the prompt bar (e.g. "Video\ncrop_16_9\nx2" or "🍌 Nano Banana 2\ncrop_16_9\nx2").

Panel tabs:
  image Image         → Image tab (Nano Banana / Imagen models, 5 aspect ratios)
  videocam Video      → Video tab (Veo models, 2 aspect ratios)
  crop_free Frames    → closes panel (no settable inputs)
  chrome_extension Ingredients → style preset picker (visual, not text-based)

Image models (from dropdown inside Image tab):
  🍌 Nano Banana Pro
  🍌 Nano Banana 2
  Imagen 4

Video models (from dropdown inside Video tab):
  volume_up Veo 3.1 - Fast
  volume_up Veo 3.1 - Lite
  (Veo 3.1 - Quality skipped — high cost)

Image aspect ratio button texts:
  crop_16_9    → 16:9
  crop_landscape → 4:3
  crop_square  → 1:1
  crop_portrait  → 3:4
  crop_9_16    → 9:16

Video aspect ratio button texts (only 2 options):
  crop_16_9    → 16:9
  crop_9_16    → 9:16
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

# Persistent session store
SESSION_DIR = Path.home() / ".openmontage"
FLOW_SESSION_FILE = SESSION_DIR / "google_flow_session.json"
FLOW_PROFILE_DIR = SESSION_DIR / "google_flow_profile"

# Default project URL
DEFAULT_FLOW_URL = (
    "https://labs.google/fx/tools/flow/project/"
    "c0de0689-8528-430d-af06-c4e39e1205d9"
)

IMAGE_MODELS = {"nano_banana", "nano_banana_pro", "imagen_4"}
VIDEO_MODELS = {"veo_fast", "veo_lite"}

IMAGE_MODEL_OPTION = {
    "nano_banana_pro": "Nano Banana Pro",
    "nano_banana":     "Nano Banana 2",
    "imagen_4":        "Imagen 4",
}
VIDEO_MODEL_OPTION = {
    "veo_fast": "Veo 3.1 - Fast",
    "veo_lite": "Veo 3.1 - Lite",
}

IMAGE_ASPECT_RATIO_ICON = {
    "16:9": "crop_16_9",
    "9:16": "crop_9_16",
    "1:1":  "crop_square",
    "4:3":  "crop_landscape",
    "3:4":  "crop_portrait",
}
VIDEO_ASPECT_RATIO_ICON = {
    "16:9": "crop_16_9",
    "9:16": "crop_9_16",
}


def launch_browser_context(pw, headless=True):
    """Launch persistent Chrome context from the saved Flow profile."""
    return pw.chromium.launch_persistent_context(
        user_data_dir=str(FLOW_PROFILE_DIR),
        channel="chrome",
        headless=headless,
        accept_downloads=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
        ],
        ignore_default_args=["--enable-automation"],
    )


def check_session_valid(page) -> bool:
    """Return True if page is inside Flow (not redirected to Google login)."""
    url = page.url
    return "accounts.google.com" not in url and "signin" not in url.lower()


def open_settings_panel(page) -> bool:
    """Click the combined model+settings button to open the panel."""
    candidates = ["Video", "Image", "Nano", "Banana", "Veo", "Imagen"]
    for b in page.locator("button").all():
        t = b.inner_text()
        if "crop_" in t and any(c in t for c in candidates):
            b.click()
            time.sleep(2)
            return True
    return False


def configure_image_settings(page, model: str, aspect_ratio: str) -> None:
    """Switch to Image tab, select model and aspect ratio inside the panel.
    Uses force=True to bypass Radix UI overlay interceptors.
    """
    # 1. Click Image tab
    image_tab = page.locator("button[role='tab']").filter(has_text="Image")
    if image_tab.count() > 0:
        image_tab.first.click(force=True)
        time.sleep(1.5)

    # 2. Select aspect ratio
    ar_icon = IMAGE_ASPECT_RATIO_ICON.get(aspect_ratio, "crop_square")
    ar_tabs = page.locator("button[role='tab']").filter(has_text=ar_icon)
    if ar_tabs.count() > 0:
        ar_tabs.first.click(force=True)
        time.sleep(0.5)

    # 3. Open model dropdown
    for b in page.locator("button").all():
        t = b.inner_text().strip().replace("\n", " ")
        if any(kw in t for kw in ("Nano Banana", "Imagen")) and "arrow_drop_down" in t:
            b.click(force=True)
            time.sleep(1.5)
            break

    # 4. Select model option
    model_text = IMAGE_MODEL_OPTION.get(model, "Nano Banana 2")
    for b in page.locator("button").all():
        t = b.inner_text().strip().replace("\n", " ")
        if model_text in t and "arrow_drop_down" not in t:
            b.click(force=True)
            return


def configure_video_settings(page, model: str, aspect_ratio: str) -> None:
    """Ensure Video tab is active, then select model and aspect ratio."""
    # 1. Click Video tab
    video_tab = page.locator("button[role='tab']").filter(has_text="Video")
    for i in range(video_tab.count()):
        el = video_tab.nth(i)
        t = el.inner_text().strip()
        if "videocam" in t or t == "Video":
            el.click(force=True)
            time.sleep(1.5)
            break

    # 2. Select aspect ratio
    ar_icon = VIDEO_ASPECT_RATIO_ICON.get(aspect_ratio, "crop_16_9")
    ar_tabs = page.locator("button[role='tab']").filter(has_text=ar_icon)
    if ar_tabs.count() > 0:
        ar_tabs.first.click(force=True)
        time.sleep(0.5)

    # 3. Open Veo dropdown
    for b in page.locator("button").all():
        t = b.inner_text().strip().replace("\n", " ")
        if "Veo 3.1" in t and "arrow_drop_down" in t:
            b.click(force=True)
            time.sleep(1.5)
            break

    # 4. Select model option
    model_text = VIDEO_MODEL_OPTION.get(model, "Veo 3.1 - Fast")
    for b in page.locator("button").all():
        t = b.inner_text().strip().replace("\n", " ")
        if model_text in t and "arrow_drop_down" not in t:
            b.click(force=True)
            return


def wait_for_generation(page, tiles_before: int, is_image: bool) -> bool:
    """Poll until a new tile appears. Returns True on success."""
    initial_wait = 30 if is_image else 60
    max_poll    = 300 if is_image else 420
    poll_interval = 10 if is_image else 15

    time.sleep(initial_wait)
    poll_start = time.time()

    while time.time() - poll_start < max_poll:
        time.sleep(poll_interval)
        failed = page.locator(
            ":has-text('Generation failed'), :has-text('Error generating'), :has-text('failed to generate')"
        ).count() > 0
        if failed:
            return False
        tiles_now = page.locator("img:not([class*='icon']):not([class*='logo'])").count()
        if tiles_now > tiles_before:
            return True
    return False


def upload_frame(page, which: str, file_path: str) -> bool:
    """Upload a first (Start) or last (End) frame image for video generation.
    The prompt bar uses div[type='button'] elements labeled 'Start'/'End'.
    """
    from pathlib import Path as _Path
    if not _Path(file_path).exists():
        return False

    frame_divs = page.locator("div[type='button']")
    target = None
    for i in range(frame_divs.count()):
        el = frame_divs.nth(i)
        if el.inner_text().strip() == which:
            target = el
            break

    if not target:
        return False

    target.click()
    time.sleep(1.5)

    fi = page.locator("input[type='file']")
    if fi.count() > 0:
        fi.first.set_input_files(str(file_path))
        time.sleep(1)
        return True
    return False


def upload_media_reference(page, file_path: str) -> bool:
    """Upload a local image/video as reference via hidden file input (+ button)."""
    from pathlib import Path as _Path
    if not _Path(file_path).exists():
        return False
    fi = page.locator("input[type='file']").first
    if fi.count() == 0:
        return False
    fi.set_input_files(str(file_path))
    time.sleep(1)
    return True


def open_download_submenu(page) -> None:
    """Hover tile → click more_vert → click Download submenu trigger.

    Image sub-menu:  [1K Original size]
    Video sub-menu:  [270p Animated GIF] [720p Original Size] [1080p Upscaled] [4K Upscaled Upgrade]
    """
    first_tile = page.locator("img:not([class*='icon']):not([class*='logo'])").nth(1)
    first_tile.hover()
    time.sleep(1.5)
    page.locator("button:has-text('more_vert')").last.click()
    time.sleep(1.5)
    dl_trigger = page.locator("div[role='menuitem']:has-text('Download')")
    if dl_trigger.count() > 0:
        dl_trigger.first.click()
        time.sleep(1.5)
    else:
        page.locator("text=Download").last.click()
        time.sleep(1.5)


def hover_download_menu(page) -> None:
    """Deprecated alias for open_download_submenu."""
    open_download_submenu(page)
```

---

## 3. `tools/video/google_flow_image.py` — New File

```python
"""Google Flow image generation via browser automation (Playwright).

Nano Banana Pro: best for text-in-image, posters, CTAs, typography
Nano Banana 2:   general high-quality image generation
Imagen 4:        Google Imagen 4 model

Uses subscription credits — no per-call API cost.
Falls back to flux_image → imagen_image → dalle_image.
"""

from tools.video._google_flow_base import (
    DEFAULT_FLOW_URL, FLOW_PROFILE_DIR, check_session_valid,
    configure_image_settings, hover_download_menu, launch_browser_context,
    open_settings_panel, upload_media_reference, wait_for_generation,
)

class GoogleFlowImage(BaseTool):
    name = "google_flow_image"
    version = "1.0.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "google_flow"
    runtime = ToolRuntime.HYBRID

    fallback_tools = ["flux_image", "imagen_image", "dalle_image"]

    input_schema = {
        "prompt": str,
        "model": ["nano_banana_pro", "nano_banana", "imagen_4"],  # default: nano_banana_pro
        "aspect_ratio": ["16:9", "9:16", "1:1", "4:3", "3:4"],   # default: 1:1
        "ingredients": [list of local file paths],                # uploaded via + button
        "output_path": str,
        "project_url": str,
    }

    # execute() flow:
    # 1. launch_browser_context(pw) → persistent profile at ~/.openmontage/google_flow_profile/
    # 2. goto flow_url, check_session_valid()
    # 3. open_settings_panel() → configure_image_settings(model, aspect_ratio) → Escape
    # 4. Type prompt into div[contenteditable='true']
    # 5. upload_media_reference() for each ingredient
    # 6. Click button:has-text('arrow_forward') to submit
    # 7. wait_for_generation(tiles_before, is_image=True)
    # 8. hover_download_menu() → click button:has-text('Original size')
    # 9. expect_download() → shutil.move() to output_path
```

---

## 4. `tools/video/google_flow_video.py` — New File

```python
"""Google Flow video generation via browser automation (Playwright).

Veo 3.1 Fast: balanced quality and speed (default)
Veo 3.1 Lite: lighter, faster variant

Uses subscription credits — no per-call API cost.
Falls back to kling_video → higgsfield_video → minimax_video.

For image generation, use google_flow_image instead.
"""

class GoogleFlowVideo(BaseTool):
    name = "google_flow_video"
    version = "0.3.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "google_flow"
    runtime = ToolRuntime.HYBRID

    fallback_tools = ["kling_video", "higgsfield_video", "minimax_video"]

    input_schema = {
        "prompt": str,
        "model": ["veo_fast", "veo_lite"],              # default: veo_fast
        "aspect_ratio": ["16:9", "9:16"],               # ONLY these two for video
        "first_frame": str,                              # local path → uploaded to Start div
        "last_frame": str,                               # local path → uploaded to End div
        "ingredients": [list of local file paths],
        "download_quality": ["270p", "720p", "1080p", "4k"],  # default: 720p
        "output_path": str,
        "project_url": str,
    }

    # execute() flow:
    # 1. launch_browser_context(pw)
    # 2. goto flow_url, check_session_valid()
    # 3. open_settings_panel() → configure_video_settings(model, aspect_ratio) → Escape
    # 4. Type prompt into div[contenteditable='true']
    # 5. upload_frame("Start", first_frame) if provided
    # 6. upload_frame("End", last_frame) if provided
    # 7. upload_media_reference() for each ingredient
    # 8. Click arrow_forward to submit
    # 9. wait_for_generation(tiles_before, is_image=False)
    # 10. hover_download_menu() → click button matching download_quality
    # 11. expect_download() → shutil.move() to output_path

    # NOTE: default download_quality changed from "1080p" → "720p"
    # (720p = Original Size = instant download, no server-side upscaling delay)
```

---

## 5. `tools/video/magic_hour_video.py` — New File

```python
"""Magic Hour cinematic video generation via Magic Hour API.

Cost: ~$0.04/second of video
Fallback: kling_video → higgsfield_video → minimax_video
"""

class MagicHourVideo(BaseTool):
    name = "magic_hour_video"
    version = "0.1.0"
    capability = "video_generation"
    provider = "magic_hour"
    runtime = ToolRuntime.API

    input_schema = {
        "prompt": str,
        "duration": int,          # 3–30 seconds, default 5
        "style": ["cinematic", "hyperreal", "ad", "natural"],  # default: cinematic
        "aspect_ratio": ["16:9", "9:16", "1:1"],               # default: 16:9
        "image_url": str,         # optional reference image
        "output_path": str,
    }

    # execute() flow:
    # 1. _enhance_prompt(prompt, style) — appends cinematic style keywords
    # 2. POST https://api.magichour.ai/v1/text-to-video
    #    body: { end_seconds, style: { prompt }, aspect_ratio }
    # 3. Poll GET https://api.magichour.ai/v1/video-projects/{id}
    #    until status in ("complete", "completed", "done", "success")
    # 4. Extract downloads[0].url
    # 5. GET video URL → write to output_path

    # Style enhancement map:
    # cinematic  → "golden hour lighting, soft shadows, shallow depth of field..."
    # hyperreal  → "photorealistic, 8K detail, physically accurate lighting..."
    # ad         → "clean product lighting, sharp focus, professional color grade..."
    # natural    → "natural lighting, realistic motion, authentic"
```

---

## 6. `tools/video/heygen_browser_video.py` — New File

```python
"""HeyGen subscription video via Playwright browser automation.

Uses subscription credits instead of API credits.
Falls back to heygen_video (API).
Session cookies saved to ~/.openmontage/heygen_session.json.
"""

class HeyGenBrowserVideo(BaseTool):
    name = "heygen_browser_video"
    version = "0.1.0"
    capability = "video_generation"
    provider = "heygen_browser"
    runtime = ToolRuntime.HYBRID

    fallback_tools = ["heygen_video"]

    input_schema = {
        "script": str,            # REQUIRED — narration text
        "avatar_id": str,         # optional HeyGen avatar ID
        "voice": str,             # default: "default"
        "language": str,          # default: "en"
        "tone": ["professional", "casual", "friendly", "authoritative"],
        "output_path": str,
    }

    # execute() flow:
    # 1. Load saved cookies from ~/.openmontage/heygen_session.json
    # 2. goto app.heygen.com/home — check if already logged in
    # 3. If not: goto /login → fill email/password → click submit → wait for /home
    # 4. Save cookies after login
    # 5. goto app.heygen.com/create
    # 6. Fill textarea[placeholder*='script'] with script text
    # 7. Click avatar if avatar_id provided
    # 8. Click Generate/Submit/Create Video button
    # 9. wait_for_url("**/video/**")
    # 10. Poll page.reload() every 10s, look for download button or a[href*='.mp4']
    # 11. Extract download URL → requests.get() → write to output_path
```

---

## 7. `tools/graphics/giphy_search.py` — New File

```python
"""GIF search via Giphy API.
Returns animated GIF URLs — no local download unless output_dir is set.
Cost: Free (Giphy free tier)
"""

class GiphySearch(BaseTool):
    name = "giphy_search"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "gif_search"
    provider = "giphy"
    runtime = ToolRuntime.API

    input_schema = {
        "query": str,             # REQUIRED
        "limit": int,             # 1–25, default 3
        "rating": ["g", "pg", "pg-13", "r"],  # default: pg
        "lang": str,              # default: "en"
        "trending": bool,         # default: False — use Giphy trending endpoint
        "output_dir": str,        # optional — download MP4s here
    }

    # Returns per GIF:
    # { id, title, rating, url, gif_url, mp4_url, webp_url, preview_url,
    #   width, height, size_bytes, local_path (if downloaded) }
    # Plus convenience fields:
    # { primary_mp4_url, primary_gif_url, primary_local_path }

    # execute() flow:
    # 1. GET api.giphy.com/v1/gifs/search (or /trending if trending=True)
    # 2. Map each result to { id, title, gif_url, mp4_url, webp_url, ... }
    # 3. If output_dir: download mp4_url for each result → save as giphy_{id}.mp4
```

---

## AGENT_GUIDE.md — Key Additions (Diff Summary)

```diff
+ ## Browser Subscription Tools
+   heygen_browser_video — avatar video via HeyGen web UI (subscription credits)
+   google_flow_video    — Veo video via Google Flow web UI (subscription credits)
+   How they work: Playwright → session cookies → form fill → poll → download
+   Fallback chains: heygen_browser → heygen_video, google_flow → kling_video

+ ## Resilient Execution — execute_safe()
+   timeout = max(30s, min(estimate_runtime × 2, 600s))
+   Auto-falls back to first available tool in fallback_tools[]
+   Always use execute_safe() for cloud generation tools

+ ## New Tools Reference
+   magic_hour_video — cinematic video, ~$0.04/sec, fallback: kling→higgsfield→minimax
+   giphy_search     — GIF search, free, returns URLs + optional MP4 download
+   heygen_browser_video — avatar video, $0 subscription, fallback: heygen_video
+   google_flow_image    — Nano Banana/Imagen4 images, $0 subscription
+   google_flow_video    — Veo 3.1 Fast/Lite video, $0 subscription

+ ## Setup Guide
+   Step 1: Fill HEYGEN_EMAIL/PASSWORD, GOOGLE_FLOW_EMAIL in .env
+   Step 2: Playwright already installed ✓
+   Step 3: HeyGen first-time login (auto)
+   Step 4: Google Flow first-time OAuth (manual — must click in browser)
+   Step 5: python3 verify all tools available
+   Step 6: pip install faster-whisper (optional)
+   Step 7: pip install yt-dlp (optional)
```

---

## Known Issues / Pending

| Issue | Status |
|-------|--------|
| Video smoke test (veo_fast 720p) | ⚠️ Not retested after 720p fix — needs one more run |
| `google_flow_video.py` has stale `download_quality` default `"1080p"` in execute() | ⚠️ Should be `"720p"` — base default is correct in schema but line 218 uses `"1080p"` as fallback |
| `heygen_browser_video` session check is fragile | `[data-testid='user-menu']` may not exist in all HeyGen UI versions |
| `magic_hour_video` endpoint not smoke-tested | API endpoint assumed correct, not verified live |
| Nothing committed yet | ⚠️ 9 files of work uncommitted — vulnerable to disk loss |

---

## Quick Commit Command

```bash
cd /Users/amankhanna/claude/videoagent
git add tools/base_tool.py \
        tools/video/_google_flow_base.py \
        tools/video/google_flow_image.py \
        tools/video/google_flow_video.py \
        tools/video/magic_hour_video.py \
        tools/video/heygen_browser_video.py \
        tools/graphics/giphy_search.py \
        AGENT_GUIDE.md \
        PROJECT_CONTEXT.md

git commit -m "feat: add google_flow split, magic_hour, heygen_browser, giphy tools + execute_safe"
```
