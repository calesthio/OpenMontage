# Google Flow Multi-Account Sequential Fallback — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Support 3 Google Flow accounts (session_1/2/3) with automatic sequential fallback — when one account fails (auth expired, quota, generation error), the tool transparently tries the next account before returning an error.

**Architecture:** Add multi-slot session management to `_google_flow_base.py` (shared constants + helpers), update `google_flow_setup.py` to accept `--slot N`, and refactor both `google_flow_image.py` and `google_flow_video.py` to loop over available slots. Slot 1 retains the legacy (unnumbered) path so existing setups are not broken.

**Tech Stack:** Python, Playwright, existing `BaseTool` pattern. All files live in `tools/video/`.

---

## Critical Files

| File | Action |
|------|--------|
| `tools/video/_google_flow_base.py` | Modify — add slot constants + helper functions |
| `tools/video/google_flow_setup.py` | Modify — add `--slot` CLI argument |
| `tools/video/google_flow_image.py` | Modify — extract browser body, add slot loop |
| `tools/video/google_flow_video.py` | Modify — extract browser body, add slot loop |

Session files live in `~/.openmontage/` (gitignored, never in the repo):

| Slot | Profile dir | Session file |
|------|-------------|--------------|
| 1 | `~/.openmontage/google_flow_profile/` | `google_flow_session.json` (legacy compat) |
| 2 | `~/.openmontage/google_flow_profile_2/` | `google_flow_session_2.json` |
| 3 | `~/.openmontage/google_flow_profile_3/` | `google_flow_session_3.json` |

---

## Task 1: Update `_google_flow_base.py` — multi-slot constants + helpers

**Files:**
- Modify: `tools/video/_google_flow_base.py`

**Step 1: Add slot dictionaries and helper functions after the existing constants (after line 87)**

Insert the following block right after `VIDEO_ASPECT_RATIO_ICON`:

```python
# ---------------------------------------------------------------------------
# Multi-account session slots
# Slot 1 uses the legacy unnumbered path so existing setups keep working.
# Slots 2 and 3 use numbered paths.
# ---------------------------------------------------------------------------
MAX_SESSIONS = 3

_SLOT_PROFILE_DIRS: dict[int, Path] = {
    1: SESSION_DIR / "google_flow_profile",      # legacy path — backward compat
    2: SESSION_DIR / "google_flow_profile_2",
    3: SESSION_DIR / "google_flow_profile_3",
}
_SLOT_SESSION_FILES: dict[int, Path] = {
    1: SESSION_DIR / "google_flow_session.json",  # legacy path — backward compat
    2: SESSION_DIR / "google_flow_session_2.json",
    3: SESSION_DIR / "google_flow_session_3.json",
}


def get_slot_paths(slot: int) -> tuple[Path, Path]:
    """Return (profile_dir, session_file) for a given slot number (1-3)."""
    if slot not in _SLOT_PROFILE_DIRS:
        raise ValueError(f"Invalid slot {slot}. Must be 1-{MAX_SESSIONS}.")
    return _SLOT_PROFILE_DIRS[slot], _SLOT_SESSION_FILES[slot]


def get_available_slots() -> list[int]:
    """Return list of slot numbers whose profile directory exists (in order)."""
    return [s for s in range(1, MAX_SESSIONS + 1) if _SLOT_PROFILE_DIRS[s].exists()]


def launch_browser_context_for_slot(
    pw: object, slot: int, headless: bool = True
) -> "BrowserContext":
    """Launch a persistent Chrome context for the given slot number."""
    profile_dir, _ = get_slot_paths(slot)
    return pw.chromium.launch_persistent_context(  # type: ignore[attr-defined]
        user_data_dir=str(profile_dir),
        channel="chrome",
        headless=headless,
        accept_downloads=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
        ],
        ignore_default_args=["--enable-automation"],
    )
```

**Step 2: Verify by running a quick import check**

```bash
cd /Users/amankhanna/claude/videoagent/.claude/worktrees/busy-leavitt
python -c "from tools.video._google_flow_base import get_available_slots, get_slot_paths, MAX_SESSIONS; print('OK', MAX_SESSIONS)"
```
Expected output: `OK 3`

