"""Clipia multi-model video generation via the Clipia public API.

Clipia (https://clipia.ai) is a generation aggregator: one API key covers
50+ hosted image and video models — Kling, Veo, Seedance, Wan, Sora and
more — behind a single fal.ai-shaped queue API (submit -> status -> result).
Model slugs are discovered dynamically via GET /v1/models, so new models
become usable without code changes here.

Notable for RU/CIS users: Clipia bills in rubles and accepts Russian bank
cards (USD/EUR plans exist too), which makes it a practical route to premium
video models in regions where most Western providers cannot be paid for
directly.

Keys with the ``clipia_test_`` prefix run in sandbox mode: submit returns a
deterministic mock COMPLETED result instantly and no credits are spent —
useful for integration testing. See docs/PROVIDERS.md and the ``clipia``
agent skill for the full API contract.
"""

from __future__ import annotations

import os
import time
import uuid
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

_API_BASE = "https://api.clipia.ai"
_DEFAULT_T2V_MODEL = "seedance-2-fast-t2v"
_DEFAULT_I2V_MODEL = "seedance-2-fast-i2v"

_POLL_INTERVAL_SECONDS = 5.0
_POLL_TIMEOUT_SECONDS = 900.0  # 15 min — long clips on premium models can take a while

# Clipia bills in credits (fixed price per operation, known at submit time).
# 1 credit ≈ $0.04 derived from public plan pricing ($0.04–0.06 depending on
# plan); used only to express ToolResult.cost_usd.
_CREDIT_USD = 0.04

# Approximate public credit prices at 720p (clipia.ai pricing matrix,
# 2026-07). Keyed by slug prefix so t2v/i2v variants share an entry.
# The authoritative price for an exact parameter set is
# POST /v1/models/{slug}/estimate (returns credits without queueing) —
# not called here because estimate_cost() must stay fast and offline.
_CREDITS_PER_SECOND_720P = {
    "seedance-2-fast": 9.4,  # 47 credits / 5 s (480p is ~5.6/s)
    "kling-3": 7.2,          # 36 credits / 5 s
    "wan-2-7": 4.8,          # 24 credits / 5 s
}
_FLAT_CREDITS_PER_CLIP = {
    "sora-2-pro": 28.0,
    "sora-2": 17.0,
}
_DEFAULT_CREDITS_PER_SECOND = 9.4

_TERMINAL_STATUSES = ("COMPLETED", "FAILED", "CANCELED")  # note: single L


