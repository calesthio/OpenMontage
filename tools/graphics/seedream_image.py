"""Seedream  V5 image generation via fal.ai API.
deep-thinking prompt understanding, native text in 14 languages, and precise control over dense layouts and structured designs.
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
class SeedreamImage(BaseTool):
    name = "seedream_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "bytedance"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:FAL_KEY"]
    install_instructions = (
        "Set FAL_KEY to your fal.ai API key.\n"
        "  Get one at https://fal.ai/dashboard/keys"
    )
    agent_skills = ["visual-style"]

    capabilities = [
        "generate_image",
        "text_to_image",
        "structured_designs",
        "dense_layouts",
        "multi_language_text",
    ]
    supports = {
        "text_rendering": True,
        "color_palette": True,
        "custom_size": True,
        "structured_designs": True,
        "dense_layouts": True,
        "multi_language_text": True,
    }
    best_for = [
        "raster brand and campaign assets",
        "images with accurate text rendering",
        "structured designs and dense layouts",
        "multi-language text rendering (14 languages)",
    ]
    input_schema = {
            "type": "object",
            "required": ["prompt"],
            "properties": {
                "prompt": {"type": "string"},
                "image_size": {
                    "type": "string",
                    "enum": [
                        "square", "square_hd",
                        "landscape_4_3", "landscape_16_9",
                        "portrait_4_3", "portrait_16_9",
                        "auto_1K","auto_2K"
                    ],
                    "default": "auto_2K",
                },
                "num_images": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 4,
                    "default": 1,
                },
                "output_format": {
                    "type": "string",
                    "enum": ["jpeg", "png"],
                    "description": "Output image format. Use 'jpeg' for smaller file size with lossy compression (suitable for web/preview), or 'png' for lossless quality with transparency support (suitable for design assets and further editing).",
                },
                "enable_safety_checker": {
                    "type": "boolean",
                    "default": True,
                    "description": "If set to true, the safety checker will be enabled.",
                 },
                 "output_path": {"type": "string"}
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = [
        "prompt",
        "image_size",
        "output_format",
        "num_images",
        "enable_safety_checker",
    ]
    side_effects = ["writes image file to output_path", "calls fal.ai queue API"]
    user_visible_verification = ["Inspect generated image for brand accuracy and text readability"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        image_size = inputs.get("image_size", "auto_2K")
        num_images = inputs.get("num_images", 1)
        size_price_map = {
            "square": 0.0675,
            "square_hd": 0.135,
            "landscape_4_3": 0.0675,
            "landscape_16_9": 0.135,
            "portrait_4_3": 0.0675,
            "portrait_16_9": 0.135,
            "auto_1K": 0.0675,
            "auto_2K": 0.135,
        }
        unit_price = size_price_map.get(image_size, 0.135)
        return round(unit_price * num_images, 4)

    @staticmethod
    def _output_paths(
        output_path: str | None, count: int, output_format: str
    ) -> list[Path]:
        path = Path(output_path or f"seedream_image.{output_format}")
        if not path.suffix:
            path = path.with_suffix(f".{output_format}")
        if count == 1:
            return [path]
        return [
            path.with_name(f"{path.stem}_{index}{path.suffix}")
            for index in range(1, count + 1)
        ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="FAL_KEY not set. " + self.install_instructions,
            )

        start = time.time()
        prompt = inputs["prompt"]
        num_images = inputs.get("num_images", 1)
        if isinstance(num_images, bool) or not isinstance(num_images, int):
            return ToolResult(
                success=False, error="num_images must be an integer from 1 to 4."
            )
        if not 1 <= num_images <= 4:
            return ToolResult(
                success=False, error="num_images must be between 1 and 4."
            )
        submit_url = "https://queue.fal.run/bytedance/seedream/v5/pro/text-to-image"
        payload: dict[str, Any] = {
            "prompt": prompt,
            "image_size": inputs.get("image_size", "auto_2K"),
            "output_format": inputs.get("output_format", "jpeg"),
            "num_images": num_images,
            "enable_safety_checker": inputs.get("enable_safety_checker", True),
        }

        try:
            headers = {
                "Authorization": f"Key {api_key}",
                "Content-Type": "application/json",
            }

            submit_resp = requests.post(
                submit_url,
                headers=headers,
                json=payload,
                timeout=(10, 60),
            )
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()
            request_id = submit_data.get("request_id")
            if not request_id:
                raise RuntimeError(
                    "Seedream submit succeeded but did not return request_id"
                )
            status_url = (
                f"https://queue.fal.run/bytedance/seedream/requests/"
                f"{request_id}/status"
            )
            elapsed = 0.0
            while elapsed < 300:
                status_resp = requests.get(
                    status_url,
                    headers=headers,
                    timeout=30,
                )
                status_resp.raise_for_status()
                status_data = status_resp.json()
                status = status_data.get("status")

                if status == "COMPLETED":
                    break
                elif status in ("FAILED", "CANCELLED"):
                    error_msg = status_data.get("error", "Unknown error")
                    raise RuntimeError(f"Seedream task {status}: {error_msg}")

                time.sleep(10)
                elapsed += 10

            if elapsed >= 300:
                raise RuntimeError(
                    f"Seedream task timed out after {300}s"
                )

            result_resp = requests.get(
                f"https://queue.fal.run/bytedance/seedream/requests/"
                f"{request_id}",
                headers=headers,
                timeout=30,
            )
            result_resp.raise_for_status()
            result_data = result_resp.json()

            images = result_data.get("images", [])
            if not images:
                raise RuntimeError("Seedream completed but no images returned")

            ext = inputs.get("output_format", "jpeg")
            expected_paths = self._output_paths(
                inputs.get("output_path"), len(images), ext
            )
            output_paths = []
            for img, output_path in zip(images, expected_paths):
                image_url = img.get("url")
                if not image_url:
                    continue
                image_resp = requests.get(image_url, timeout=60)
                image_resp.raise_for_status()

                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(image_resp.content)
                output_paths.append(str(output_path))

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Seedream generation failed: {e}",
            )

        return ToolResult(
            success=True,
            data={
                "provider": "seedream",
                "model": "seedream_v5",
                "prompt": prompt,
                "request_id": request_id,
                "image_count": len(output_paths),
                "outputs": output_paths,
            },
            artifacts=output_paths,
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model="fal-ai/bytedance/seedream/v5",
        )