**Step 3: Commit**

```bash
git add tools/video/_google_flow_base.py
git commit -m "feat(google-flow): add multi-slot session constants + helpers to base"
```

---

## Task 2: Update `google_flow_setup.py` — add `--slot` argument

**Files:**
- Modify: `tools/video/google_flow_setup.py`

**Step 1: Replace the file's `main()` and top-level constants with the multi-slot version**

Replace the entire file content:

```python
"""One-time Google Flow OAuth setup — supports up to 3 accounts.

Run once per Google account to save its browser profile and session cookies:

    # Slot 1 (default — backward compat with existing setups):
    python3 -m tools.video.google_flow_setup

    # Slot 2 (second Google account):
    python3 -m tools.video.google_flow_setup --slot 2

    # Slot 3 (third Google account):
    python3 -m tools.video.google_flow_setup --slot 3

This opens a visible Chromium browser. Complete the Google sign-in,
navigate to https://labs.google/flow, then press ENTER in this terminal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.video._google_flow_base import (
    MAX_SESSIONS,
    SESSION_DIR,
    get_slot_paths,
)

_FLOW_URL = "https://labs.google/fx/tools/flow"


def setup_slot(slot: int) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    profile_dir, session_file = get_slot_paths(slot)

    print("=" * 60)
    print(f"Google Flow — One-time login setup (slot {slot}/{MAX_SESSIONS})")
    print("=" * 60)
    print()
    print(f"Profile will be saved to: {profile_dir}")
    print(f"Session file:             {session_file}")
    print()
    print("A browser window will open. Sign in with your Google account")
    print(f"that has Google Flow access, then press ENTER here.")
    print()
    input("Press ENTER to open the browser...")

    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
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
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page.goto(_FLOW_URL)

        print()
        print(f"Browser opened at {_FLOW_URL}")
        print("Sign in with Google if prompted, then wait for the Flow UI.")
        print()
        input("Once inside Google Flow (can see the prompt box), press ENTER...")

        cookies = context.cookies()
        session_file.write_text(json.dumps({"cookies": cookies, "slot": slot}, indent=2))
        context.close()

    if cookies:
        print()
        print(f"Slot {slot} saved ({len(cookies)} cookies) → {session_file}")
        print("google_flow_image / google_flow_video will use this slot automatically.")
    else:
        print("WARNING: No cookies captured. Make sure you completed login.")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-time Google Flow browser login — saves session for a given slot."
    )
    parser.add_argument(
        "--slot",
        type=int,
        default=1,
        choices=list(range(1, MAX_SESSIONS + 1)),
        help=f"Account slot to configure (1-{MAX_SESSIONS}, default: 1).",
    )
    args = parser.parse_args()
    setup_slot(args.slot)


if __name__ == "__main__":
    main()
```

**Step 2: Verify syntax**

```bash
python -c "import ast, pathlib; ast.parse(pathlib.Path('tools/video/google_flow_setup.py').read_text()); print('syntax OK')"
```
Expected: `syntax OK`

**Step 3: Commit**

```bash
git add tools/video/google_flow_setup.py
git commit -m "feat(google-flow): add --slot arg to setup script, support 3 accounts"
```

---

## Task 3: Refactor `google_flow_image.py` — sequential slot fallback

**Files:**
- Modify: `tools/video/google_flow_image.py`

**Step 1: Update imports at the top of the file**

The existing import block imports `FLOW_PROFILE_DIR` and `launch_browser_context`. Replace those two with the new multi-slot helpers:

```python
from tools.video._google_flow_base import (
    DEFAULT_FLOW_URL,
    check_session_valid,
    configure_image_settings,
    get_available_slots,
    hover_download_menu,
    launch_browser_context_for_slot,
    open_settings_panel,
    upload_media_reference,
    wait_for_generation,
)
```

**Step 2: Replace the `execute()` method and add `_try_slot()`**

