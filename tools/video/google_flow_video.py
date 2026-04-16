"""Google Flow video generation via browser automation (Playwright).

Uses Veo models on the Google Flow subscription UI.
- Veo 3.1 Fast: balanced quality and speed
- Veo 3.1 Lite: lighter, faster variant

Uses subscription credits — no per-call API cost.
Falls back to kling_video → higgsfield_video → minimax_video.

For image generation (Nano Banana models), use google_flow_image instead.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.video._google_flow_base import (
    DEFAULT_FLOW_URL,
    FLOW_PROFILE_DIR,
    MAX_INGREDIENTS,
    VIDEO_DOWNLOAD_QUALITY_LABEL,
    apply_camera_motion,
    check_session_valid,
    click_download_quality,
    configure_video_settings,
    hover_download_menu,
    launch_browser_context,
    open_download_submenu,
    open_settings_panel,
    upload_frame,
    upload_media_reference,
    wait_for_generation,
)

_VIDEO_MODELS = {"veo_fast", "veo_lite"}


class GoogleFlowVideo(BaseTool):
    name = "google_flow_video"
    version = "0.5.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "google_flow"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID  # local browser + Google cloud

    install_instructions = (
        "Set GOOGLE_FLOW_EMAIL to your Google account email with Flow access.\n"
        "Install Playwright: pip install playwright && playwright install chromium\n"
        "Note: Google Flow requires a subscription / waitlist access at labs.google/flow"
    )
    agent_skills = ["ai-video-gen", "create-video"]
    fallback_tools = ["kling_video", "higgsfield_video", "minimax_video"]

    capabilities = ["text_to_video", "image_to_video", "extend_video", "camera_motion"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "extend_video": True,
        "camera_motion": True,
        "first_last_frame": True,
        "subscription_credits": True,
        "google_veo_backend": True,
        "offline": False,
    }
    best_for = [
        "experimental Google Veo-quality video via subscription (no per-call API cost)",
        "cinematic and photorealistic AI-generated video",
        "fast turnaround AI video (veo_fast)",
        "camera motion control (dolly, orbit)",
        "extending/continuing existing video clips",
    ]
    not_good_for = [
        "users without Google Flow subscription/access",
        "headless server environments",
        "deterministic batch workflows",
        "image generation (use google_flow_image for Nano Banana models)",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Video generation prompt",
            },
            "model": {
                "type": "string",
                "enum": ["veo_fast", "veo_lite"],
                "default": "veo_fast",
                "description": "veo_fast: balanced quality/speed. veo_lite: lighter, faster.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16"],
                "default": "16:9",
                "description": "Output video aspect ratio. Only 16:9 and 9:16 are supported.",
            },
            "quantity": {
                "type": "string",
                "enum": ["x1", "x2", "x3", "x4"],
                "default": "x1",
                "description": "Number of video clips to generate in one batch. x1=1 clip, x4=4 clips. All are downloaded and returned as artifacts.",
            },
            "first_frame": {
                "type": "string",
                "description": "Local path to an image to use as the first/start frame.",
            },
            "last_frame": {
                "type": "string",
                "description": "Local path to an image to use as the last/end frame.",
            },
            "ingredients": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": (
                    "Local image/video file paths to upload as reference material via the + button. "
                    "Attached as visual context to the prompt."
                ),
            },
            "camera_motion": {
                "type": "string",
                "enum": ["none", "dolly_in", "dolly_out", "orbit_left", "orbit_up", "dolly_out_zoom"],
                "default": "none",
                "description": (
                    "Camera motion preset applied to the generated clip. "
                    "dolly_in: push toward subject. dolly_out: pull back. "
                    "orbit_left/up: arc around subject. dolly_out_zoom: zoom while pulling."
                ),
            },
            "continue_prompt": {
                "type": "string",
                "description": (
                    "If set, extend the most recent video clip with this prompt "
                    "(uses the 'What happens next?' continuation feature). "
                    "The main 'prompt' field is used for the initial generation."
                ),
            },
            "output_path": {
                "type": "string",
                "description": "Output .mp4 file path. Defaults to google_flow_output.mp4.",
            },
            "project_url": {
                "type": "string",
                "description": "Full URL to your Flow project. Overrides default.",
            },
            "download_quality": {
                "type": "string",
                "enum": ["270p", "720p", "1080p", "4k"],
                "default": "720p",
                "description": (
                    "270p=Animated GIF, 720p=Original Size (default, no upscaling), "
                    "1080p=Upscaled, 4k=4K Upscaled Upgrade."
                ),
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["session_expired", "timeout"])
    idempotency_key_fields = ["prompt", "aspect_ratio", "model", "quantity"]
    side_effects = [
        "launches Playwright browser",
        "authenticates with Google account",
        "submits video generation job using Flow subscription",
        "writes MP4 file to output_path",
    ]
    user_visible_verification = [
        "Review generated video for visual quality and prompt adherence",
    ]

    def _has_playwright(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    def _has_credentials(self) -> bool:
        return bool(os.environ.get("GOOGLE_FLOW_EMAIL"))

    def get_status(self) -> ToolStatus:
        if self._has_playwright() and self._has_credentials():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 180.0  # ~3 minutes typical

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

        if not FLOW_PROFILE_DIR.exists():
            return ToolResult(
                success=False,
                error=(
                    f"No saved Google Flow profile at {FLOW_PROFILE_DIR}. "
                    "Run the one-time setup:\n"
                    "  python3 -m tools.video.google_flow_setup"
                ),
            )

        # --- Input validation (before opening browser) ---
        first_frame = inputs.get("first_frame")
        last_frame = inputs.get("last_frame")
        ingredients = inputs.get("ingredients", [])

        if (first_frame or last_frame) and ingredients:
            return ToolResult(
                success=False,
                error=(
                    "Use either first_frame/last_frame OR ingredients — not both. "
                    "Frames fix the visual start/end of the clip; "
                    "ingredients provide style/subject references."
                ),
            )
        if len(ingredients) > MAX_INGREDIENTS:
            return ToolResult(
                success=False,
                error=f"Maximum {MAX_INGREDIENTS} ingredients allowed by the Flow UI.",
            )

        start = time.time()
        prompt = inputs["prompt"]
        model = inputs.get("model", "veo_fast")
        aspect_ratio = inputs.get("aspect_ratio", "16:9")
        quantity = inputs.get("quantity", "x1")
        quantity_count = int(quantity[1])  # "x3" -> 3
        camera_motion = inputs.get("camera_motion", "none")
        continue_prompt = inputs.get("continue_prompt")
        flow_url = inputs.get("project_url") or DEFAULT_FLOW_URL
        dl_quality = inputs.get("download_quality", "720p")

        raw_output = inputs.get("output_path", "google_flow_output.mp4")
        output_path = Path(raw_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        downloaded: list[str] = []

        try:
            with sync_playwright() as pw:
                context = launch_browser_context(pw)
                page = context.new_page()
                page.set_viewport_size({"width": 1440, "height": 900})
                page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
                page.goto(flow_url, wait_until="domcontentloaded", timeout=150000)
                time.sleep(3)

                # Detect stale/expired session (redirected to Google login)
                current_url = page.url
                page_title = page.title()
                if (
                    "accounts.google.com" in current_url
                    or "login" in current_url
                    or "Sign in" in page_title
                ):
                    context.close()
                    raise RuntimeError(
                        "Google Flow session expired. Re-run google_flow_setup.py to refresh your session."
                    )

                if not check_session_valid(page):
                    context.close()
                    return ToolResult(
                        success=False,
                        error=(
                            "Google Flow session expired. Re-run:\n"
                            "  python3 -m tools.video.google_flow_setup"
                        ),
                    )

                # Configure model, aspect ratio, and quantity
                if open_settings_panel(page):
                    configure_video_settings(page, model, aspect_ratio, quantity)
                    page.keyboard.press("Escape")
                    time.sleep(0.5)

                # Enter prompt
                prompt_input = page.locator("div[contenteditable='true']").first
                prompt_input.wait_for(timeout=15000)
                prompt_input.click()
                page.keyboard.press("Control+a")
                page.keyboard.type(prompt)

                # Upload first/last frames
                if first_frame:
                    upload_frame(page, "Start", first_frame)
                if last_frame:
                    upload_frame(page, "End", last_frame)

                # Upload ingredient references
                for ingredient_path in ingredients:
                    upload_media_reference(page, ingredient_path)

                # Submit generation
                generate_btn = page.get_by_role("button", name="arrow_forward Create")
                if generate_btn.count() == 0:
                    generate_btn = page.locator("button:has-text('arrow_forward')")
                generate_btn.first.click()

                # Wait for tile to appear
                tiles_before = page.locator(
                    "img:not([class*='icon']):not([class*='logo'])"
                ).count()
                success = wait_for_generation(page, tiles_before, is_image=False)
                if not success:
                    context.close()
                    return ToolResult(
                        success=False,
                        error="Google Flow video generation failed or timed out",
                    )

                # Continue/extend the clip if requested
                if continue_prompt:
                    cont_btn = page.get_by_role("button", name="keyboard_double_arrow_right")
                    if cont_btn.count() > 0:
                        cont_btn.last.click()
                        time.sleep(2)
                        next_box = page.get_by_role("textbox").filter(has_text="What happens next?")
                        if next_box.count() > 0:
                            next_box.first.fill(continue_prompt)
                            page.get_by_role("button", name="arrow_forward Create").first.click()
                            tiles_before2 = page.locator(
                                "img:not([class*='icon']):not([class*='logo'])"
                            ).count()
                            wait_for_generation(page, tiles_before2, is_image=False)

                # Apply camera motion if requested
                if camera_motion and camera_motion != "none":
                    apply_camera_motion(page, camera_motion)

                # Download all generated clips
                import shutil as _shutil
                quality_label = VIDEO_DOWNLOAD_QUALITY_LABEL.get(dl_quality, "720p Original Size")
                for i in range(quantity_count):
                    if quantity_count == 1:
                        out = output_path
                    else:
                        out = output_path.parent / f"{output_path.stem}_{i + 1}{output_path.suffix}"
                    open_download_submenu(page)
                    with page.expect_download(timeout=60000) as dl_info:
                        click_download_quality(page, quality_label)
                    _shutil.move(str(dl_info.value.path()), str(out))
                    downloaded.append(str(out))

                context.close()

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Google Flow video automation failed: {exc}",
            )

        if not downloaded:
            return ToolResult(
                success=False,
                error="Google Flow completed but no video files were saved",
            )

        primary = downloaded[0]
        return ToolResult(
            success=True,
            data={
                "provider": "google_flow",
                "model": model,
                "output_type": "video",
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "quantity": quantity,
                "camera_motion": camera_motion,
                "continue_prompt": continue_prompt,
                "first_frame": first_frame,
                "last_frame": last_frame,
                "ingredients": ingredients,
                "download_quality": dl_quality,
                "output": primary,
                "output_path": primary,
                "all_outputs": downloaded,
                "format": "mp4",
                "credits_source": "subscription",
            },
            artifacts=downloaded,
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
