"""Kling video generation via fal.ai API.

Best for cinematic B-roll with high visual fidelity and fluid motion.
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


class KlingVideo(BaseTool):
    name = "kling_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "kling"
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
    }
    best_for = [
        "cinematic B-roll with highest visual fidelity",
        "fluid motion and camera direction",
        "professional video clips",
    ]
    not_good_for = ["budget-constrained projects", "offline generation", "quick iteration"]
    fallback_tools = ["minimax_video", "veo_video", "wan_video"]

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
                "enum": ["v3/standard", "v2.1/master", "v2.1/pro", "v2.1/standard"],
                "default": "v3/standard",
            },
            "duration": {
                "type": "string",
                "enum": ["5", "10"],
                "default": "5",
                "description": "Duration in seconds",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1"],
                "default": "16:9",
            },
            "image_url": {"type": "string", "description": "Reference image URL for image_to_video"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model_variant", "operation", "duration"]
    side_effects = ["writes video file to output_path", "calls fal.ai API"]
    user_visible_verification = ["Watch generated clip for motion coherence and visual quality"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        variant = inputs.get("model_variant", "v3/standard")
        duration = int(inputs.get("duration", "5"))
        if "master" in variant:
            return 0.30 * (duration / 5)
        if "pro" in variant:
            return 0.20 * (duration / 5)
        return 0.10 * (duration / 5)  # standard

    def max_cost_usd(self, inputs: dict[str, Any]) -> float | None:
        """Upper bound on a single call's spend.

        The schema's known variants price exactly through the estimate; an
        unrecognized variant string is bounded at the dearest tier (master)
        rather than the cheap standard fallback. Duration comes from the
        request. execute() issues one billed request.
        """
        variant = inputs.get("model_variant", "v3/standard")
        if variant in ("v3/standard", "v2.1/master", "v2.1/pro", "v2.1/standard"):
            return self.estimate_cost(inputs)
        return self.estimate_cost({**inputs, "model_variant": "v2.1/master"})

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0  # ~1 minute typical

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
        variant = inputs.get("model_variant", "v3/standard")
        # fal.ai uses hyphens in endpoint paths (text-to-video, not text_to_video)
        operation_path = operation.replace("_", "-")
        model_path = f"kling-video/{variant}/{operation_path}"

        payload: dict[str, Any] = {"prompt": inputs["prompt"]}
        if inputs.get("duration"):
            payload["duration"] = inputs["duration"]
        if inputs.get("aspect_ratio"):
            payload["aspect_ratio"] = inputs["aspect_ratio"]
        if operation == "image_to_video" and inputs.get("image_url"):
            payload["image_url"] = inputs["image_url"]

        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }

        try:
            # Submit to queue API (async) — sync endpoint times out for video gen
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

            # Poll until complete
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
                        error=f"Kling video generation {status.lower()}",
                    )

            # Fetch result
            result_resp = requests.get(response_url, headers=headers, timeout=30)
            result_resp.raise_for_status()
            data = result_resp.json()

            video_url = data["video"]["url"]
            video_response = requests.get(video_url, timeout=120)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "kling_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as e:
            return ToolResult(success=False, error=f"Kling video generation failed: {e}")

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "kling",
                "model": f"fal-ai/{model_path}",
                "prompt": inputs["prompt"],
                "operation": operation,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
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
