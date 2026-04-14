"""Magic Hour cinematic video generation via Magic Hour API.

Best for premium cinematic B-roll, hyperreal motion, and ad-quality visuals.
Uses subscription credits via MAGICHOUR_API_KEY.
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


class MagicHourVideo(BaseTool):
    name = "magic_hour_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "magic_hour"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    install_instructions = (
        "Set MAGICHOUR_API_KEY to your Magic Hour API key.\n"
        "  Get one at https://magichour.ai/api-keys"
    )
    agent_skills = ["ai-video-gen", "create-video"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "cinematic_quality": True,
        "style_presets": True,
    }
    best_for = [
        "premium cinematic B-roll",
        "hyperreal motion and depth-of-field",
        "ad-quality visuals",
        "golden hour and dramatic lighting",
    ]
    not_good_for = [
        "free/budget generation",
        "offline workflows",
        "very short < 3s clips",
    ]
    fallback_tools = ["kling_video", "higgsfield_video", "minimax_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Video generation prompt"},
            "duration": {
                "type": "integer",
                "default": 5,
                "minimum": 3,
                "maximum": 30,
                "description": "Duration in seconds",
            },
            "style": {
                "type": "string",
                "enum": ["cinematic", "hyperreal", "ad", "natural"],
                "default": "cinematic",
                "description": "Visual style preset",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1"],
                "default": "16:9",
            },
            "image_url": {
                "type": "string",
                "description": "Reference image URL for image-to-video",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "duration", "style", "aspect_ratio"]
    side_effects = ["writes video file to output_path", "calls Magic Hour API"]
    user_visible_verification = [
        "Check clip for cinematic quality, motion fluidity, and lighting"
    ]

    # Approximate cost per second at cinematic quality
    _COST_PER_SEC = 0.04

    def get_status(self) -> ToolStatus:
        if os.environ.get("MAGICHOUR_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        duration = int(inputs.get("duration", 5))
        return round(self._COST_PER_SEC * duration, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        duration = int(inputs.get("duration", 5))
        # ~20-40s generation per second of video
        return float(duration * 25)

    def _enhance_prompt(self, prompt: str, style: str) -> str:
        """Append cinematic quality keywords based on style."""
        enhancements = {
            "cinematic": "golden hour lighting, soft shadows, shallow depth of field, realistic motion, cinematic",
            "hyperreal": "photorealistic, 8K detail, physically accurate lighting, hyperreal motion",
            "ad": "clean product lighting, sharp focus, professional color grade, advertisement quality",
            "natural": "natural lighting, realistic motion, authentic",
        }
        suffix = enhancements.get(style, enhancements["cinematic"])
        if suffix.split(",")[0].lower() not in prompt.lower():
            return f"{prompt}, {suffix}"
        return prompt

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("MAGICHOUR_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="MAGICHOUR_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        style = inputs.get("style", "cinematic")
        duration = int(inputs.get("duration", 5))
        prompt = self._enhance_prompt(inputs["prompt"], style)

        # Magic Hour API schema: end_seconds + style.prompt (not top-level prompt/duration)
        payload: dict[str, Any] = {
            "end_seconds": duration,
            "style": {"prompt": prompt},
            "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
        }
        if inputs.get("image_url"):
            payload["assets"] = {"image_url": inputs["image_url"]}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            # Submit generation job
            # Correct Magic Hour API endpoint (v1, no extra /api/ segment)
            submit_resp = requests.post(
                "https://api.magichour.ai/v1/text-to-video",
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit_resp.raise_for_status()
            job_data = submit_resp.json()
            job_id = job_data.get("id") or job_data.get("job_id")
            if not job_id:
                return ToolResult(
                    success=False,
                    error=f"Magic Hour did not return a job ID: {job_data}",
                )

            # Poll for completion — status at /v1/video-projects/{id}
            status_url = f"https://api.magichour.ai/v1/video-projects/{job_id}"
            max_wait = self.estimate_runtime(inputs) * 2
            poll_start = time.time()
            poll_interval = 5.0

            while True:
                if time.time() - poll_start > max_wait:
                    return ToolResult(
                        success=False,
                        error=f"Magic Hour job {job_id} timed out after {max_wait:.0f}s",
                    )
                time.sleep(poll_interval)
                poll_interval = min(poll_interval * 1.5, 30.0)  # back off gradually

                status_resp = requests.get(status_url, headers=headers, timeout=15)
                status_resp.raise_for_status()
                status_data = status_resp.json()
                status = status_data.get("status", "").lower()

                if status in ("complete", "completed", "done", "success"):
                    break
                if status in ("failed", "error", "cancelled", "canceled"):
                    return ToolResult(
                        success=False,
                        error=f"Magic Hour job {status}: {status_data.get('error', '')}",
                    )

            # Extract download URL — Magic Hour returns downloads[].url when complete
            downloads = status_data.get("downloads", [])
            video_url = (
                downloads[0].get("url") if downloads else None
            ) or (
                status_data.get("video_url")
                or status_data.get("output", {}).get("url")
                or status_data.get("result", {}).get("url")
            )
            if not video_url:
                return ToolResult(
                    success=False,
                    error=f"Magic Hour returned no video URL: {status_data}",
                )

            # Download the video
            video_resp = requests.get(video_url, timeout=120)
            video_resp.raise_for_status()

            output_path = Path(inputs.get("output_path", f"magic_hour_{job_id}.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_resp.content)

        except Exception as exc:
            return ToolResult(success=False, error=f"Magic Hour video generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "magic_hour",
                "job_id": job_id,
                "prompt": prompt,
                "original_prompt": inputs["prompt"],
                "style": style,
                "duration_requested": duration,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model="magic_hour_ai_video",
        )