class ClipiaVideo(BaseTool):
    name = "clipia_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "clipia"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically via env var
    install_instructions = (
        "Set CLIPIA_API_KEY to your Clipia API key.\n"
        "  Get one at https://clipia.ai/ru/developer (Developer console -> API keys).\n"
        "  A key with the clipia_test_ prefix runs in sandbox mode: instant mock\n"
        "  results, no credits spent — handy for testing this integration."
    )
    agent_skills = ["clipia", "ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "model_selection": True,
        "aspect_ratio": True,
        "resolution": True,
        "sandbox_mode": True,
        "multi_model_aggregator": True,
    }
    best_for = [
        "one API key covering 50+ video and image models (Kling, Veo, Seedance, Wan, Sora)",
        "switching video models per shot without opening new provider accounts",
        "RU/CIS users — billing in rubles with Russian bank cards",
        "integration testing via sandbox keys (clipia_test_) with zero credit spend",
    ]
    not_good_for = [
        "offline generation",
        "sub-minute latency demands (queue-based, clips render in 1-10 min)",
    ]
    fallback_tools = ["kling_video", "wan_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "default": _DEFAULT_T2V_MODEL,
                "description": (
                    "Clipia model slug, e.g. seedance-2-fast-t2v, kling-3, wan-2-7, "
                    "sora-2. Full live catalog: GET https://api.clipia.ai/v1/models. "
                    "When omitted: seedance-2-fast-t2v for text_to_video, "
                    "seedance-2-fast-i2v for image_to_video."
                ),
            },
            "duration": {
                "type": "string",
                "default": "5",
                "description": (
                    "Duration in seconds (model-dependent range, typically 4-15). "
                    "'auto' omits the field and lets the model decide, e.g. for "
                    "fixed-length models like sora-2."
                ),
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1"],
                "default": "16:9",
                "description": (
                    "Some models accept more ratios (see GET /v1/models/{slug}); "
                    "these three are safe across the catalog."
                ),
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "1080p"],
                "description": (
                    "Only sent when provided. Supported values vary per model "
                    "(seedance-2-fast: 480p/720p; kling-3, wan-2-7: 720p/1080p)."
                ),
            },
            "image_url": {
                "type": "string",
                "description": "Start-frame image URL, required for image_to_video.",
            },
            "idempotency_key": {
                "type": "string",
                "description": (
                    "Optional UUID v4 sent as the Idempotency-Key header. Resubmitting "
                    "with the same key and params within 24h returns the same request "
                    "instead of generating (and billing) again. Auto-generated per call "
                    "when omitted."
                ),
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "duration", "aspect_ratio"]
    side_effects = ["writes video file to output_path", "calls the Clipia API (api.clipia.ai)"]
    user_visible_verification = [
        "Watch generated clip for motion coherence and visual quality",
        "Sandbox keys return a fixed sample video — do not judge model quality from it",
    ]

    def _get_api_key(self) -> str | None:
        return os.environ.get("CLIPIA_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def _resolve_model(self, inputs: dict[str, Any]) -> str:
        model = inputs.get("model")
        if model:
            return model
        if inputs.get("operation") == "image_to_video":
            return _DEFAULT_I2V_MODEL
        return _DEFAULT_T2V_MODEL

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Approximate cost in USD from a static credit table (offline).

        Figures are 720p list prices as of 2026-07; the exact per-call price
        is available server-side via POST /v1/models/{slug}/estimate.
        """
        model = self._resolve_model(inputs)
        duration = inputs.get("duration", "5")
        secs = 5 if duration == "auto" else int(duration)
        for prefix, credits in _FLAT_CREDITS_PER_CLIP.items():
            if model.startswith(prefix):
                return round(credits * _CREDIT_USD, 2)
        rate = _DEFAULT_CREDITS_PER_SECOND
        for prefix, per_second in _CREDITS_PER_SECOND_720P.items():
            if model.startswith(prefix):
                rate = per_second
                break
        return round(rate * secs * _CREDIT_USD, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 120.0  # 1-10 min typical; sandbox keys return instantly

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="CLIPIA_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        operation = inputs.get("operation", "text_to_video")
        model = self._resolve_model(inputs)

        if operation == "image_to_video" and not inputs.get("image_url"):
            return ToolResult(
                success=False,
                error="image_url is required for operation='image_to_video'",
            )

        payload: dict[str, Any] = {"prompt": inputs["prompt"]}
        duration = inputs.get("duration", "5")
        if duration and duration != "auto":
            payload["duration"] = int(duration)
        if inputs.get("aspect_ratio"):
            payload["aspect_ratio"] = inputs["aspect_ratio"]
        if inputs.get("resolution"):
            payload["resolution"] = inputs["resolution"]
        if operation == "image_to_video":
            payload["image_url"] = inputs["image_url"]

        headers = {
            # "Bearer <key>" and "X-Api-Key: <key>" are accepted too.
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": inputs.get("idempotency_key") or str(uuid.uuid4()),
        }

        try:
            # Submit to the queue API. The response always carries request_id +
            # absolute status/response URLs; `cost` is the fixed price in
            # credits, reserved now and refunded in full on failure.
            submit_resp = requests.post(
                f"{_API_BASE}/v1/models/{model}",
                headers=headers,
                json={"input": payload},
                timeout=60,
            )
            if not submit_resp.ok:
                return ToolResult(
                    success=False,
                    error=f"Clipia submit failed ({_api_error(submit_resp)})",
                )
            queue_data = submit_resp.json()
            request_id = queue_data["request_id"]
            status_url = queue_data["status_url"]
            response_url = queue_data["response_url"]
            cost_credits = queue_data.get("cost")
            status = queue_data.get("status", "IN_QUEUE")

            # Poll until terminal. Sandbox keys (clipia_test_) return
            # status=COMPLETED directly from submit, skipping this loop.
            deadline = start + _POLL_TIMEOUT_SECONDS
            while status not in _TERMINAL_STATUSES:
                if time.time() >= deadline:
                    return ToolResult(
                        success=False,
                        error=(
                            f"Clipia video generation timed out after "
                            f"{int(_POLL_TIMEOUT_SECONDS)}s (request_id={request_id} "
                            "may still complete server-side)"
                        ),
                    )
                time.sleep(_POLL_INTERVAL_SECONDS)
                try:
                    status_resp = requests.get(status_url, headers=headers, timeout=15)
                    status_resp.raise_for_status()
                    status = status_resp.json().get("status", status)
                except requests.RequestException:
                    continue  # transient poll error — bounded by the deadline above

            if status != "COMPLETED":
                # FAILED / CANCELED are terminal; reserved credits are refunded.
                return ToolResult(
                    success=False,
                    error=(
                        f"Clipia video generation {status.lower()}"
                        f"{_result_error_detail(requests, response_url, headers)} "
                        "(reserved credits are refunded)"
                    ),
                )

            # Fetch result (HTTP 200 for terminal statuses, 202 while running).
            result_resp = requests.get(response_url, headers=headers, timeout=30)
            result_resp.raise_for_status()
            result = result_resp.json()
            cost_credits = result.get("cost", cost_credits)

            video = (result.get("output") or {}).get("video") or {}
            # `url` is a display-optimized rendition; `original_url` is the
            # full-quality file when available — prefer it for downloads.
            video_url = video.get("original_url") or video.get("url")
            if not video_url:
                return ToolResult(
                    success=False,
                    error=f"Clipia result for {request_id} is missing video output",
                )

            video_response = requests.get(video_url, timeout=180)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "clipia_video_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as e:
            return ToolResult(success=False, error=f"Clipia video generation failed: {e}")

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        cost_usd = (
            round(cost_credits * _CREDIT_USD, 2)
            if isinstance(cost_credits, (int, float))
            else self.estimate_cost(inputs)
        )
        return ToolResult(
            success=True,
            data={
                "provider": "clipia",
                "model": model,
                "prompt": inputs["prompt"],
                "operation": operation,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "resolution": inputs.get("resolution"),
                "request_id": request_id,
                "cost_credits": cost_credits,
                "sandbox": api_key.startswith("clipia_test_"),
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=cost_usd,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )


def _api_error(resp: Any) -> str:
    """Extract Clipia's sanitized error envelope: {"error": {code, message}}."""
    try:
        err = resp.json().get("error", {})
        code = err.get("code") or f"http_{resp.status_code}"
        message = err.get("message", "")
        return f"{code}: {message}".rstrip(": ")
    except Exception:
        return f"HTTP {resp.status_code}"


def _result_error_detail(requests_mod: Any, response_url: str, headers: dict[str, str]) -> str:
    """Best-effort fetch of error {code, message} from a FAILED result."""
    try:
        resp = requests_mod.get(response_url, headers=headers, timeout=15)
        err = resp.json().get("error") or {}
        if err.get("message"):
            return f" — {err.get('code', 'error')}: {err['message']}"
    except Exception:
        pass
    return ""
