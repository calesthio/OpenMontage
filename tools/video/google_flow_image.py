"""Google Flow image generation via browser automation (Playwright).

Uses Nano Banana models on the Google Flow subscription UI.
- Nano Banana Pro: best for text-in-image, posters, CTAs, typography
- Nano Banana 2:   general high-quality image generation

Uses subscription credits — no per-call API cost.
Falls back to flux_image tools if browser automation fails.
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
    IMAGE_DOWNLOAD_LABEL,
    MAX_INGREDIENTS,
    check_session_valid,
    click_download_quality,
    configure_image_settings,
    hover_download_menu,
    launch_browser_context,
    open_download_submenu,
    open_settings_panel,
    upload_media_reference,
    wait_for_generation,
)

_IMAGE_MODELS = {"nano_banana", "nano_banana_pro"}


class GoogleFlowImage(BaseTool):
    name = "google_flow_image"
    version = "1.2.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
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
    agent_skills = ["flux-best-practices", "bfl-api"]
    fallback_tools = ["flux_image", "imagen_image", "dalle_image"]

    capabilities = ["text_to_image", "poster_generation", "cta_image"]
    supports = {
        "text_to_image": True,
        "text_in_image": True,
        "poster_generation": True,
        "subscription_credits": True,
        "offline": False,
    }
    best_for = [
        "text-in-image, posters, and CTAs (nano_banana_pro)",
        "high-quality general images (nano_banana)",
        "subscription-based generation with no per-call API cost",
        "photorealistic scenes via Nano Banana models",
    ]
    not_good_for = [
        "users without Google Flow subscription/access",
        "headless server environments",
        "deterministic batch workflows",
        "video generation (use google_flow_video instead)",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Image generation prompt",
            },
            "model": {
                "type": "string",
                "enum": ["nano_banana_pro", "nano_banana", "imagen_4"],
                "default": "nano_banana_pro",
                "description": (
                    "nano_banana_pro: excels at text in images, posters, CTAs. "
                    "nano_banana: general high-quality image generation. "
                    "imagen_4: Google Imagen 4 model."
                ),
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4"],
                "default": "1:1",
                "description": "Output image aspect ratio.",
            },
            "ingredients": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": (
                    "Local image/video file paths to upload as reference material via the + button. "
                    "These are attached to the prompt as visual context (not style preset cards)."
                ),
            },
            "quantity": {
                "type": "string",
                "enum": ["x1", "x2", "x3", "x4"],
                "default": "x1",
                "description": "Number of images to generate in one batch. x1=1 (default), x4=4. Extra images don't consume additional subscription credits. All are downloaded and returned as artifacts.",
            },
            "output_path": {
                "type": "string",
                "description": "Output file path. Defaults to google_flow_image.png. Extension auto-set to .png.",
            },
            "project_url": {
                "type": "string",
                "description": "Full URL to your Flow project. Overrides default.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=200, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["session_expired", "timeout"])
    idempotency_key_fields = ["prompt", "aspect_ratio", "model"]
    side_effects = [
        "launches Playwright browser",
        "authenticates with Google account",
        "submits image generation job using Flow subscription",
        "writes PNG file to output_path",
    ]
    user_visible_verification = [
        "Review generated image for visual quality, prompt adherence, and text accuracy",
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
        return 60.0  # ~1 min for image generation

    def _resolve_output_path(self, inputs: dict[str, Any]) -> Path:
        raw = inputs.get("output_path")
        if raw:
            p = Path(raw)
            return p.with_suffix(".png") if not p.suffix else p
        return Path("google_flow_image.png")

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

        # --- Input validation ---
        ingredients = inputs.get("ingredients", [])
        if len(ingredients) > MAX_INGREDIENTS:
            return ToolResult(
                success=False,
                error=f"Maximum {MAX_INGREDIENTS} ingredients allowed by the Flow UI.",
            )

        start = time.time()
        prompt = inputs["prompt"]
        model = inputs.get("model", "nano_banana_pro")
        aspect_ratio = inputs.get("aspect_ratio", "1:1")
        quantity = inputs.get("quantity", "x1")
        quantity_count = int(quantity[1])  # "x2" -> 2
        flow_url = inputs.get("project_url") or DEFAULT_FLOW_URL

        base_output = self._resolve_output_path(inputs)
        base_output.parent.mkdir(parents=True, exist_ok=True)

        downloaded: list[str] = []

        try:
            with sync_playwright() as pw:
                context = launch_browser_context(pw)
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
                        error=(
                            "Google Flow session expired. Re-run:\n"
                            "  python3 -m tools.video.google_flow_setup"
                        ),
                    )

                # Configure model, aspect ratio, and quantity
                if open_settings_panel(page):
                    configure_image_settings(page, model, aspect_ratio, quantity)
                    page.keyboard.press("Escape")
                    time.sleep(0.5)

                # Enter prompt
                prompt_input = page.locator("div[contenteditable='true']").first
                prompt_input.wait_for(timeout=15000)
                prompt_input.click()
                page.keyboard.press("Control+a")
                page.keyboard.type(final_prompt)

                # Upload reference media via hidden file input
                for ingredient_path in ingredients:
                    upload_media_reference(page, ingredient_path)

                # Submit
                generate_btn = page.locator("button:has-text('arrow_forward')")
                generate_btn.first.click()

                # Wait for generation
                tiles_before = page.locator(
                    "img:not([class*='icon']):not([class*='logo'])"
                ).count()
                success = wait_for_generation(page, tiles_before, is_image=True)
                if not success:
                    context.close()
                    return ToolResult(
                        success=False,
                        error="Google Flow image generation failed or timed out",
                    )

                # Download all generated images
                import shutil as _shutil
                for i in range(quantity_count):
                    if quantity_count == 1:
                        out = base_output
                    else:
                        out = base_output.parent / f"{base_output.stem}_{i + 1}{base_output.suffix}"
                    open_download_submenu(page)
                    with page.expect_download(timeout=60000) as dl_info:
                        click_download_quality(page, IMAGE_DOWNLOAD_LABEL)
                    _shutil.move(str(dl_info.value.path()), str(out))
                    downloaded.append(str(out))

                context.close()

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Google Flow image automation failed: {exc}",
            )

        if not downloaded:
            return ToolResult(
                success=False,
                error="Google Flow completed but no image files were saved",
            )

        primary = downloaded[0]
        return ToolResult(
            success=True,
            data={
                "provider": "google_flow",
                "model": model,
                "output_type": "image",
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "quantity": quantity,
                "ingredients": ingredients,
                "output": primary,
                "output_path": primary,
                "all_outputs": downloaded,
                "format": "png",
                "credits_source": "subscription",
            },
            artifacts=downloaded,
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