The new design:
- `_try_slot(slot, pw, inputs, output_path)` — contains the entire current browser automation body, parameterised by slot.
- `execute()` — validates prereqs, then iterates `get_available_slots()`, calling `_try_slot` until one succeeds.

Replace the entire `execute()` method (lines 172-316) with:

```python
    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not self._has_playwright():
            return ToolResult(
                success=False,
                error="Playwright not installed. Run: pip install playwright && playwright install chromium",
            )
        if not self._has_credentials():
            return ToolResult(
                success=False,
                error="GOOGLE_FLOW_EMAIL must be set. " + self.install_instructions,
            )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ToolResult(
                success=False,
                error="playwright package not importable. Run: pip install playwright",
            )

        slots = get_available_slots()
        if not slots:
            return ToolResult(
                success=False,
                error=(
                    "No Google Flow profiles found. Run the one-time setup:\n"
                    "  python3 -m tools.video.google_flow_setup\n"
                    "  python3 -m tools.video.google_flow_setup --slot 2  # for a second account"
                ),
            )

        output_path = self._resolve_output_path(inputs)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        last_error: str = ""
        with sync_playwright() as pw:
            for slot in slots:
                result = self._try_slot(slot, pw, inputs, output_path)
                if result.success:
                    return result
                last_error = result.error or "unknown error"
                print(f"[google_flow_image] slot {slot} failed: {last_error} — trying next account…")

        return ToolResult(
            success=False,
            error=f"All {len(slots)} Google Flow account(s) failed. Last error: {last_error}",
        )

    def _try_slot(
        self,
        slot: int,
        pw: Any,
        inputs: dict[str, Any],
        output_path: Path,
    ) -> ToolResult:
        """Attempt image generation using a single browser slot. Returns ToolResult."""
        import shutil as _shutil

        start = time.time()
        prompt = inputs["prompt"]
        model = inputs.get("model", "nano_banana_pro")
        aspect_ratio = inputs.get("aspect_ratio", "1:1")
        ingredients = inputs.get("ingredients", [])
        flow_url = inputs.get("project_url") or DEFAULT_FLOW_URL

        try:
            context = launch_browser_context_for_slot(pw, slot)
            page = context.new_page()
            page.set_viewport_size({"width": 1440, "height": 900})
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page.goto(flow_url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            if not check_session_valid(page):
                context.close()
                return ToolResult(
                    success=False,
                    error=f"slot {slot}: session expired — re-run google_flow_setup --slot {slot}",
                )

            if open_settings_panel(page):
                configure_image_settings(page, model, aspect_ratio)
                page.keyboard.press("Escape")
                time.sleep(0.5)

            prompt_input = page.locator("div[contenteditable='true']").first
            prompt_input.wait_for(timeout=15000)
            prompt_input.click()
            page.keyboard.press("Control+a")
            page.keyboard.type(prompt)

            for ingredient_path in ingredients:
                upload_media_reference(page, ingredient_path)

            generate_btn = page.locator("button:has-text('arrow_forward')")
            generate_btn.first.click()

            tiles_before = page.locator(
                "img:not([class*='icon']):not([class*='logo'])"
            ).count()
            success = wait_for_generation(page, tiles_before, is_image=True)
            if not success:
                context.close()
                return ToolResult(
                    success=False,
                    error=f"slot {slot}: generation failed or timed out",
                )

            hover_download_menu(page)
            with page.expect_download(timeout=60000) as dl_info:
                orig_btn = page.locator("button:has-text('Original size')")
                if orig_btn.count() > 0:
                    orig_btn.first.click()
                else:
                    page.locator("div[role='menuitem']:has-text('Download')").first.click()

            _shutil.move(str(dl_info.value.path()), str(output_path))
            context.close()

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"slot {slot}: browser automation failed: {exc}",
            )

        if not output_path.exists():
            return ToolResult(
                success=False,
                error=f"slot {slot}: generation completed but no file saved",
            )

        return ToolResult(
            success=True,
            data={
                "provider": "google_flow",
                "model": model,
                "output_type": "image",
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "ingredients": ingredients,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "png",
                "credits_source": "subscription",
                "slot_used": slot,
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
```

