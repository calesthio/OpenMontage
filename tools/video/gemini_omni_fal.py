"""Gemini Omni Flash generation and editing through fal.ai."""

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


class GeminiOmniFalVideo(BaseTool):
    name = "gemini_omni_fal"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "gemini_omni"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API
    agent_skills = ["gemini-omni", "ai-video-gen"]
    capabilities = [
        "text_to_video",
        "image_to_video",
        "reference_to_video",
        "edit_video",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "video_to_video": True,
        "multiple_reference_images": True,
        "native_audio": True,
    }
    best_for = [
        "Gemini Omni Flash with a fal.ai key",
        "reference-image-driven 3-10 second video with synchronized audio",
    ]
    not_good_for = ["Google interaction-id workflows", "offline generation"]
    fallback_tools = ["gemini_omni_video", "runway_video", "veo_video"]
    dependencies = ["env:FAL_KEY"]
    install_instructions = (
        "Set FAL_KEY (or FAL_AI_API_KEY) from https://fal.ai/dashboard/keys."
    )
    quality_score = 0.85
    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": [
                    "text_to_video",
                    "image_to_video",
                    "reference_to_video",
                    "edit_video",
                ],
                "default": "text_to_video",
            },
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "reference_image_paths": {"type": "array", "items": {"type": "string"}},
            "video_url": {
                "type": "string",
                "description": "Source clip for edit_video",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16"],
                "default": "16:9",
            },
            "duration": {"type": "integer", "minimum": 3, "maximum": 10, "default": 8},
            "output_path": {"type": "string"},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = [
        "prompt",
        "operation",
        "aspect_ratio",
        "duration",
        "reference_image_urls",
    ]
    side_effects = ["writes video file to output_path", "calls fal.ai API"]
    user_visible_verification = ["Watch the clip and listen for synchronized audio"]

    @staticmethod
    def _api_key() -> str | None:
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return round(0.13 * int(inputs.get("duration", 8)), 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 90.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False, error="FAL_KEY not set. " + self.install_instructions
            )
        import requests
        from tools.video._shared import probe_output, upload_image_fal

        operation = inputs.get("operation", "text_to_video")
        urls = list(inputs.get("reference_image_urls") or [])
        for local in inputs.get("reference_image_paths") or []:
            urls.append(upload_image_fal(local))
        if inputs.get("image_url"):
            urls.insert(0, inputs["image_url"])
        elif inputs.get("image_path"):
            urls.insert(0, upload_image_fal(inputs["image_path"]))
        if operation in {"image_to_video", "reference_to_video"} and not urls:
            return ToolResult(
                success=False,
                error=f"{operation} requires at least one reference image",
            )

        endpoints = {
            "text_to_video": "google/gemini-omni-flash",
            "image_to_video": "google/gemini-omni-flash/image-to-video",
            "reference_to_video": "google/gemini-omni-flash/reference-to-video",
            "edit_video": "google/gemini-omni-flash/edit",
        }
        if operation not in endpoints:
            return ToolResult(
                success=False, error=f"unsupported Gemini Omni operation: {operation}"
            )
        if operation in {"text_to_video", "edit_video"} and urls:
            return ToolResult(
                success=False,
                error=f"{operation} does not accept reference images on fal.ai",
            )
        endpoint = endpoints[operation]
        payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
            "duration": int(inputs.get("duration", 8)),
        }
        if operation == "image_to_video":
            payload["image_url"] = urls[0]
        elif operation == "reference_to_video":
            payload["image_urls"] = urls
        elif operation == "edit_video":
            if not inputs.get("video_url"):
                return ToolResult(success=False, error="edit_video requires video_url")
            payload = {"prompt": inputs["prompt"], "video_url": inputs["video_url"]}
        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }
        started = time.time()
        try:
            submit = requests.post(
                f"https://queue.fal.run/{endpoint}",
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit.raise_for_status()
            queued = submit.json()
            while True:
                time.sleep(5)
                status_response = requests.get(
                    queued["status_url"], headers=headers, timeout=15
                )
                status_response.raise_for_status()
                status = status_response.json().get("status")
                if status == "COMPLETED":
                    break
                if status in {"FAILED", "CANCELLED"}:
                    return ToolResult(
                        success=False,
                        error=f"fal.ai Gemini Omni generation {status.lower()}",
                    )
            result_response = requests.get(
                queued["response_url"], headers=headers, timeout=30
            )
            result_response.raise_for_status()
            video_url = result_response.json()["video"]["url"]
            download = requests.get(video_url, timeout=120)
            download.raise_for_status()
            output_path = Path(inputs.get("output_path", "gemini_omni_fal_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(download.content)
        except Exception as exc:
            return ToolResult(
                success=False, error=f"fal.ai Gemini Omni generation failed: {exc}"
            )
        return ToolResult(
            success=True,
            data={
                "provider": "gemini_omni",
                "gateway": "fal.ai",
                "model": endpoint,
                "operation": operation,
                "output": str(output_path),
                **probe_output(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - started, 2),
            model=endpoint,
        )
