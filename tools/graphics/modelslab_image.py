"""ModelsLab image generation API."""

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


class ModelsLabImage(BaseTool):
    name = "modelslab_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "modelslab"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set MODELSLAB_API_KEY to your ModelsLab API key.\n"
        "  Get one at https://modelslab.com"
    )
    agent_skills = ["ai-image-gen"]

    capabilities = ["generate_image", "generate_illustration", "text_to_image"]
    supports = {
        "negative_prompt": True,
        "seed": True,
        "custom_size": True,
    }
    best_for = [
        "cost-effective image generation",
        "flux and sdxl models at competitive pricing",
        "image-to-image generation",
    ]
    not_good_for = ["offline generation", "real-time applications"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "negative_prompt": {"type": "string", "default": ""},
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "model": {
                "type": "string",
                "enum": [
                    "flux-v1-schnell", "flux-v1-dev", "flux-pro", "flux-sdxl",
                    "sdxl", "turbo-v2", "realistic-v5", "anime-v6", "custom",
                ],
                "default": "flux-v1-schnell",
            },
            "seed": {"type": "integer"},
            "num_inference_steps": {"type": "integer", "default": 30},
            "guidance_scale": {"type": "number", "default": 7.5},
            "image_url": {"type": "string", "description": "Reference image URL for image-to-image"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "width", "height", "seed", "model"]
    side_effects = ["writes image file to output_path", "calls modelslab API"]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("MODELSLAB_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", "flux-v1-schnell")
        if "pro" in model or "flux-sdxl" in model:
            return 0.05
        if "dev" in model:
            return 0.03
        return 0.02  # schnell/turbo

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="No ModelsLab API key found. " + self.install_instructions,
            )

        import requests

        start = time.time()
        model = inputs.get("model", "flux-v1-schnell")
        prompt = inputs["prompt"]
        width = inputs.get("width", 1024)
        height = inputs.get("height", 1024)

        # Build API URL based on operation
        if inputs.get("image_url"):
            endpoint = "image-to-image"
            payload: dict[str, Any] = {
                "key": api_key,
                "prompt": prompt,
                "model_name": model,
                "image_width": width,
                "image_height": height,
                "image_url": inputs["image_url"],
            }
        else:
            endpoint = "text-to-image"
            payload = {
                "key": api_key,
                "prompt": prompt,
                "model_name": model,
                "width": width,
                "height": height,
            }

        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]
        if inputs.get("num_inference_steps"):
            payload["num_inference_steps"] = inputs["num_inference_steps"]
        if inputs.get("guidance_scale"):
            payload["guidance_scale"] = inputs["guidance_scale"]
        if inputs.get("negative_prompt"):
            payload["negative_prompt"] = inputs["negative_prompt"]

        try:
            response = requests.post(
                f"https://modelslab.com/api/v1/{endpoint}",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            # Handle async responses (status polling)
            if "request_id" in data or data.get("status") == "processing":
                request_id = data.get("request_id") or data.get("id")
                max_attempts = 60
                for _ in range(max_attempts):
                    time.sleep(5)
                    status_resp = requests.get(
                        f"https://modelslab.com/api/v1/fetch",
                        params={"key": api_key, "request_id": request_id},
                        timeout=30,
                    )
                    status_resp.raise_for_status()
                    status_data = status_resp.json()
                    if status_data.get("status") == "completed":
                        data = status_data
                        break
                    elif status_data.get("status") in ("failed", "error"):
                        return ToolResult(
                            success=False,
                            error=f"ModelsLab generation failed: {status_data.get('error', 'unknown error')}",
                        )

            # Extract image URL from response
            if data.get("output") and isinstance(data["output"], list):
                image_url = data["output"][0]
            elif data.get("output_url"):
                image_url = data["output_url"]
            elif data.get("image_url"):
                image_url = data["image_url"]
            else:
                return ToolResult(
                    success=False,
                    error=f"Unexpected API response format: {data}",
                )

            image_response = requests.get(image_url, timeout=60)
            image_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "generated_image.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_response.content)

        except Exception as e:
            return ToolResult(success=False, error=f"ModelsLab generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "modelslab",
                "model": model,
                "prompt": prompt,
                "output": str(output_path),
                "seed": data.get("seed"),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            seed=data.get("seed"),
            model=f"modelslab/{model}",
        )
