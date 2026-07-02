"""Clipia multi-model image generation via the Clipia public API.

Clipia (https://clipia.ai) is a generation aggregator: one API key covers
50+ hosted image and video models (Nano Banana, FLUX, GPT-Image, plus the
video catalog served by tools/video/clipia_video.py) behind a single
fal.ai-shaped queue API (submit -> status -> result). Model slugs are
discovered dynamically via GET /v1/models.

Notable for RU/CIS users: Clipia bills in rubles and accepts Russian bank
cards (USD/EUR plans exist too). Keys with the ``clipia_test_`` prefix run
in sandbox mode: instant mock COMPLETED results, no credits spent. See
docs/PROVIDERS.md and the ``clipia`` agent skill for the full API contract.
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
_DEFAULT_MODEL = "nano-banana-2"

_POLL_INTERVAL_SECONDS = 3.0
_POLL_TIMEOUT_SECONDS = 300.0  # images usually complete in seconds to ~2 min

# Clipia bills in credits; 1 credit ≈ $0.04 derived from public plan pricing
# ($0.04–0.06 depending on plan). Used only for ToolResult.cost_usd.
_CREDIT_USD = 0.04

# Approximate public credit prices per image at default resolution
# (clipia.ai pricing matrix, 2026-07). Resolution multipliers (e.g. 4K is
# roughly x1.4-1.5 on Nano Banana) are not modeled here — the exact price
# for a parameter set is POST /v1/models/{slug}/estimate (returns credits
# without queueing), not called here because estimate_cost() must stay
# fast and offline.
_CREDITS_PER_IMAGE = {
    "nano-banana-2": 4.0,
    "nano-banana-pro": 5.0,
    "flux-2-pro": 3.0,
    "gpt-image-2": 6.0,  # 3-7 depending on resolution
}
_DEFAULT_CREDITS_PER_IMAGE = 5.0

_TERMINAL_STATUSES = ("COMPLETED", "FAILED", "CANCELED")  # note: single L


class ClipiaImage(BaseTool):
    name = "clipia_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
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
    agent_skills = ["clipia"]

    capabilities = ["generate_image", "text_to_image", "image_to_image"]
    supports = {
        "text_to_image": True,
        "image_to_image": True,
        "multi_reference": True,
        "num_images": True,
        "model_selection": True,
        "sandbox_mode": True,
        "multi_model_aggregator": True,
    }
    best_for = [
        "one API key across Nano Banana, FLUX, GPT-Image and 20+ image models",
        "instruction-following edits and multi-reference composites (image_urls)",
        "RU/CIS users — billing in rubles with Russian bank cards",
        "integration testing via sandbox keys (clipia_test_) with zero credit spend",
    ]
    not_good_for = ["offline generation", "pixel-exact reproducibility (no seed parameter)"]
    fallback_tools = ["flux_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_image", "image_to_image"],
                "default": "text_to_image",
            },
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "description": (
                    "Clipia model slug, e.g. nano-banana-2, nano-banana-pro, "
                    "flux-2-pro, gpt-image-2. Full live catalog: "
                    "GET https://api.clipia.ai/v1/models."
                ),
            },
            "aspect_ratio": {
                "type": "string",
                "default": "1:1",
                "description": "e.g. 1:1, 16:9, 9:16, 4:3, 3:4 (model-dependent).",
            },
            "resolution": {
                "type": "string",
                "enum": ["1K", "2K", "4K"],
                "description": (
                    "Only sent when provided; supported values and price "
                    "multipliers vary per model (see GET /v1/models/{slug})."
                ),
            },
            "num_images": {
                "type": "integer",
                "minimum": 1,
                "maximum": 4,
                "default": 1,
                "description": "Variants per request (support varies by model).",
            },
            "image_url": {
                "type": "string",
                "description": "Input image URL, required for image_to_image.",
            },
            "image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Multiple reference images for multi-reference edits.",
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
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "aspect_ratio", "num_images"]
    side_effects = ["writes image file(s) to output_path", "calls the Clipia API (api.clipia.ai)"]
    user_visible_verification = [
        "Inspect generated image(s) for relevance and quality",
        "Sandbox keys return a fixed sample image — do not judge model quality from it",
    ]

    def _get_api_key(self) -> str | None:
        return os.environ.get("CLIPIA_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Approximate cost in USD from a static credit table (offline).

        Exact per-call pricing lives server-side at
        POST /v1/models/{slug}/estimate.
        """
        model = inputs.get("model", _DEFAULT_MODEL)
        num_images = int(inputs.get("num_images", 1) or 1)
        credits = _DEFAULT_CREDITS_PER_IMAGE
        for prefix, per_image in _CREDITS_PER_IMAGE.items():
            if model.startswith(prefix):
                credits = per_image
                break
        return round(credits * num_images * _CREDIT_USD, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0  # seconds to ~2 min typical; sandbox keys return instantly

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="CLIPIA_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        operation = inputs.get("operation", "text_to_image")
        model = inputs.get("model", _DEFAULT_MODEL)

        if operation == "image_to_image" and not (
            inputs.get("image_url") or inputs.get("image_urls")
        ):
            return ToolResult(
                success=False,
                error="image_url (or image_urls) is required for operation='image_to_image'",
            )

        payload: dict[str, Any] = {"prompt": inputs["prompt"]}
        if inputs.get("aspect_ratio"):
            payload["aspect_ratio"] = inputs["aspect_ratio"]
        if inputs.get("resolution"):
            payload["resolution"] = inputs["resolution"]
        num_images = int(inputs.get("num_images", 1) or 1)
        if num_images > 1:
            payload["num_images"] = num_images
        if inputs.get("image_url"):
            payload["image_url"] = inputs["image_url"]
        if inputs.get("image_urls"):
            payload["image_urls"] = inputs["image_urls"]

        headers = {
            # "Bearer <key>" and "X-Api-Key: <key>" are accepted too.
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": inputs.get("idempotency_key") or str(uuid.uuid4()),
        }

        try:
            # Submit to the queue API; `cost` is the fixed price in credits,
            # reserved at submit and refunded in full on failure.
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
                            f"Clipia image generation timed out after "
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
                return ToolResult(
                    success=False,
                    error=(
                        f"Clipia image generation {status.lower()}"
                        f"{_result_error_detail(requests, response_url, headers)} "
                        "(reserved credits are refunded)"
                    ),
                )

            # Fetch result (HTTP 200 for terminal statuses, 202 while running).
            result_resp = requests.get(response_url, headers=headers, timeout=30)
            result_resp.raise_for_status()
            result = result_resp.json()
            cost_credits = result.get("cost", cost_credits)

            images = (result.get("output") or {}).get("images") or []
            if not images:
                return ToolResult(
                    success=False,
                    error=f"Clipia result for {request_id} is missing image output",
                )

            output_path = Path(inputs.get("output_path", "clipia_image.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            saved: list[str] = []
            for i, image in enumerate(images):
                # `url` is a display-optimized rendition (usually WebP);
                # `original_url` is the full-quality PNG/JPG — prefer it.
                image_url = image.get("original_url") or image.get("url")
                if not image_url:
                    continue
                target = (
                    output_path
                    if i == 0
                    else output_path.with_name(
                        f"{output_path.stem}_{i + 1}{output_path.suffix}"
                    )
                )
                image_response = requests.get(image_url, timeout=60)
                image_response.raise_for_status()
                target.write_bytes(image_response.content)
                saved.append(str(target))

            if not saved:
                return ToolResult(
                    success=False,
                    error=f"Clipia result for {request_id} contained no downloadable images",
                )

        except Exception as e:
            return ToolResult(success=False, error=f"Clipia image generation failed: {e}")

        cost_usd = (
            round(cost_credits * _CREDIT_USD, 2)
            if isinstance(cost_credits, (int, float))
            else self.estimate_cost(inputs)
        )
        first_image = images[0]
        return ToolResult(
            success=True,
            data={
                "provider": "clipia",
                "model": model,
                "prompt": inputs["prompt"],
                "operation": operation,
                "aspect_ratio": inputs.get("aspect_ratio", "1:1"),
                "resolution": inputs.get("resolution"),
                "num_images": len(saved),
                "width": first_image.get("width"),
                "height": first_image.get("height"),
                "request_id": request_id,
                "cost_credits": cost_credits,
                "sandbox": api_key.startswith("clipia_test_"),
                "output": saved[0],
                "output_path": saved[0],
                "images": saved,
            },
            artifacts=saved,
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
