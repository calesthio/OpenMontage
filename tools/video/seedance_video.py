"""Seedance 2.0 (ByteDance) video generation via fal.ai API.

Best for cinematic clips with native audio, director-level camera control,
and lip-sync from quoted dialogue in prompts.
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


class SeedanceVideo(BaseTool):
    name = "seedance_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "seedance"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set FAL_KEY to your fal.ai API key.\n"
        "  Get one at https://fal.ai/dashboard/keys"
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "native_audio": True,
        "cinematic_quality": True,
        "camera_direction": True,
        "lip_sync": True,
    }
    best_for = [
        "cinematic clips with native synchronized audio",
        "director-level camera control and multi-shot editing",
        "lip-sync from quoted dialogue in prompts",
        "high-fidelity motion with real-world physics",
    ]
    not_good_for = ["offline generation", "budget-constrained projects"]
    fallback_tools = ["kling_video", "minimax_video", "veo_video"]

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
                "enum": ["standard", "fast"],
                "default": "standard",
                "description": "standard = highest quality, fast = lower latency and cost",
            },
            "duration": {
                "type": "string",
                "enum": ["auto", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"],
                "default": "5",
                "description": "Duration in seconds. 'auto' lets the model decide.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["auto", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p"],
                "default": "720p",
            },
            "generate_audio": {
                "type": "boolean",
                "default": True,
                "description": "Generate synchronized audio (speech, SFX, ambient)",
            },
            "image_url": {
                "type": "string",
                "description": "Start frame image URL for image_to_video (jpg, png, webp)",
            },
            "end_image_url": {
                "type": "string",
                "description": "Optional end frame URL for image_to_video",
            },
            "seed": {
                "type": "integer",
                "description": "Optional seed for reproducibility",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model_variant", "operation", "duration", "seed"]
    side_effects = ["writes video file to output_path", "calls fal.ai API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence, audio sync, and visual quality"
    ]

    def _get_api_key(self) -> str | None:
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        variant = inputs.get("model_variant", "standard")
        duration = inputs.get("duration", "5")
        secs = 5 if duration == "auto" else int(duration)
        rate = 0.2419 if variant == "fast" else 0.3034
        return round(rate * secs, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        variant = inputs.get("model_variant", "standard")
        return 60.0 if variant == "fast" else 120.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="FAL_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        operation = inputs.get("operation", "text_to_video")
        variant = inputs.get("model_variant", "standard")
        operation_path = operation.replace("_", "-")

        if variant == "fast":
            model_path = f"bytedance/seedance-2.0/fast/{operation_path}"
        else:
            model_path = f"bytedance/seedance-2.0/{operation_path}"

        payload: dict[str, Any] = {"prompt": inputs["prompt"]}

        if inputs.get("duration"):
            payload["duration"] = inputs["duration"]
        if inputs.get("aspect_ratio"):
            payload["aspect_ratio"] = inputs["aspect_ratio"]
        if inputs.get("resolution"):
            payload["resolution"] = inputs["resolution"]
        if "generate_audio" in inputs:
            payload["generate_audio"] = inputs["generate_audio"]
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]

        if operation == "image_to_video":
            if inputs.get("image_url"):
                payload["image_url"] = inputs["image_url"]
            elif inputs.get("image_path"):
                from tools.video._shared import upload_image_to_fal
                payload["image_url"] = upload_image_to_fal(inputs["image_path"])
            if inputs.get("end_image_url"):
                payload["end_image_url"] = inputs["end_image_url"]

        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }

        try:
            submit_resp = requests.post(
                f"https://queue.fal.run/fal-ai/{model_path}",
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit_resp.raise_for_status()
            queue_data = submit_resp.json()
            status_url = queue_data["status_url"]
            response_url = queue_data["response_url"]

            while True:
                time.sleep(5)
                status_resp = requests.get(status_url, headers=headers, timeout=15)
                status_resp.raise_for_status()
                status = status_resp.json().get("status", "UNKNOWN")
                if status == "COMPLETED":
                    break
                if status in ("FAILED", "CANCELLED"):
                    return ToolResult(
                        success=False,
                        error=f"Seedance 2.0 video generation {status.lower()}",
                    )

            result_resp = requests.get(response_url, headers=headers, timeout=30)
            result_resp.raise_for_status()
            data = result_resp.json()

            video_url = data["video"]["url"]
            video_response = requests.get(video_url, timeout=120)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "seedance_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Seedance 2.0 video generation failed: {e}",
            )

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "seedance",
                "model": f"fal-ai/{model_path}",
                "prompt": inputs["prompt"],
                "operation": operation,
                "variant": variant,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "resolution": inputs.get("resolution", "720p"),
                "generate_audio": inputs.get("generate_audio", True),
                "seed": data.get("seed"),
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=f"fal-ai/{model_path}",
        )