**Step 3: Verify syntax**

```bash
python -c "import ast, pathlib; ast.parse(pathlib.Path('tools/video/google_flow_image.py').read_text()); print('syntax OK')"
```
Expected: `syntax OK`

**Step 4: Commit**

```bash
git add tools/video/google_flow_image.py
git commit -m "feat(google-flow): sequential account fallback in google_flow_image"
```

---

## Task 4: Refactor `google_flow_video.py` — sequential slot fallback

**Files:**
- Modify: `tools/video/google_flow_video.py`

**Step 1: Update imports — same pattern as Task 3**

Replace `FLOW_PROFILE_DIR` and `launch_browser_context` with:

```python
from tools.video._google_flow_base import (
    DEFAULT_FLOW_URL,
    check_session_valid,
    configure_video_settings,
    get_available_slots,
    hover_download_menu,
    launch_browser_context_for_slot,
    open_settings_panel,
    upload_frame,
    upload_media_reference,
    wait_for_generation,
)
```

**Step 2: Replace `execute()` and add `_try_slot()`**

Replace the entire `execute()` method (lines 185-337) with:

```python
    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not self._has_playwright():
            return ToolResult(
                success=False,
                error="Playwright not installed. Run: pip install playwright && playwright install chromium",
            )
        if not self._has_credentials():
            return ToolResult(
                success=False,
                error="GOOGLE_FLOW_EMAIL must be set. " + self.install_instructions,
            )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ToolResult(
                success=False,
                error="playwright package not importable. Run: pip install playwright",
            )

        slots = get_available_slots()
        if not slots:
            return ToolResult(
                success=False,
                error=(
                    "No Google Flow profiles found. Run the one-time setup:\n"
                    "  python3 -m tools.video.google_flow_setup\n"
                    "  python3 -m tools.video.google_flow_setup --slot 2  # for a second account"
                ),
            )

        raw_output = inputs.get("output_path", "google_flow_output.mp4")
        output_path = Path(raw_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        last_error: str = ""
        with sync_playwright() as pw:
            for slot in slots:
                result = self._try_slot(slot, pw, inputs, output_path)
                if result.success:
                    return result
                last_error = result.error or "unknown error"
                print(f"[google_flow_video] slot {slot} failed: {last_error} — trying next account…")

        return ToolResult(
            success=False,
            error=f"All {len(slots)} Google Flow account(s) failed. Last error: {last_error}",
        )

    def _try_slot(
        self,
        slot: int,
        pw: Any,
        inputs: dict[str, Any],
        output_path: Path,
    ) -> ToolResult:
        """Attempt video generation using a single browser slot. Returns ToolResult."""
        import shutil as _shutil

        start = time.time()
        prompt = inputs["prompt"]
        model = inputs.get("model", "veo_fast")
        aspect_ratio = inputs.get("aspect_ratio", "16:9")
        ingredients = inputs.get("ingredients", [])
        flow_url = inputs.get("project_url") or DEFAULT_FLOW_URL

        try:
            context = launch_browser_context_for_slot(pw, slot)
            page = context.new_page()
            page.set_viewport_size({"width": 1440, "height": 900})
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page.goto(flow_url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            if not check_session_valid(page):
                context.close()
                return ToolResult(
                    success=False,
                    error=f"slot {slot}: session expired — re-run google_flow_setup --slot {slot}",
                )

            if open_settings_panel(page):
                configure_video_settings(page, model, aspect_ratio)
                page.keyboard.press("Escape")
                time.sleep(0.5)

            prompt_input = page.locator("div[contenteditable='true']").first
            prompt_input.wait_for(timeout=15000)
            prompt_input.click()
            page.keyboard.press("Control+a")
            page.keyboard.type(prompt)

            first_frame = inputs.get("first_frame")
            last_frame = inputs.get("last_frame")
            if first_frame:
                upload_frame(page, "Start", first_frame)
            if last_frame:
                upload_frame(page, "End", last_frame)

            for ingredient_path in ingredients:
                upload_media_reference(page, ingredient_path)

            generate_btn = page.locator("button:has-text('arrow_forward')")
            generate_btn.first.click()

            tiles_before = page.locator(
                "img:not([class*='icon']):not([class*='logo'])"
            ).count()
            success = wait_for_generation(page, tiles_before, is_image=False)
            if not success:
                context.close()
                return ToolResult(
                    success=False,
                    error=f"slot {slot}: generation failed or timed out",
                )

            hover_download_menu(page)
            dl_quality = inputs.get("download_quality", "1080p")
            quality_btn = page.locator(f"button:has-text('{dl_quality}')")
            if quality_btn.count() == 0:
                quality_btn = page.locator("button:has-text('1080p')")
            with page.expect_download(timeout=60000) as dl_info:
                quality_btn.first.click()

            _shutil.move(str(dl_info.value.path()), str(output_path))
            context.close()

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"slot {slot}: browser automation failed: {exc}",
            )

        if not output_path.exists():
            return ToolResult(
                success=False,
                error=f"slot {slot}: generation completed but no file saved",
            )

        return ToolResult(
            success=True,
            data={
                "provider": "google_flow",
                "model": model,
                "output_type": "video",
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "first_frame": inputs.get("first_frame"),
                "last_frame": inputs.get("last_frame"),
                "ingredients": ingredients,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                "credits_source": "subscription",
                "slot_used": slot,
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
```

