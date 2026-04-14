"""HeyGen subscription video generation via browser automation (Playwright).

Uses the HeyGen web UI with your subscription account — burns subscription
credits instead of API credits. This is the preferred path when API credits
are limited or when using avatar/talking-head features included in your plan.

Falls back to heygen_video (API) if browser automation fails.
"""

from __future__ import annotations

import json
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

# Persistent session cookie store — shared across calls
_SESSION_DIR = Path.home() / ".openmontage"
_HEYGEN_SESSION_FILE = _SESSION_DIR / "heygen_session.json"


class HeyGenBrowserVideo(BaseTool):
    name = "heygen_browser_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "heygen_browser"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID  # local browser + remote HeyGen

    install_instructions = (
        "Set HEYGEN_EMAIL and HEYGEN_PASSWORD to your HeyGen account credentials.\n"
        "Install Playwright: pip install playwright && playwright install chromium"
    )
    agent_skills = ["ai-video-gen", "create-video"]
    fallback_tools = ["heygen_video"]

    capabilities = ["text_to_video", "avatar_video", "talking_head"]
    supports = {
        "text_to_video": True,
        "avatar_video": True,
        "talking_head": True,
        "subscription_credits": True,
        "offline": False,
    }
    best_for = [
        "avatar and talking-head video using subscription credits",
        "HeyGen features included in plan (not billed per API call)",
        "presenter-led spokesperson videos",
    ]
    not_good_for = [
        "headless/server environments without display",
        "high-volume automated batch generation",
        "when HEYGEN_EMAIL/HEYGEN_PASSWORD are not available",
    ]

    input_schema = {
        "type": "object",
        "required": ["script"],
        "properties": {
            "script": {"type": "string", "description": "Narration or dialogue script"},
            "avatar_id": {
                "type": "string",
                "description": "HeyGen avatar ID (leave empty to use default)",
            },
            "voice": {
                "type": "string",
                "description": "Voice name or ID",
                "default": "default",
            },
            "language": {"type": "string", "default": "en"},
            "tone": {
                "type": "string",
                "enum": ["professional", "casual", "friendly", "authoritative"],
                "default": "professional",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["session_expired", "timeout"])
    idempotency_key_fields = ["script", "avatar_id", "voice", "language"]
    side_effects = [
        "launches Playwright browser",
        "authenticates with HeyGen web UI",
        "submits video render job using subscription credits",
        "writes video file to output_path",
    ]
    user_visible_verification = ["Review avatar lip sync and audio quality"]

    def _has_playwright(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    def _has_credentials(self) -> bool:
        return bool(os.environ.get("HEYGEN_EMAIL") and os.environ.get("HEYGEN_PASSWORD"))

    def get_status(self) -> ToolStatus:
        if self._has_playwright() and self._has_credentials():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # subscription credits, not direct API cost

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # ~2–4 minutes typical for a short avatar video
        words = len(inputs.get("script", "").split())
        speaking_seconds = words / 2.5  # ~2.5 words/second
        return max(120.0, speaking_seconds * 20)

    def _load_session(self) -> list[dict] | None:
        """Load persisted browser cookies, return None if missing/expired."""
        if not _HEYGEN_SESSION_FILE.exists():
            return None
        try:
            data = json.loads(_HEYGEN_SESSION_FILE.read_text())
            cookies = data.get("cookies", [])
            # Basic expiry check — any cookie expired?
            now = time.time()
            for c in cookies:
                if c.get("expires", 0) > 0 and c["expires"] < now:
                    return None
            return cookies if cookies else None
        except Exception:
            return None

    def _save_session(self, cookies: list[dict]) -> None:
        """Persist browser cookies for reuse."""
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        _HEYGEN_SESSION_FILE.write_text(json.dumps({"cookies": cookies}, indent=2))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not self._has_playwright():
            return ToolResult(
                success=False,
                error=(
                    "Playwright not installed. "
                    "Run: pip install playwright && playwright install chromium"
                ),
            )
        if not self._has_credentials():
            return ToolResult(
                success=False,
                error="HEYGEN_EMAIL and HEYGEN_PASSWORD must be set. " + self.install_instructions,
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ToolResult(
                success=False,
                error="playwright package not importable. Run: pip install playwright",
            )

        start = time.time()
        email = os.environ["HEYGEN_EMAIL"]
        password = os.environ["HEYGEN_PASSWORD"]
        script = inputs["script"]
        output_path = Path(inputs.get("output_path", "heygen_browser_output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context()

                # Restore session if available
                saved_cookies = self._load_session()
                if saved_cookies:
                    context.add_cookies(saved_cookies)

                page = context.new_page()

                # Check if session is still valid
                page.goto("https://app.heygen.com/home", wait_until="networkidle", timeout=30000)
                is_logged_in = "app.heygen.com/home" in page.url and page.locator("[data-testid='user-menu']").count() > 0

                if not is_logged_in:
                    # Log in
                    page.goto("https://app.heygen.com/login", wait_until="networkidle", timeout=30000)
                    page.fill("input[type='email'], input[name='email']", email)
                    page.fill("input[type='password'], input[name='password']", password)
                    page.click("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')")
                    page.wait_for_url("**/home", timeout=30000)

                    # Save session cookies
                    self._save_session(context.cookies())

                # Navigate to AI Avatar Studio or Video creation
                page.goto("https://app.heygen.com/create", wait_until="networkidle", timeout=30000)

                # Fill in script — HeyGen's create page has a script/text area
                script_selector = "textarea[placeholder*='script'], textarea[placeholder*='Script'], [data-testid='script-input']"
                page.wait_for_selector(script_selector, timeout=15000)
                page.fill(script_selector, script)

                # Select avatar if provided
                avatar_id = inputs.get("avatar_id")
                if avatar_id:
                    avatar_btn = page.locator(f"[data-avatar-id='{avatar_id}']")
                    if avatar_btn.count() > 0:
                        avatar_btn.click()

                # Submit for rendering
                submit_btn = page.locator("button:has-text('Generate'), button:has-text('Submit'), button:has-text('Create Video')")
                submit_btn.first.click()

                # Wait for redirect to video status or job page
                page.wait_for_url("**/video/**", timeout=30000)
                video_page_url = page.url
                video_id = video_page_url.rstrip("/").split("/")[-1]

                # Poll until the video status shows download available
                max_poll = 600  # 10 minutes
                poll_start = time.time()
                download_url = None

                while time.time() - poll_start < max_poll:
                    time.sleep(10)
                    page.reload(wait_until="networkidle")

                    # Look for download button or status indicator
                    done = page.locator("[data-testid='download-btn'], a[href*='.mp4'], button:has-text('Download')").count() > 0
                    failed = page.locator("[data-testid='status-failed'], :has-text('Generation failed')").count() > 0

                    if failed:
                        return ToolResult(
                            success=False,
                            error="HeyGen video generation failed (reported by web UI)",
                        )
                    if done:
                        # Extract download URL
                        dl_elem = page.locator("a[href*='.mp4'], a[download]").first
                        if dl_elem.count() > 0:
                            download_url = dl_elem.get_attribute("href")
                        break

                if not download_url:
                    return ToolResult(
                        success=False,
                        error=f"HeyGen video {video_id} did not produce a download URL within {max_poll}s",
                    )

                # Download the video
                import requests as req_lib
                video_resp = req_lib.get(download_url, timeout=120)
                video_resp.raise_for_status()
                output_path.write_bytes(video_resp.content)

                browser.close()

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"HeyGen browser automation failed: {exc}",
            )

        return ToolResult(
            success=True,
            data={
                "provider": "heygen_browser",
                "video_id": video_id,
                "script_length_words": len(script.split()),
                "avatar_id": inputs.get("avatar_id", "default"),
                "voice": inputs.get("voice", "default"),
                "language": inputs.get("language", "en"),
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                "credits_source": "subscription",
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model="heygen_browser_subscription",
        )
