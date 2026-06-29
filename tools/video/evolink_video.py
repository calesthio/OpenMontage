"""EvoLink video generation provider.

Wraps EvoLink's asynchronous video task API in OpenMontage's synchronous
BaseTool contract so the capability selectors can discover and rank it.
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


class EvoLinkVideo(BaseTool):
    name = "evolink_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "evolink"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set EVOLINK_API_KEY to your EvoLink API key.\n"
        "  Get one at https://evolink.ai/dashboard/keys"
    )
    agent_skills = ["ai-video-gen", "seedance-2-0"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_image": True,
        "native_audio": True,
        "cinematic_quality": True,
        "camera_direction": True,
        "lip_sync": True,
        "aspect_ratio": True,
        "web_search": True,
    }
    best_for = [
        "single EvoLink key access to premium video generation models",
        "Seedance 2.0 text-to-video and first-frame image-to-video clips",
        "cinematic short clips with optional synchronized audio",
        "web-search enhanced video prompts when current information matters",
    ]
    not_good_for = ["offline generation", "local image paths that are not publicly reachable URLs"]
    fallback_tools = ["seedance_video", "veo_video", "kling_video", "minimax_video"]
    quality_score = 0.92

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
            },
            "duration": {
                "type": "integer",
                "minimum": 4,
                "maximum": 15,
                "default": 5,
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "1080p"],
                "default": "720p",
            },
            "quality": {
                "type": "string",
                "enum": ["480p", "720p", "1080p"],
                "description": "Alias for resolution; EvoLink calls this field quality.",
            },
            "generate_audio": {"type": "boolean", "default": True},
            "content_filter": {"type": "boolean", "default": True},
            "web_search": {
                "type": "boolean",
                "default": False,
                "description": "Enable EvoLink's Seedance web search extension for text-to-video.",
            },
            "image_url": {
                "type": "string",
                "description": "First-frame image URL for image_to_video.",
            },
            "reference_image_url": {
                "type": "string",
                "description": (
                    "Alias accepted by OpenMontage selectors for the first-frame image URL."
                ),
            },
            "end_image_url": {
                "type": "string",
                "description": "Optional last-frame image URL for image_to_video.",
            },
            "output_path": {"type": "string"},
            "poll_interval_seconds": {"type": "integer", "minimum": 2, "default": 5},
            "timeout_seconds": {"type": "integer", "minimum": 30, "default": 900},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = [
        "prompt",
        "operation",
        "model_variant",
        "duration",
        "aspect_ratio",
        "resolution",
    ]
    side_effects = ["writes video file to output_path", "calls EvoLink API"]
    user_visible_verification = [
        "Watch generated clip for motion quality, prompt fidelity, and audio sync"
    ]

    def get_status(self) -> ToolStatus:
        if os.environ.get("EVOLINK_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        duration = self._normalize_duration(inputs.get("duration", 5))
        quality = inputs.get("quality") or inputs.get("resolution", "720p")
        variant = inputs.get("model_variant", "standard")
        rates = {
            "standard": {"480p": 0.092, "720p": 0.199, "1080p": 0.496},
            "fast": {"480p": 0.074, "720p": 0.161, "1080p": 0.496},
        }
        rate = rates.get(variant, rates["standard"]).get(quality, 0.199)
        return round(duration * rate, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        duration = self._normalize_duration(inputs.get("duration", 5))
        return 90.0 + duration * 10.0

    @staticmethod
    def _normalize_duration(value: Any) -> int:
        try:
            duration = int(value)
        except (TypeError, ValueError):
            duration = 5
        return min(15, max(4, duration))

    @staticmethod
    def _model_name(operation: str, variant: str) -> str:
        prefix = "seedance-2.0-fast" if variant == "fast" else "seedance-2.0"
        suffix = "image-to-video" if operation == "image_to_video" else "text-to-video"
        return f"{prefix}-{suffix}"

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        operation = inputs.get("operation", "text_to_video")
        if operation not in {"text_to_video", "image_to_video"}:
            raise ValueError(f"EvoLink video does not support operation: {operation}")

        variant = inputs.get("model_variant", "standard")
        payload: dict[str, Any] = {
            "model": self._model_name(operation, variant),
            "prompt": inputs["prompt"],
            "duration": self._normalize_duration(inputs.get("duration", 5)),
            "quality": inputs.get("quality") or inputs.get("resolution", "720p"),
            "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
            "generate_audio": inputs.get("generate_audio", True),
            "content_filter": inputs.get("content_filter", True),
        }

        if operation == "text_to_video" and inputs.get("web_search"):
            payload["model_params"] = {"web_search": True}

        if operation == "image_to_video":
            first_frame = inputs.get("image_url") or inputs.get("reference_image_url")
            if not first_frame:
                raise ValueError("image_to_video requires image_url or reference_image_url")
            image_urls = [first_frame]
            if inputs.get("end_image_url"):
                image_urls.append(inputs["end_image_url"])
            payload["image_urls"] = image_urls

        return payload

    @staticmethod
    def _extract_result_url(task_data: dict[str, Any]) -> str:
        results = task_data.get("results") or []
        if not results:
            raise RuntimeError(f"EvoLink task completed without result URLs: {task_data}")
        first = results[0]
        if not isinstance(first, str):
            raise RuntimeError(f"Unexpected EvoLink result payload: {results}")
        return first

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("EVOLINK_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="EVOLINK_API_KEY not set. " + self.install_instructions,
            )

        import requests
        from tools.video._shared import probe_output

        start = time.time()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            payload = self._build_payload(inputs)
            submit_resp = requests.post(
                "https://api.evolink.ai/v1/videos/generations",
                headers=headers,
                json=payload,
                timeout=60,
            )
            submit_resp.raise_for_status()
            task_data = submit_resp.json()
            task_id = task_data["id"]

            timeout_seconds = int(inputs.get("timeout_seconds", 900))
            poll_interval = int(inputs.get("poll_interval_seconds", 5))
            deadline = time.time() + timeout_seconds

            while time.time() < deadline:
                status_resp = requests.get(
                    f"https://api.evolink.ai/v1/tasks/{task_id}",
                    headers={"Authorization": headers["Authorization"]},
                    timeout=30,
                )
                status_resp.raise_for_status()
                task_data = status_resp.json()
                status = task_data.get("status")
                if status == "completed":
                    break
                if status == "failed":
                    error = task_data.get("error") or {}
                    detail = error.get("message") or error or "failed"
                    return ToolResult(
                        success=False,
                        error=f"EvoLink video generation failed: {detail}",
                    )
                time.sleep(min(poll_interval, max(0.0, deadline - time.time())))
            else:
                return ToolResult(
                    success=False,
                    error=f"EvoLink video generation timed out after {timeout_seconds}s",
                )

            video_url = self._extract_result_url(task_data)
            video_response = requests.get(video_url, timeout=120)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "evolink_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as exc:
            return ToolResult(success=False, error=f"EvoLink video generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "evolink",
                "model": payload["model"],
                "prompt": inputs["prompt"],
                "operation": inputs.get("operation", "text_to_video"),
                "task_id": task_id,
                "result_url": video_url,
                "aspect_ratio": payload.get("aspect_ratio"),
                "resolution": payload.get("quality"),
                "generate_audio": payload.get("generate_audio"),
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                "usage": task_data.get("usage"),
                **probe_output(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=payload["model"],
        )
