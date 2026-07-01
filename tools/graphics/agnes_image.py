"""Agnes AI image generation via Sapiens AI API.

Best for high-density visuals, multi-image composition, and cost-free generation.
"""

from __future__ import annotations

import base64
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


class AgnesImage(BaseTool):
    name = "agnes_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "agnes"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set AGNES_API_KEY to your Agnes AI API key.\n"
        "  Get one at https://www.agnes-ai.com"
    )
    agent_skills = ["agnes-image"]

    capabilities = [
        "generate_image",
        "generate_illustration",
        "text_to_image",
        "image_to_image",
        "multi_image_composition",
    ]
    supports = {
        "text_to_image": True,
        "image_to_image": True,
        "multi_image_composition": True,
        "custom_size": True,
        "seed": False,
    }
    best_for = [
        "cost-free image generation (currently $0/image)",
        "high-information-density visuals and complex compositions",
        "multi-image composition and character compositing",
        "image editing and style transfer",
    ]
    not_good_for = ["offline generation", "seed-reproducible outputs"]
    fallback_tools = ["flux_image", "openai_image", "google_imagen"]

    input_schema = {
        "type": "object",
        "required": ["prompt", "size"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text prompt describing the target image or editing instruction.",
            },
            "model": {
                "type": "string",
                "enum": ["agnes-image-2.0-flash", "agnes-image-2.1-flash"],
                "default": "agnes-image-2.1-flash",
                "description": (
                    "2.0: general T2I/I2I. "
                    "2.1: optimized for high-density details and complex compositions."
                ),
            },
            "size": {
                "type": "string",
                "default": "1024x768",
                "description": "Output image size, e.g. 1024x768, 1024x1024, 768x1024.",
            },
            "image_url": {
                "type": "string",
                "description": "Source image URL for image_to_image editing.",
            },
            "image_path": {
                "type": "string",
                "description": "Local source image path for image_to_image. Auto-converted to data URI.",
            },
            "image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Multiple source image URLs for multi-image composition.",
            },
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local source image paths for multi-image composition. Auto-converted to data URIs.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "size", "model"]
    side_effects = ["writes image file to output_path", "calls Agnes AI API"]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    BASE_URL = "https://apihub.agnes-ai.com/v1"

    def _get_api_key(self) -> str | None:
        return os.environ.get("AGNES_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        has_images = inputs.get("image_url") or inputs.get("image_path") or inputs.get("image_urls") or inputs.get("image_paths")
        return 30.0 if has_images else 15.0

    def _local_to_data_uri(self, image_path: str) -> str:
        suffix = Path(image_path).suffix.lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "image/png")
        data = Path(image_path).read_bytes()
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="AGNES_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        model = inputs.get("model", "agnes-image-2.1-flash")
        prompt = inputs["prompt"]
        size = inputs.get("size", "1024x768")

        extra_body: dict[str, Any] = {"response_format": "url"}

        images: list[str] = []
        if inputs.get("image_url"):
            images.append(inputs["image_url"])
        if inputs.get("image_urls"):
            images.extend(inputs["image_urls"])
        if inputs.get("image_path"):
            images.append(self._local_to_data_uri(inputs["image_path"]))
        if inputs.get("image_paths"):
            images.extend(self._local_to_data_uri(p) for p in inputs["image_paths"])

        if images:
            extra_body["image"] = images

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "extra_body": extra_body,
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=360,
            )
            response.raise_for_status()
            data = response.json()

            image_data = data["data"][0]
            image_url = image_data.get("url")
            b64 = image_data.get("b64_json")

            if image_url:
                img_resp = requests.get(image_url, timeout=60)
                img_resp.raise_for_status()
                image_bytes = img_resp.content
            elif b64:
                image_bytes = base64.b64decode(b64)
            else:
                return ToolResult(
                    success=False,
                    error="No image URL or base64 data in Agnes AI response",
                )

            output_path = Path(inputs.get("output_path", "agnes_image.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)

        except Exception as e:
            return ToolResult(success=False, error=f"Agnes AI image generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "agnes",
                "model": model,
                "prompt": prompt,
                "output": str(output_path),
                "size": size,
                "has_source_images": len(images) > 0,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
