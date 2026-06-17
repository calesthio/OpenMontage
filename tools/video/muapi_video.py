"""MuAPI video generation via muapi.ai — 400+ model aggregator.

Provides unified access to text-to-video and image-to-video generation
through muapi.ai's single API: Veo3, Kling, Wan, Seedance, Runway, and more.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import requests

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

BASE_URL = "https://api.muapi.ai/api/v1"

T2V_MODELS = {
    "veo3": "veo3",
    "veo3-fast": "veo3-fast",
    "kling-master": "kling",
    "wan2.1": "wan2.1",
    "wan2.2": "wan2.2",
    "seedance-pro": "seedance-pro",
    "seedance-pro-fast": "seedance-pro-fast",
    "runway": "runway",
    "pixverse": "pixverse",
    "hunyuan": "hunyuan",
    "minimax-hailuo-02-pro": "minimax-hailuo-02-pro",
}

I2V_MODELS = {
    "kling-master": "kling-i2v",
    "kling-v2.5-pro": "kling-v2.5-pro-i2v",
    "wan2.1": "wan2.1-i2v",
    "wan2.2": "wan2.2-i2v",
    "seedance-pro": "seedance-pro-i2v",
    "runway": "runway-i2v",
    "pixverse": "pixverse-i2v",
    "hunyuan": "hunyuan-i2v",
    "vidu": "vidu-i2v",
}


class MuApiVideo(BaseTool):
    """Video generation via muapi.ai — a unified API for 400+ generative media models."""

    name = "muapi_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "muapi"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    install_instructions = (
        "Set MUAPI_API_KEY to your muapi.ai API key.\n"
        "  Get one at https://muapi.ai/dashboard/api-keys"
    )
    agent_skills = ["text-to-video", "image-to-video"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_image": True,
        "native_audio": False,
        "cinematic_quality": True,
        "aspect_ratio": True,
        "seed": False,
        "offline": False,
    }
    best_for = [
        "access to 400+ video generation models through a single API",
        "switching between Veo3, Kling, Wan, Seedance, Runway, and others without re-auth",
        "cost-effective video generation with pay-per-use pricing",
    ]
    not_good_for = ["offline generation", "sub-second latency requirements"]
    fallback_tools = ["kling_video", "runway_video", "seedance_video"]

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
            "model_variant": {
                "type": "string",
                "enum": sorted(T2V_MODELS),
                "default": "veo3-fast",
                "description": "Model to use. For image_to_video, valid values are: " + ", ".join(sorted(I2V_MODELS)),
            },
            "duration": {
                "type": "integer",
                "default": 5,
                "minimum": 3,
                "maximum": 60,
                "description": "Duration in seconds",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4"],
                "default": "16:9",
            },
            "image_url": {
                "type": "string",
                "description": "Start frame image URL for image_to_video",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model_variant", "operation", "duration"]
    side_effects = ["writes video file to output_path", "calls muapi.ai API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence and visual quality"
    ]

    def _get_api_key(self) -> str | None:
        return os.environ.get("MUAPI_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # muapi.ai charges per second of video generated
        duration = inputs.get("duration", 5)
        return round(0.05 * duration, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0

    def _poll(self, api_key: str, request_id: str, timeout: int = 600) -> str:
        headers = {"x-api-key": api_key}
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = requests.get(
                f"{BASE_URL}/predictions/{request_id}/result",
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "pending")
            if status == "completed":
                outputs = data.get("outputs", [])
                if not outputs:
                    raise ValueError("Generation completed but no outputs returned")
                return outputs[0]
            if status in ("failed", "cancelled"):
                raise ValueError(f"Video generation {status}: {data.get('error', '')}")
            time.sleep(5)
        raise TimeoutError(f"Video generation timed out after {timeout}s")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="MUAPI_API_KEY not set. " + self.install_instructions,
            )

        start = time.time()
        operation = inputs.get("operation", "text_to_video")
        model_variant = inputs.get("model_variant", "veo3-fast")

        if operation == "text_to_video":
            endpoint = T2V_MODELS.get(model_variant, model_variant)
        else:
            endpoint = I2V_MODELS.get(model_variant, f"{model_variant}-i2v")

        payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "duration": inputs.get("duration", 5),
            "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
        }

        if operation == "image_to_video" and inputs.get("image_url"):
            payload["image_url"] = inputs["image_url"]

        headers = {"x-api-key": api_key, "Content-Type": "application/json"}

        try:
            submit_resp = requests.post(
                f"{BASE_URL}/{endpoint}",
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit_resp.raise_for_status()
            request_id = submit_resp.json()["request_id"]

            video_url = self._poll(api_key, request_id)

            video_resp = requests.get(video_url, timeout=120)
            video_resp.raise_for_status()

            output_path = Path(inputs.get("output_path", "muapi_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_resp.content)

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"MuAPI video generation failed: {e}",
            )

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "muapi",
                "model": model_variant,
                "endpoint": endpoint,
                "prompt": inputs["prompt"],
                "operation": operation,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "duration": inputs.get("duration", 5),
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model_variant,
        )
