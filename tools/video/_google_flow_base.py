"""Shared browser automation helpers for Google Flow tools.

Used by both google_flow_image and google_flow_video.
Internal module — do not import directly from outside tools/video/.

## UI Structure (confirmed via live Playwright codegen recording)

Settings panel opened by clicking the combined model+aspect-ratio button in the
prompt bar (e.g. "Video\\ncrop_16_9\\nx2" or "🍌 Nano Banana 2\\ncrop_16_9\\nx2").

Panel tabs (row 1):
  image Image         → Image tab (Nano Banana / Imagen models)
  videocam Video      → Video tab (Veo models)
  crop_free Frames    → First/Last frame upload (video mode only)
  chrome_extension Ingredients → visual preset cards

Panel tabs (row 2 — aspect ratios):
  crop_16_9   → 16:9
  crop_landscape → 4:3
  crop_square → 1:1
  crop_portrait  → 3:4
  crop_9_16   → 9:16

Panel tabs (row 3 — quality multiplier, applies to both image and video):
  x1 / x2 / x3 / x4

Image models (dropdown):
  🍌 Nano Banana Pro
  🍌 Nano Banana 2
  Imagen 4

Video models (dropdown):
  Veo 3.1 - Fast
  Veo 3.1 - Lite
  (Veo 3.1 - Quality skipped — high cost)

Download menu (after clicking role=button name="download Download"):
  Image: menuitem "Original size"
  Video: menuitem "270p Animated GIF"
         menuitem "720p Original Size"
         menuitem "1080p Upscaled"
         menuitem "4K Upscaled Upgrade"

Camera motion panel (video detail view):
  role=button name="videocam Camera"  → opens panel
  role=tab name="Camera motion"       → Camera motion tab
  Buttons: "Dolly in", "Dolly out", "Orbit left", "Orbit up", "Dolly out zoom in"

Continue/extend video:
  role=button name="keyboard_double_arrow_right"  → opens "What happens next?" prompt
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

# Models that produce images
IMAGE_MODELS = {"nano_banana", "nano_banana_pro", "imagen_4"}
# Models that produce video
VIDEO_MODELS = {"veo_fast", "veo_lite"}

# Button text in model dropdown
IMAGE_MODEL_OPTION = {
    "nano_banana_pro": "Nano Banana Pro",
    "nano_banana":     "Nano Banana 2",
    "imagen_4":        "Imagen 4",
}
VIDEO_MODEL_OPTION = {
    "veo_fast": "Veo 3.1 - Fast",
    "veo_lite": "Veo 3.1 - Lite",
}

# Aspect ratio → Material icon substring in tab name
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

# Download quality → menuitem aria-label / name
VIDEO_DOWNLOAD_QUALITY_LABEL = {
    "270p": "270p Animated GIF",
    "720p": "720p Original Size",
    "1080p": "1080p Upscaled",
    "4k":   "4K Upscaled Upgrade",
}
IMAGE_DOWNLOAD_LABEL = "Original size"

# Maximum number of ingredient files the Flow UI accepts
MAX_INGREDIENTS = 5

# Camera motion → button name
CAMERA_MOTION_BUTTON = {
    "dolly_in":        "Dolly in",
    "dolly_out":       "Dolly out",
    "orbit_left":      "Orbit left",
    "orbit_up":        "Orbit up",
    "dolly_out_zoom":  "Dolly out zoom in",
}


def launch_browser_context(pw: object, headless: bool = True) -> "BrowserContext":
    """Launch persistent Chrome context from the saved Flow profile."""
    return pw.chromium.launch_persistent_context(  # type: ignore[attr-defined]
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


def check_session_valid(page: "Page") -> bool:
    """Return True if page is inside Flow (not redirected to Google login)."""
    url = page.url
    return "accounts.google.com" not in url and "signin" not in url.lower()


def open_settings_panel(page: "Page") -> bool:
    """Click the combined model+settings button to open the settings panel.

    The button always contains a Material icon aspect-ratio name (crop_*) plus
    a model name or 'Video'/'Image'. Returns True if the panel was opened.
    """
    candidates = ["Video", "Image", "Nano", "Banana", "Veo", "Imagen"]
    for b in page.locator("button").all():
        t = b.inner_text()
        if "crop_" in t and any(c in t for c in candidates):
            b.click()
            time.sleep(2)
            return True
    print("DEBUG open_settings_panel: button not found")
    return False


def configure_image_settings(
    page: "Page",
    model: str,
    aspect_ratio: str,
    quantity: str = "x1",
) -> None:
    """Switch to Image tab, select model, aspect ratio, and quality multiplier.

    Uses force=True for tab clicks — Radix dropdown popper wrappers can
    intercept pointer events on children.
    """
    # 1. Click Image tab
    image_tab = page.locator("button[role='tab']").filter(has_text="Image")
    if image_tab.count() > 0:
        try:
            image_tab.first.click(force=True)
            time.sleep(1.5)
        except Exception as e:
            print(f"DEBUG configure_image_settings: Image tab click failed: {e}")

    # 2. Select aspect ratio
    ar_icon = IMAGE_ASPECT_RATIO_ICON.get(aspect_ratio, "crop_square")
    ar_tabs = page.locator("button[role='tab']").filter(has_text=ar_icon)
    if ar_tabs.count() > 0:
        try:
            ar_tabs.first.click(force=True)
            time.sleep(0.5)
        except Exception as e:
            print(f"DEBUG configure_image_settings: aspect ratio '{ar_icon}' click failed: {e}")
    else:
        print(f"DEBUG configure_image_settings: aspect ratio icon '{ar_icon}' not found")

    # 3. Select quantity (x1/x2/x3/x4 = number of outputs to generate)
    if quantity in ("x1", "x2", "x3", "x4"):
        qm_tab = page.get_by_role("tab", name=quantity)
        if qm_tab.count() > 0:
            try:
                qm_tab.first.click(force=True)
                time.sleep(0.5)
            except Exception as e:
                print(f"DEBUG configure_image_settings: quantity '{quantity}' click failed: {e}")

    # 4. Open model dropdown
    _image_model_keywords = ("Nano Banana", "Imagen")
    for b in page.locator("button").all():
        t = b.inner_text().strip().replace("\n", " ")
        if any(kw in t for kw in _image_model_keywords) and "arrow_drop_down" in t:
            try:
                b.click(force=True)
                time.sleep(1.5)
            except Exception as e:
                print(f"DEBUG configure_image_settings: model dropdown click failed: {e}")
            break

    # 5. Select model option from dropdown
    model_text = IMAGE_MODEL_OPTION.get(model, "Nano Banana 2")
    for b in page.locator("button").all():
        t = b.inner_text().strip().replace("\n", " ")
        if model_text in t and "arrow_drop_down" not in t:
            try:
                b.click(force=True)
                time.sleep(0.5)
            except Exception as e:
                print(f"DEBUG configure_image_settings: model option click failed: {e}")
            return
    print(f"DEBUG configure_image_settings: model option '{model_text}' not found")


def configure_video_settings(
    page: "Page",
    model: str,
    aspect_ratio: str,
    quantity: str = "x1",
) -> None:
    """Ensure Video tab is active, then select model, aspect ratio, and quality multiplier.

    Uses force=True for tab clicks — Radix dropdown popper wrappers can
    intercept pointer events on children.
    """
    # 1. Click Video tab
    video_tab = page.locator("button[role='tab']").filter(has_text="Video")
    for i in range(video_tab.count()):
        el = video_tab.nth(i)
        t = el.inner_text().strip()
        if "videocam" in t or t == "Video":
            try:
                el.click(force=True)
                time.sleep(1.5)
            except Exception as e:
                print(f"DEBUG configure_video_settings: Video tab click failed: {e}")
            break

    # 2. Select aspect ratio
    ar_icon = VIDEO_ASPECT_RATIO_ICON.get(aspect_ratio, "crop_16_9")
    ar_tabs = page.locator("button[role='tab']").filter(has_text=ar_icon)
    if ar_tabs.count() > 0:
        try:
            ar_tabs.first.click(force=True)
            time.sleep(0.5)
        except Exception as e:
            print(f"DEBUG configure_video_settings: aspect ratio '{ar_icon}' click failed: {e}")
    else:
        print(f"DEBUG configure_video_settings: aspect ratio '{ar_icon}' not found")

    # 3. Select quantity (x1/x2/x3/x4 = number of clips to generate)
    if quantity in ("x1", "x2", "x3", "x4"):
        qm_tab = page.get_by_role("tab", name=quantity)
        if qm_tab.count() > 0:
            try:
                qm_tab.first.click(force=True)
                time.sleep(0.5)
            except Exception as e:
                print(f"DEBUG configure_video_settings: quantity '{quantity}' click failed: {e}")

    # 4. Open Veo model dropdown
    for b in page.locator("button").all():
        t = b.inner_text().strip().replace("\n", " ")
        if "Veo 3.1" in t and "arrow_drop_down" in t:
            try:
                b.click(force=True)
                time.sleep(1.5)
            except Exception as e:
                print(f"DEBUG configure_video_settings: Veo dropdown click failed: {e}")
            break

    # 5. Select model option
    model_text = VIDEO_MODEL_OPTION.get(model, "Veo 3.1 - Fast")
    for b in page.locator("button").all():
        t = b.inner_text().strip().replace("\n", " ")
        if model_text in t and "arrow_drop_down" not in t:
            try:
                b.click(force=True)
                time.sleep(0.5)
            except Exception as e:
                print(f"DEBUG configure_video_settings: model option click failed: {e}")
            return
    print(f"DEBUG configure_video_settings: model option '{model_text}' not found")


def apply_camera_motion(page: "Page", camera_motion: str) -> None:
    """Apply a camera motion preset to the currently open video clip.

    Must be called when a video tile/detail is open.

    Args:
        camera_motion: one of "dolly_in", "dolly_out", "orbit_left",
                       "orbit_up", "dolly_out_zoom"
    """
    btn_name = CAMERA_MOTION_BUTTON.get(camera_motion)
    if not btn_name:
        print(f"DEBUG apply_camera_motion: unknown motion '{camera_motion}'")
        return

    # Open camera panel
    cam_btn = page.get_by_role("button", name="videocam Camera")
    if cam_btn.count() == 0:
        print("DEBUG apply_camera_motion: Camera button not found")
        return
    cam_btn.first.click()
    time.sleep(1.5)

    # Switch to Camera motion tab
    motion_tab = page.get_by_role("tab", name="Camera motion")
    if motion_tab.count() > 0:
        motion_tab.first.click()
        time.sleep(0.5)

    # Click the motion button
    motion_btn = page.get_by_role("button", name=btn_name, exact=True)
    if motion_btn.count() > 0:
        motion_btn.first.click()
        time.sleep(0.5)
    else:
        print(f"DEBUG apply_camera_motion: button '{btn_name}' not found")


def wait_for_generation(page: "Page", tiles_before: int, is_image: bool) -> bool:
    """Poll until a new tile appears. Returns True on success, False on timeout."""
    initial_wait = 30 if is_image else 60
    max_poll    = 300 if is_image else 420
    poll_interval = 10 if is_image else 15

    time.sleep(initial_wait)
    poll_start = time.time()

    while time.time() - poll_start < max_poll:
        time.sleep(poll_interval)

        failed = page.locator(
            ":has-text('Generation failed'), "
            ":has-text('Error generating'), "
            ":has-text('failed to generate')"
        ).count() > 0
        if failed:
            return False

        tiles_now = page.locator(
            "img:not([class*='icon']):not([class*='logo'])"
        ).count()
        if tiles_now > tiles_before:
            return True

    return False


def upload_frame(page: "Page", which: str, file_path: str) -> bool:
    """Upload a first or last frame image for video generation.

    In Video mode the prompt bar shows "Start" and "End" text elements.
    Clicking opens an "Upload image" option which leads to a file dialog.

    Args:
        which: "Start" or "End"
        file_path: absolute path to the image file
    """
    from pathlib import Path as _Path
    if not _Path(file_path).exists():
        print(f"DEBUG upload_frame: file not found: {file_path}")
        return False

    # Click the Start/End placeholder in the prompt bar
    frame_el = page.get_by_text(which, exact=True)
    if frame_el.count() == 0:
        # Fallback: div[type='button'] approach
        frame_divs = page.locator("div[type='button']")
        for i in range(frame_divs.count()):
            el = frame_divs.nth(i)
            if el.inner_text().strip() == which:
                el.click()
                time.sleep(1.5)
                break
        else:
            print(f"DEBUG upload_frame: '{which}' element not found in prompt bar")
            return False
    else:
        frame_el.first.click()
        time.sleep(1.5)

    # Click "Upload image" option if it appears
    upload_opt = page.get_by_text("Upload image")
    if upload_opt.count() > 0:
        upload_opt.first.click()
        time.sleep(0.5)

    # Set file on the dialog input
    fi = page.get_by_role("dialog").locator("input[type='file']")
    if fi.count() == 0:
        fi = page.locator("input[type='file']")
    if fi.count() > 0:
        fi.first.set_input_files(str(file_path))
        time.sleep(1)
        return True

    print(f"DEBUG upload_frame: no file input found after clicking {which}")
    return False


def upload_media_reference(page: "Page", file_path: str) -> bool:
    """Upload a local image/video as an ingredient reference.

    The prompt bar has a hidden input[type='file'] reachable via the + button.
    """
    from pathlib import Path as _Path
    if not _Path(file_path).exists():
        print(f"DEBUG upload_media_reference: file not found: {file_path}")
        return False
    fi = page.locator("input[type='file']").first
    if fi.count() == 0:
        print("DEBUG upload_media_reference: no file input found")
        return False
    fi.set_input_files(str(file_path))
    time.sleep(1)
    return True


def open_download_submenu(page: "Page") -> None:
    """Open the download sub-menu for the most recently generated tile.

    Tries the direct "download Download" button first (visible on tiles/detail
    view). Falls back to the more_vert → Download menuitem approach.

    After this call the caller should click the specific quality/format menuitem.
    """
    # Primary: direct download button (confirmed via codegen recording)
    dl_btn = page.get_by_role("button", name="download Download")
    if dl_btn.count() > 0:
        dl_btn.last.click()
        time.sleep(1.5)
        return

    # Fallback: hover newest tile → more_vert → Download menuitem
    first_tile = page.locator("img:not([class*='icon']):not([class*='logo'])").nth(1)
    first_tile.hover()
    time.sleep(1.5)
    page.locator("button:has-text('more_vert')").last.click()
    time.sleep(1.5)
    dl_trigger = page.locator("div[role='menuitem']:has-text('Download')")
    if dl_trigger.count() > 0:
        dl_trigger.first.click()
    else:
        page.locator("text=Download").last.click()
    time.sleep(1.5)


def click_download_quality(page: "Page", quality_label: str) -> None:
    """Click a specific quality menuitem after open_download_submenu().

    Args:
        quality_label: the full menuitem name, e.g. "720p Original Size"
    """
    item = page.get_by_role("menuitem", name=quality_label)
    if item.count() > 0:
        item.first.click()
    else:
        # Fallback: button with has-text
        page.locator(f"button:has-text('{quality_label.split()[0]}')").first.click()


def create_new_project(page: "Page") -> str:
    """Click 'New project', wait for navigation, and return the new project URL.

    Used by google_flow_setup --new-project to create a fresh Flow project.
    The returned URL should be set as DEFAULT_FLOW_URL for subsequent runs.
    """
    page.get_by_role("button", name="add_2 New project").click()
    time.sleep(3)
    return page.url


# Keep old name as alias for backward compatibility
def hover_download_menu(page: "Page") -> None:
    """Deprecated alias for open_download_submenu."""
    open_download_submenu(page)