**Step 3: Verify syntax**

```bash
python -c "import ast, pathlib; ast.parse(pathlib.Path('tools/video/google_flow_video.py').read_text()); print('syntax OK')"
```
Expected: `syntax OK`

**Step 4: Commit**

```bash
git add tools/video/google_flow_video.py
git commit -m "feat(google-flow): sequential account fallback in google_flow_video"
```

---

## Task 5: End-to-end verification

**Step 1: Import-level smoke test (no Playwright needed)**

```bash
cd /Users/amankhanna/claude/videoagent/.claude/worktrees/busy-leavitt
python -c "
from tools.video._google_flow_base import get_available_slots, get_slot_paths, MAX_SESSIONS, launch_browser_context_for_slot
from tools.video.google_flow_image import GoogleFlowImage
from tools.video.google_flow_video import GoogleFlowVideo
img = GoogleFlowImage()
vid = GoogleFlowVideo()
print('MAX_SESSIONS:', MAX_SESSIONS)
print('slot 1 paths:', get_slot_paths(1))
print('slot 2 paths:', get_slot_paths(2))
print('slot 3 paths:', get_slot_paths(3))
print('available slots:', get_available_slots())
print('image tool status:', img.get_status())
print('video tool status:', vid.get_status())
print('ALL OK')
"
```

Expected: all paths print correctly, available slots lists only those with existing `~/.openmontage/google_flow_profile*` dirs, status prints without exception.

**Step 2: Registry discovery check**

```bash
python -c "
from tools.tool_registry import registry
import json
registry.discover()
catalog = registry.capability_catalog()
img_tools = [t for t in catalog.get('image_generation', []) if 'google_flow' in t.get('name','')]
vid_tools = [t for t in catalog.get('video_generation', []) if 'google_flow' in t.get('name','')]
print('image:', img_tools)
print('video:', vid_tools)
"
```

Expected: both tools appear in their respective capability lists.

**Step 3: Setup script help check**

```bash
python -m tools.video.google_flow_setup --help
```

Expected: shows `--slot {1,2,3}` argument in usage.

---

## Fallback Behaviour Summary

| Scenario | Behaviour |
|----------|-----------|
| Slot 1 session expired | Tries slot 2 → slot 3 → error with all-failed message |
| Slot 1 generation timeout | Tries slot 2 → slot 3 → error |
| Only slot 1 set up | Tries slot 1, fails fast with single-slot error |
| All 3 slots succeed on first | Returns slot 1 result immediately |
| Slot 2 succeeds after slot 1 fails | Returns slot 2 result, logs slot 1 failure |
| `slot_used` in result data | Agent and user can see which account produced the output |
