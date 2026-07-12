"""DolphinLitePark MaaS platform image generation tool.

Calls POST /v1/images/generations (OpenAI-compatible, synchronous or async-
task, see execute()). Two models:
  - leapfast/flux2 — self-hosted FLUX.1 on the H100 GPU cluster. Supports
    image-to-image via `input_image` (base64 data-uri or raw base64 — NOT a
    URL, per docs/multimodal-call-guide-v4.md).
  - gemini-3.1-flash-image-preview ("NanoBanana") — fast Visionular-backed
    generation. Uses ratio-style `size` ("16x9"/"3x4"/"1x1", not pixel
    dimensions) and a `quality` tier ("1K"/"2K"); image-to-image takes a
    `reference_images` array of URLs (NOT base64 — the inverse of flux2).

Gateway base URL: https://api.aiapbot.com (override via MAAS_API_BASE)
Auth:            Authorization: Bearer <MAAS_API_KEY>
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)
from tools.maas_base import MaasBaseTool


class MaasImage(MaasBaseTool):
    name = "maas_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "maas"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API

    dependencies = ["env:MAAS_API_KEY"]
    install_instructions = (
        "Set MAAS_API_KEY to your DolphinLitePark API key (sk-dlp-...).\n"
        "Optionally set MAAS_API_BASE to override the gateway URL\n"
        "(default: https://api.aiapbot.com)."
    )
    agent_skills = ["flux-best-practices", "bfl-api"]

    capabilities = ["generate_image", "text_to_image"]
    supports = {
        "text_to_image": True,
        "seed": True,
        "custom_size": True,
        "b64_json": True,
    }
    best_for = [
        "internal MaaS quota — no external billing",
        "leapfast/flux2: self-hosted FLUX.1 on H100 GPU, photorealistic quality",
        "fast iteration without consuming external API credits",
    ]
    not_good_for = [
        "offline / air-gapped environments",
        "access without a valid MAAS_API_KEY",
    ]
    fallback_tools = ["flux_image", "google_imagen", "recraft_image"]

    # Models available for image generation on the MaaS platform
    MODELS = {
        "leapfast/flux2": {"desc": "Self-hosted FLUX.1 on H100 cluster, photorealistic"},
        "gemini-3.1-flash-image-preview": {"desc": "NanoBanana — fast Visionular-backed generation"},
    }
    DEFAULT_MODEL = "leapfast/flux2"
    _NANOBANANA_MODEL = "gemini-3.1-flash-image-preview"

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Image generation prompt"},
            "model": {
                "type": "string",
                "description": (
                    "Gateway model ID: leapfast/flux2 (default, pixel-dimension "
                    "size like '1024x1024') or gemini-3.1-flash-image-preview "
                    "/ NanoBanana (ratio-style size like '16x9', see `quality`)"
                ),
                "default": "leapfast/flux2",
            },
            "size": {
                "type": "string",
                "description": (
                    "leapfast/flux2: WxH pixel dims, e.g. '1024x1024', '1280x720', '768x1344'. "
                    "gemini-3.1-flash-image-preview: ratio string, e.g. '16x9', '3x4', '1x1'."
                ),
                "default": "1024x1024",
            },
            "n": {
                "type": "integer",
                "default": 1,
                "description": "Number of images to generate",
            },
            "seed": {"type": "integer", "description": "Reproducibility seed"},
            "input_image": {
                "type": "string",
                "description": (
                    "leapfast/flux2 image-to-image: base64 reference image, "
                    "as a data:image/png;base64,... URI or raw base64. Not a URL."
                ),
            },
            "reference_images": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "gemini-3.1-flash-image-preview image-to-image: array of "
                    "reference image URLs. Not base64 — the inverse of flux2's input_image."
                ),
            },
            "quality": {
                "type": "string",
                "enum": ["1K", "2K"],
                "default": "1K",
                "description": "gemini-3.1-flash-image-preview only.",
            },
            "output_path": {"type": "string", "description": "Local path to save the PNG"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=20, network_required=True
    )
    # Declarative only — execute() doesn't wrap the submit call with retries
    # honoring this policy; it hand-rolls its own poll-retry tolerance instead
    # (see _MAX_POLL_ERRORS below). Same is true of every other API tool in
    # this codebase today.
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "rate_limit"])
    idempotency_key_fields = ["prompt", "model", "size", "seed"]
    side_effects = ["writes image file to output_path", "calls MaaS gateway API"]
    user_visible_verification = ["Inspect generated image for quality and prompt adherence"]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # MaaS bills internally in CNY; report 0 USD external cost.
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 15.0  # H100/FLUX2 is fast — typically 5-20s

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Build the /v1/images/generations payload for the selected model.
        Pulled out of execute() so the model-specific field mapping (see
        module docstring) is unit-testable without a network call."""
        model = inputs.get("model", self.DEFAULT_MODEL)
        prompt = inputs["prompt"]
        is_nanobanana = model == self._NANOBANANA_MODEL
        # flux2's default size is pixel dimensions ("1024x1024"); NanoBanana
        # takes a ratio string instead ("16x9") — a caller relying on the
        # schema default while switching models would otherwise silently
        # send a nonsensical ratio.
        size = inputs.get("size") or ("16x9" if is_nanobanana else "1024x1024")

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": inputs.get("n", 1),
            "response_format": "b64_json",
        }
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]

        if is_nanobanana:
            payload["quality"] = inputs.get("quality", "1K")
            if inputs.get("reference_images"):
                payload["images"] = inputs["reference_images"]
        elif inputs.get("input_image"):
            # flux2 image-to-image: base64 only, not a URL.
            payload["input_image"] = inputs["input_image"]

        return payload

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="MAAS_API_KEY not set. " + self.install_instructions,
            )

        base_url = self._base_url()
        model = inputs.get("model", self.DEFAULT_MODEL)
        prompt = inputs["prompt"]
        payload = self._build_payload(inputs)

        start = time.time()
        try:
            resp = requests.post(
                f"{base_url}/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
        except Exception as e:
            return ToolResult(success=False, error=f"MaaS image generation failed: {e}")

        data = resp.json()

        # H100/async providers return a task object instead of images directly.
        # The gateway sets response.id = requestId (NOT job_id which is the upstream ID).
        # Poll /v1/images/jobs/{requestId} until succeeded.
        if data.get("object") == "task":
            job_id = data.get("id")  # requestId set by the gateway controller
            deadline = start + 300  # 5-minute timeout for image jobs
            # Job is already submitted/billed — tolerate transient poll blips.
            poll_errors = 0
            _MAX_POLL_ERRORS = 5
            while time.time() < deadline:
                time.sleep(3)
                try:
                    poll = requests.get(
                        f"{base_url}/v1/images/jobs/{job_id}",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=15,
                    )
                    poll.raise_for_status()
                except Exception as e:
                    poll_errors += 1
                    if poll_errors >= _MAX_POLL_ERRORS:
                        return ToolResult(
                            success=False,
                            error=f"MaaS image poll failed {poll_errors}x (last: {e}); job_id={job_id}",
                        )
                    continue  # transient — retry on the next interval
                poll_errors = 0
                poll_data = poll.json()
                status = poll_data.get("status", "unknown")
                if status in ("succeeded", "completed"):
                    data = poll_data
                    break
                if status in ("failed", "cancelled"):
                    return ToolResult(
                        success=False,
                        error=f"MaaS image job {status}: {poll_data.get('error')}",
                    )
            else:
                return ToolResult(success=False, error=f"MaaS image job timed out (job_id={job_id})")

        # Synchronous response or settled async job:
        # shapes: {"data": [{"b64_json"|"url": ...}]}  OR  {"result_url": "..."}
        images = data.get("data", [])
        if not images and data.get("result_url"):
            images = [{"url": data["result_url"]}]
        if not images:
            return ToolResult(success=False, error=f"No images in MaaS response: {data}")

        first = images[0]
        output_path = Path(inputs.get("output_path", f"maas_image_{int(start)}.png"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if first.get("b64_json"):
            output_path.write_bytes(base64.b64decode(first["b64_json"]))
        elif first.get("url"):
            img_bytes = requests.get(first["url"], timeout=60)
            img_bytes.raise_for_status()
            output_path.write_bytes(img_bytes.content)
        else:
            return ToolResult(success=False, error=f"No image data in response: {first}")

        return ToolResult(
            success=True,
            data={
                "provider": "maas",
                "model": model,
                "prompt": prompt,
                "size": payload["size"],
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "png",
                "seed": data.get("seed") or first.get("seed"),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),   # 0.0 for free MaaS image gen
            duration_seconds=round(time.time() - start, 2),
            seed=data.get("seed") or first.get("seed"),
            model=model,
        )
