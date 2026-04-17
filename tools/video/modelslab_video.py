"""ModelsLab video generation API."""

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


class ModelsLabVideo(BaseTool):
    name = "modelslab_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "modelslab"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set MODELSLAB_API_KEY to your ModelsLab API key.\n"
        "  Get one at https://modelslab.com"
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
    }
    best_for = [
        "cost-effective video generation",
        "text-to-video with various model options",
        "image-to-video conversion",
    ]
    not_good_for = ["offline generation", "real-time applications"]
    fallback_tools = ["kling_video", "veo_video", "wan_video", "runway_video"]

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
                "enum": ["wan2.1", "fastevaluate", "animatediff", "i2vgen", "modelscope"],
                "default": "wan2.1",
            },
            "num_frames": {"type": "integer", "default": 80, "description": "Number of frames (16-80)"},
            "fps": {"type": "integer", "default": 16, "description": "Frames per second"},
            "image_url": {"type": "string", "description": "Reference image URL for image_to_video"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation"]
    side_effects = ["writes video file to output_path", "calls modelslab API"]
    user_visible_verification = ["Watch generated clip for motion coherence and prompt adherence"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("MODELSLAB_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", "wan2.1")
        if model == "wan2.1":
            return 0.05  # per second estimate
        return 0.03

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0  # video generation takes time

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="MODELSLAB_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        operation = inputs.get("operation", "text_to_video")
        model = inputs.get("model", "wan2.1")
        prompt = inputs["prompt"]

        if operation == "image_to_video" and inputs.get("image_url"):
            endpoint = "image-to-video"
            payload: dict[str, Any] = {
                "key": api_key,
                "model_name": model,
                "image_url": inputs["image_url"],
            }
        else:
            endpoint = "text-to-video"
            payload = {
                "key": api_key,
                "model_name": model,
                "prompt": prompt,
                "num_frames": inputs.get("num_frames", 80),
                "fps": inputs.get("fps", 16),
            }

        headers = {"Content-Type": "application/json"}

        try:
            # Submit generation request
            submit_resp = requests.post(
                f"https://modelslab.com/api/v1/{endpoint}",
                json=payload,
                headers=headers,
                timeout=30,
            )
            submit_resp.raise_for_status()
            data = submit_resp.json()

            # Handle async responses
            request_id = data.get("request_id") or data.get("id")
            if not request_id:
                return ToolResult(
                    success=False,
                    error=f"No request_id in response: {data}",
                )

            # Poll until complete
            max_attempts = 60
            for _ in range(max_attempts):
                time.sleep(5)
                status_resp = requests.get(
                    "https://modelslab.com/api/v1/fetch",
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
                        error=f"ModelsLab video generation failed: {status_data.get('error', 'unknown error')}",
                    )

            # Extract video URL
            if data.get("output") and isinstance(data["output"], list):
                video_url = data["output"][0]
            elif data.get("video_url"):
                video_url = data["video_url"]
            else:
                return ToolResult(
                    success=False,
                    error=f"No video URL in response: {data}",
                )

            video_response = requests.get(video_url, timeout=120)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "modelslab_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as e:
            return ToolResult(success=False, error=f"ModelsLab video generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "modelslab",
                "model": f"{model}",
                "prompt": prompt,
                "operation": operation,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=f"modelslab/{model}",
        )
