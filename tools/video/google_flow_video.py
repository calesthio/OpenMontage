"""Experimental Google Flow video provider via a local browser session."""

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
from tools.video.google_flow_browser_bridge import (
    DEFAULT_PROFILE_DIR,
    GoogleFlowBridgeError,
    GoogleFlowBrowserBridge,
    redact_payload,
    redact_text,
)


def _env_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _truthy_input(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "confirmed"}


class GoogleFlowVideo(BaseTool):
    name = "google_flow_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "google_flow"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    dependencies = ["python:playwright"]
    install_instructions = (
        "Experimental local browser bridge. Install optional browser deps with "
        "`pip install -r requirements-browser.txt` and `python -m playwright install chromium`, "
        "then set GOOGLE_FLOW_ENABLED=true and OPENMONTAGE_EXPERIMENTAL_GOOGLE_FLOW=1."
    )
    agent_skills = ["ai-video-gen", "playwright-recording"]

    capabilities = ["text_to_video", "image_to_video", "check_auth", "open_login", "browser_session"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "local_image_upload": True,
        "check_auth": True,
        "open_login": True,
        "browser_session": True,
        "uses_subscription_credits": True,
        "requires_explicit_preference": True,
        "requires_browser_automation_confirmation": True,
        "private_api": False,
        "stores_browser_session": True,
        "stores_cookies_in_browser_profile": True,
        "stores_storage_state_in_browser_profile": True,
        "stores_repo_auth_artifacts": False,
        "stores_har": False,
        "stores_screenshots": False,
        "dedicated_profile_default": True,
        "cdp_url_localhost_only": True,
    }
    best_for = [
        "local-only use of a logged-in Google Flow UI session",
        "spending Google AI Pro or Flow web credits when the user explicitly opts in",
        "experimental video generation workflows where official API coverage is unavailable",
    ]
    not_good_for = [
        "unattended production runs",
        "auto-selected provider routing",
        "bypassing CAPTCHA, rate limits, or account protections",
    ]
    fallback_tools = ["veo_video", "runway_video", "seedance_video", "kling_video"]
    quality_score = 0.65
    historical_success_rate = 0.45
    latency_p50_seconds = 180.0

    input_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "check_auth", "open_login"],
                "default": "text_to_video",
            },
            "preferred_provider": {
                "type": "string",
                "description": "Must be google_flow for generation operations.",
            },
            "confirm_browser_automation": {
                "type": "boolean",
                "description": "Must be true for generation operations.",
                "default": False,
            },
            "reference_image_path": {"type": "string"},
            "image_path": {"type": "string"},
            "reference_image_paths": {"type": "array", "items": {"type": "string"}},
            "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"], "default": "16:9"},
            "duration": {"type": "string"},
            "model_variant": {"type": "string", "default": "flow"},
            "output_path": {"type": "string"},
            "keep_open": {
                "type": "boolean",
                "description": "For open_login only. Leave the browser session open for manual sign-in.",
                "default": True,
            },
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "output_path": {"type": "string"},
            "provider": {"type": "string"},
            "operation": {"type": "string"},
            "auth_mode": {"type": "string"},
            "experimental_surface": {"type": "boolean"},
        },
    }
    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=2048, vram_mb=0, disk_mb=2048, network_required=True)
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["prompt", "operation", "aspect_ratio", "duration"]
    side_effects = [
        "opens a local browser profile",
        "submits prompts through the Google Flow UI",
        "uses credits from the logged-in Google account",
        "writes downloaded video to output_path",
    ]
    user_visible_verification = [
        "Run check_auth before generation",
        "Watch the downloaded clip for motion quality and watermarks",
        "Confirm the browser session is the intended Google account before spending Flow credits",
    ]

    @staticmethod
    def _playwright_available() -> bool:
        try:
            import playwright.sync_api  # noqa: F401
        except ImportError:
            return False
        return True

    @staticmethod
    def _playwright_chromium_available() -> bool:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                return Path(playwright.chromium.executable_path).exists()
        except Exception:
            return False

    @staticmethod
    def _opt_in_enabled() -> bool:
        return _env_true("GOOGLE_FLOW_ENABLED") and os.environ.get("OPENMONTAGE_EXPERIMENTAL_GOOGLE_FLOW") == "1"

    def get_status(self) -> ToolStatus:
        if not self._opt_in_enabled():
            return ToolStatus.UNAVAILABLE
        if not self._playwright_available():
            return ToolStatus.UNAVAILABLE
        if not self._playwright_chromium_available():
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Flow consumes account/subscription credits in the browser UI, not an
        # OpenMontage-metered API bill. Surface as metadata, not USD.
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        operation = inputs.get("operation", "text_to_video")
        if operation in {"check_auth", "open_login"}:
            return 10.0
        return 240.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool": self.name,
            "status": self.get_status().value,
            "playwright_available": self._playwright_available(),
            "chromium_available": self._playwright_chromium_available(),
            "would_execute": bool(
                self.get_status() == ToolStatus.AVAILABLE
                and inputs.get("preferred_provider") == "google_flow"
                and _truthy_input(inputs.get("confirm_browser_automation"))
            ),
            "estimated_cost_usd": 0.0,
            "credits_source": "google_ai_pro_or_flow_web_credits",
            "experimental_surface": True,
            "requires_explicit_preference": True,
            "requires_browser_automation_confirmation": True,
        }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        operation = str(inputs.get("operation", "text_to_video"))
        profile_dir = inputs.get("profile_dir") or os.environ.get("GOOGLE_FLOW_BROWSER_PROFILE_DIR") or DEFAULT_PROFILE_DIR

        if not self._opt_in_enabled():
            return ToolResult(
                success=False,
                error=(
                    "Google Flow bridge is disabled. Set GOOGLE_FLOW_ENABLED=true and "
                    "OPENMONTAGE_EXPERIMENTAL_GOOGLE_FLOW=1 to opt in."
                ),
            )

        if not self._playwright_available():
            return ToolResult(
                success=False,
                error="Playwright is not installed. " + self.install_instructions,
            )
        if not self._playwright_chromium_available():
            return ToolResult(
                success=False,
                error="Playwright Chromium is not installed. Run `python -m playwright install chromium`.",
            )

        bridge = None
        close_bridge = True
        try:
            bridge = GoogleFlowBrowserBridge(profile_dir=profile_dir)
            if operation == "open_login":
                keep_open = _truthy_input(inputs.get("keep_open", True))
                close_bridge = not keep_open
                data = bridge.open_login(keep_open=keep_open)
                return ToolResult(
                    success=True,
                    data=self._public_metadata(data, operation=operation),
                    duration_seconds=round(time.time() - start, 2),
                )

            if operation == "check_auth":
                data = bridge.check_auth()
                return ToolResult(
                    success=True,
                    data=self._public_metadata(data, operation=operation),
                    duration_seconds=round(time.time() - start, 2),
                )

            validation_error = self._validate_generation_inputs(inputs)
            if validation_error:
                return ToolResult(success=False, error=validation_error)

            prompt = str(inputs.get("prompt") or "")
            output_path = Path(str(inputs.get("output_path") or "google_flow_output.mp4")).expanduser()
            image_paths = self._image_paths(inputs)
            model_variant = str(inputs.get("model_variant") or "flow")
            data = bridge.generate_video(
                prompt=prompt,
                operation=operation,
                image_paths=image_paths,
                aspect_ratio=inputs.get("aspect_ratio"),
                duration=inputs.get("duration"),
                model_variant=model_variant,
                output_path=output_path,
            )
            public = self._public_metadata(
                {
                    "provider": "google_flow",
                    "model": f"google-flow/{model_variant}",
                    "prompt": prompt,
                    "operation": operation,
                    "output": str(output_path),
                    "output_path": str(output_path),
                    "format": "mp4",
                    "auth_mode": "browser_session",
                    "credits_source": "google_ai_pro_or_flow_web_credits",
                    "consumes_subscription_credits": True,
                    "experimental_surface": True,
                    "browser_automation_confirmed": True,
                    **data,
                },
                operation=operation,
            )
            artifact = public.get("output_path")
            return ToolResult(
                success=True,
                data=public,
                artifacts=[artifact] if isinstance(artifact, str) else [],
                cost_usd=0.0,
                duration_seconds=round(time.time() - start, 2),
                model=public.get("model"),
            )
        except GoogleFlowBridgeError as exc:
            return ToolResult(
                success=False,
                error=(
                    f"Google Flow browser bridge failed ({exc.code}): "
                    f"{exc.public_message(profile_dir=profile_dir)}"
                ),
                data={
                    "provider": "google_flow",
                    "error_code": exc.code,
                    "retryable": exc.retryable,
                    "details": exc.public_details(profile_dir=profile_dir),
                },
                duration_seconds=round(time.time() - start, 2),
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Google Flow browser bridge failed: {redact_text(exc, profile_dir=profile_dir)}",
                data={"provider": "google_flow", "error_code": "unexpected"},
                duration_seconds=round(time.time() - start, 2),
            )
        finally:
            if close_bridge and bridge is not None:
                bridge.close()

    def _validate_generation_inputs(self, inputs: dict[str, Any]) -> str | None:
        if inputs.get("preferred_provider") != "google_flow":
            return (
                "Google Flow requires explicit provider preference. "
                "Set preferred_provider='google_flow'."
            )
        if not _truthy_input(inputs.get("confirm_browser_automation")):
            return (
                "Google Flow requires explicit browser automation confirmation. "
                "Set confirm_browser_automation=true."
            )
        operation = str(inputs.get("operation", "text_to_video"))
        if operation not in {"text_to_video", "image_to_video"}:
            return f"Unsupported Google Flow operation: {operation}"
        if not str(inputs.get("prompt") or "").strip():
            return "Google Flow generation requires a prompt."
        if operation == "image_to_video" and not self._image_paths(inputs):
            return "image_to_video requires image_path, reference_image_path, or reference_image_paths."
        return None

    @staticmethod
    def _image_paths(inputs: dict[str, Any]) -> list[Path]:
        paths: list[Path] = []
        for key in ("image_path", "reference_image_path"):
            if inputs.get(key):
                paths.append(Path(str(inputs[key])).expanduser())
        for value in inputs.get("reference_image_paths") or []:
            paths.append(Path(str(value)).expanduser())
        return paths

    @staticmethod
    def _public_metadata(data: dict[str, Any], *, operation: str) -> dict[str, Any]:
        merged = {
            "provider": "google_flow",
            "operation": operation,
            "auth_mode": "browser_session",
            "experimental_surface": True,
            **data,
        }
        return redact_payload(merged)
