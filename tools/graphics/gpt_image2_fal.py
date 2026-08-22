"""OpenAI GPT Image 2 generation and multi-reference editing via fal.ai.

Distinct from `openai_image` (calls OpenAI's API directly with OPENAI_API_KEY)
and from `atlas_image` (routes gpt-image-2 through the Atlas Cloud gateway
with ATLASCLOUD_API_KEY). This tool reaches the same model through fal.ai,
gated only by FAL_KEY/FAL_AI_API_KEY.

Endpoints confirmed against fal.ai docs (2026-08-20):
  https://fal.ai/models/openai/gpt-image-2
  - generate: fal-ai/gpt-image-2
  - edit:     fal-ai/gpt-image-2/image-to-image (accepts image_urls + prompt)
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
    "generate": "fal-ai/gpt-image-2",
    "edit": "fal-ai/gpt-image-2/image-to-image",
}

# Per-image pricing by nominal output size and quality tier, from the fal.ai
# pricing table. Edit pricing is not separately published — approximated
# with the 1024x1024 column. Verify against fal.ai before a large batch run.
_PRICE_TABLE: dict[str, dict[str, float]] = {
    "1024x768": {"low": 0.005, "medium": 0.037, "high": 0.145},
    "1024x1024": {"low": 0.006, "medium": 0.053, "high": 0.211},
    "1024x1536": {"low": 0.005, "medium": 0.042, "high": 0.165},
    "1920x1080": {"low": 0.005, "medium": 0.040, "high": 0.158},
    "2560x1440": {"low": 0.007, "medium": 0.056, "high": 0.222},
    "3840x2160": {"low": 0.012, "medium": 0.101, "high": 0.401},
}
_MAX_EDIT_IMAGES = 10  # matches the documented OpenAI gpt-image-2 edit limit


def _price_bucket(width: int, height: int) -> str:
    key = f"{width}x{height}"
    if key in _PRICE_TABLE:
        return key
    # Nearest bucket by pixel count for arbitrary sizes.
    target = width * height
    return min(_PRICE_TABLE, key=lambda k: abs(int(k.split("x")[0]) * int(k.split("x")[1]) - target))


class GptImage2Fal(BaseTool):
    name = "gpt_image2_fal"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "openai"
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
        "complex_instructions": True,
        "text_in_image": True,
        "multiple_outputs": True,
        "image_edit": True,
        "multiple_reference_images": True,
        "mask_editing": True,
    }
    best_for = [
        "GPT Image 2 generation and multi-reference editing without an OpenAI or Atlas Cloud key",
        "complex multi-element compositions",
        "images with text/labels",
    ]
    not_good_for = ["offline generation", "budget-constrained projects at high quality"]
    fallback_tools = ["openai_image", "atlas_image", "flux_image"]
    quality_score = 0.86

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["generate", "edit"],
                "default": "generate",
            },
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "quality": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "default": "high",
            },
            "num_images": {"type": "integer", "default": 1, "minimum": 1, "maximum": 4},
            "output_format": {
                "type": "string",
                "enum": ["png", "jpeg", "webp"],
                "default": "png",
            },
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "image_paths": {"type": "array", "items": {"type": "string"}},
            "mask_url": {"type": "string"},
            "mask_path": {"type": "string"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "operation", "width", "height", "quality"]
    side_effects = ["writes image file(s) to output_path", "calls fal.ai API"]
    user_visible_verification = ["Inspect generated image for relevance, quality, and edit fidelity"]

    @staticmethod
    def _api_key() -> str | None:
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        quality = inputs.get("quality", "high")
        n = int(inputs.get("num_images", 1))
        bucket = _price_bucket(int(inputs.get("width", 1024)), int(inputs.get("height", 1024)))
        return round(_PRICE_TABLE[bucket].get(quality, _PRICE_TABLE[bucket]["high"]) * n, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 25.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False, error="FAL_KEY not set. " + self.install_instructions
            )

        import requests
        from tools.video._shared import upload_image_fal

        operation = inputs.get("operation", "generate")
        if operation not in _ENDPOINTS:
            return ToolResult(success=False, error=f"unsupported operation: {operation}")

        start = time.time()
        prompt = inputs["prompt"]
        output_format = inputs.get("output_format", "png")
        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }

        try:
            if operation == "generate":
                payload: dict[str, Any] = {
                    "prompt": prompt,
                    "image_size": {
                        "width": int(inputs.get("width", 1024)),
                        "height": int(inputs.get("height", 1024)),
                    },
                    "quality": inputs.get("quality", "high"),
                    "num_images": int(inputs.get("num_images", 1)),
                    "output_format": output_format,
                }
            else:
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
                        error=f"gpt-image-2 edit accepts at most {_MAX_EDIT_IMAGES} images, got {len(urls)}",
                    )
                payload = {
                    "prompt": prompt,
                    "image_urls": urls,
                    "quality": inputs.get("quality", "high"),
                }
                mask_url = inputs.get("mask_url")
                if not mask_url and inputs.get("mask_path"):
                    mask_url = upload_image_fal(inputs["mask_path"])
                if mask_url:
                    payload["mask_image_url"] = mask_url

            endpoint = _ENDPOINTS[operation]
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

            requested = Path(inputs.get("output_path") or f"gpt_image2_fal_{operation}.png")
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
            return ToolResult(success=False, error=f"fal.ai GPT Image 2 {operation} failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "openai",
                "gateway": "fal.ai",
                "model": _ENDPOINTS[operation],
                "operation": operation,
                "prompt": prompt,
                "output": str(output_paths[0]),
                "outputs": [str(p) for p in output_paths],
                "images_generated": len(output_paths),
                "source_urls": [item["url"] for item in images],
            },
            artifacts=[str(p) for p in output_paths],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=_ENDPOINTS[operation],
        )
