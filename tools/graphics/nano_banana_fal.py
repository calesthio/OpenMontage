"""Google Nano Banana 2 / Nano Banana 2 Pro generation and editing via fal.ai.

Distinct from `atlas_image`, which routes nano-banana-2 through the Atlas
Cloud gateway (ATLASCLOUD_API_KEY) and does not expose the Pro variant at
all. This tool reaches both variants directly on fal.ai, gated only by
FAL_KEY/FAL_AI_API_KEY.

Endpoints confirmed against fal.ai docs (2026-08-20):
  https://fal.ai/models/fal-ai/nano-banana-2
  https://fal.ai/models/fal-ai/nano-banana-2/edit
  https://fal.ai/models/fal-ai/nano-banana-pro/api
  https://fal.ai/models/fal-ai/nano-banana-pro/edit/api
  - generate: fal-ai/nano-banana-2 | fal-ai/nano-banana-pro
  - edit:     fal-ai/nano-banana-2/edit | fal-ai/nano-banana-pro/edit
    (edit accepts up to 14 reference images via image_urls)
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

_ENDPOINTS = {
    ("nano-banana-2", "generate"): "fal-ai/nano-banana-2",
    ("nano-banana-2", "edit"): "fal-ai/nano-banana-2/edit",
    ("nano-banana-pro", "generate"): "fal-ai/nano-banana-pro",
    ("nano-banana-pro", "edit"): "fal-ai/nano-banana-pro/edit",
}

_MAX_EDIT_IMAGES = 14

# $0.08/image base rate confirmed for nano-banana-2 (both operations).
# nano-banana-pro's exact rate was not published on the fetched docs pages —
# the same base + multipliers are used as a placeholder estimate. Confirm
# against fal.ai's live pricing before relying on this for a paid batch run.
_BASE_PRICE = 0.08
_RESOLUTION_MULTIPLIER = {"0.5K": 0.75, "1K": 1.0, "2K": 1.5, "4K": 2.0}


class NanoBananaFal(BaseTool):
    name = "nano_banana_fal"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "google"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:FAL_KEY"]
    install_instructions = (
        "Set FAL_KEY (or FAL_AI_API_KEY) to your fal.ai API key.\n"
        "  Get one at https://fal.ai/dashboard/keys"
    )
    agent_skills = ["flux-best-practices"]

    capabilities = ["generate_image", "generate_illustration", "text_to_image", "image_edit"]
    supports = {
        "aspect_ratio": True,
        "custom_resolution": True,
        "image_edit": True,
        "multiple_reference_images": True,
        "text_in_image": True,
        "web_grounding": True,
    }
    best_for = [
        "Nano Banana 2 / Nano Banana 2 Pro generation and editing without an Atlas Cloud key",
        "up to 4K output with up to 14 reference images on edit",
        "text-heavy compositions (strong text rendering accuracy)",
    ]
    not_good_for = ["offline generation", "nano-banana-pro cost-sensitive batches (unconfirmed pricing)"]
    fallback_tools = ["atlas_image", "flux_image", "recraft_image"]
    quality_score = 0.87

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "enum": ["nano-banana-2", "nano-banana-pro"],
                "default": "nano-banana-2",
            },
            "operation": {
                "type": "string",
                "enum": ["generate", "edit"],
                "default": "generate",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": [
                    "auto", "21:9", "16:9", "3:2", "4:3", "5:4",
                    "1:1", "4:5", "3:4", "2:3", "9:16",
                ],
                "default": "auto",
            },
            "resolution": {
                "type": "string",
                "enum": ["0.5K", "1K", "2K", "4K"],
                "default": "1K",
            },
            "num_images": {"type": "integer", "default": 1, "minimum": 1, "maximum": 4},
            "seed": {"type": "integer"},
            "output_format": {
                "type": "string",
                "enum": ["png", "jpeg", "webp"],
                "default": "png",
            },
            "enable_web_search": {"type": "boolean"},
            "system_prompt": {"type": "string"},
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "image_paths": {"type": "array", "items": {"type": "string"}},
            "extra_params": {"type": "object"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=200, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "aspect_ratio", "resolution"]
    side_effects = ["writes image file(s) to output_path", "calls fal.ai API"]
    user_visible_verification = ["Inspect generated/edited images for prompt fidelity and edit consistency"]

    @staticmethod
    def _api_key() -> str | None:
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        n = int(inputs.get("num_images", 1))
        resolution = inputs.get("resolution", "1K")
        multiplier = _RESOLUTION_MULTIPLIER.get(resolution, 1.0)
        return round(_BASE_PRICE * multiplier * n, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 20.0 if inputs.get("model", "nano-banana-2") == "nano-banana-2" else 35.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False, error="FAL_KEY not set. " + self.install_instructions
            )

        import requests
        from tools.video._shared import upload_image_fal

        model = inputs.get("model", "nano-banana-2")
        operation = inputs.get("operation", "generate")
        endpoint = _ENDPOINTS.get((model, operation))
        if not endpoint:
            return ToolResult(
                success=False, error=f"unsupported model/operation combo: {model}/{operation}"
            )

        start = time.time()
        prompt = inputs["prompt"]
        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }

        try:
            payload: dict[str, Any] = {
                "prompt": prompt,
                "aspect_ratio": inputs.get("aspect_ratio", "auto"),
                "resolution": inputs.get("resolution", "1K"),
                "num_images": int(inputs.get("num_images", 1)),
            }
            if inputs.get("seed") is not None:
                payload["seed"] = inputs["seed"]
            if inputs.get("output_format") and inputs["output_format"] != "default":
                payload["output_format"] = inputs["output_format"]
            if inputs.get("enable_web_search") is not None:
                payload["enable_web_search"] = inputs["enable_web_search"]
            if inputs.get("system_prompt"):
                payload["system_prompt"] = inputs["system_prompt"]

            if operation == "edit":
                urls = list(inputs.get("image_urls") or [])
                for local in inputs.get("image_paths") or []:
                    urls.append(upload_image_fal(local))
                if inputs.get("image_url"):
                    urls.insert(0, inputs["image_url"])
                if inputs.get("image_path"):
                    urls.insert(0, upload_image_fal(inputs["image_path"]))
                if not urls:
                    return ToolResult(
                        success=False,
                        error="edit requires at least one image_url/image_path",
                    )
                if len(urls) > _MAX_EDIT_IMAGES:
                    return ToolResult(
                        success=False,
                        error=f"{model} edit accepts at most {_MAX_EDIT_IMAGES} images, got {len(urls)}",
                    )
                payload["image_urls"] = urls

            extra = inputs.get("extra_params")
            if isinstance(extra, dict):
                payload.update(extra)

            response = requests.post(
                f"https://fal.run/{endpoint}",
                headers=headers,
                json=payload,
                timeout=180,
            )
            response.raise_for_status()
            data = response.json()

            images = data.get("images") or []
            if not images:
                return ToolResult(success=False, error="fal.ai returned no image outputs")

            requested = Path(inputs.get("output_path") or f"{model.replace('-', '_')}_{operation}.png")
            output_paths: list[Path] = []
            for index, item in enumerate(images):
                out_path = requested if index == 0 else requested.with_name(
                    f"{requested.stem}_{index + 1}{requested.suffix}"
                )
                out_path.parent.mkdir(parents=True, exist_ok=True)
                image_response = requests.get(item["url"], timeout=60)
                image_response.raise_for_status()
                out_path.write_bytes(image_response.content)
                output_paths.append(out_path)

        except Exception as exc:
            return ToolResult(success=False, error=f"fal.ai {model} {operation} failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "google",
                "gateway": "fal.ai",
                "model": endpoint,
                "operation": operation,
                "prompt": prompt,
                "description": data.get("description"),
                "output": str(output_paths[0]),
                "outputs": [str(p) for p in output_paths],
                "images_generated": len(output_paths),
                "source_urls": [item["url"] for item in images],
            },
            artifacts=[str(p) for p in output_paths],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=endpoint,
            seed=inputs.get("seed"),
        )
