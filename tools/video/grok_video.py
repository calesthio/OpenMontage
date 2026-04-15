"""xAI Grok Imagine video generation with native synchronized audio.

Generates 1-15 second videos with synchronized sound (dialogue with lip-sync,
SFX, ambient, background music) in a single pass. No post-production audio needed.
"""

from __future__ import annotations

import base64
import mimetypes
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


def _file_to_data_uri(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _normalize_media_ref(url_value: str | None, path_value: str | None) -> dict[str, str] | None:
    if url_value:
        return {"url": url_value}
    if path_value:
        return {"url": _file_to_data_uri(path_value)}
    return None


class GrokVideo(BaseTool):
    name = "grok_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "grok"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set XAI_API_KEY to your xAI API key.\n"
        "  Get one from the xAI developer console"
    )
    agent_skills = ["grok-media", "ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "reference_image": True,
        "multiple_reference_images": True,
        "native_audio": True,
        "lip_sync": True,
        "cinematic_quality": True,
    }
    best_for = [
        "cinematic clips with native synchronized audio (dialogue, SFX, music)",
        "reference-conditioned video with product/character consistency",
        "lip-synced dialogue and foley in a single generation pass",
        "cost-effective high-quality video ($0.07/s at 720p)",
    ]
    not_good_for = ["offline generation"]
    fallback_tools = ["veo_video", "runway_video", "kling_video", "minimax_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "enum": ["grok-imagine-video"],
                "default": "grok-imagine-video",
            },
            "duration": {
                "type": "integer",
                "minimum": 1,
                "maximum": 15,
                "default": 5,
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p"],
                "default": "720p",
            },
            "image_url": {"type": "string", "description": "Reference image URL for image_to_video"},
            "image_path": {"type": "string", "description": "Local reference image path for image_to_video"},
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Reference image URLs for reference_to_video",
            },
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local reference image paths for reference_to_video",
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
    idempotency_key_fields = ["prompt", "operation", "model", "duration", "aspect_ratio", "resolution"]
    side_effects = ["writes video file to output_path", "calls xAI video API"]
    user_visible_verification = ["Watch generated clip for motion quality and prompt fidelity"]

    def get_status(self) -> ToolStatus:
        if os.environ.get("XAI_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    @staticmethod
    def _normalize_resolution(value: str | None) -> str:
        if value == "540p":
            return "480p"
        return value or "720p"

    @staticmethod
    def _input_image_count(inputs: dict[str, Any]) -> int:
        count = 0
        if inputs.get("image_url") or inputs.get("image_path"):
            count += 1
        count += len(inputs.get("reference_image_urls") or [])
        count += len(inputs.get("reference_image_paths") or [])
        return count

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        duration = int(inputs.get("duration", 5))
        resolution = self._normalize_resolution(inputs.get("resolution"))
        base_per_second = 0.07 if resolution == "720p" else 0.05
        input_image_cost = self._input_image_count(inputs) * 0.002
        # xAI currently publishes Grok Imagine Video at $0.05/sec for 480p,
        # $0.07/sec for 720p, plus $0.002 per input image.
        return base_per_second * duration + input_image_cost

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        duration = int(inputs.get("duration", 5))
        return 90.0 + duration * 8.0

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        operation = inputs.get("operation", "text_to_video")
        payload: dict[str, Any] = {
            "model": inputs.get("model", "grok-imagine-video"),
            "prompt": inputs["prompt"],
        }

        if operation != "reference_to_video":
            payload["duration"] = int(inputs.get("duration", 5))
            if inputs.get("aspect_ratio"):
                payload["aspect_ratio"] = inputs["aspect_ratio"]
            if inputs.get("resolution"):
                payload["resolution"] = self._normalize_resolution(inputs["resolution"])

        if operation == "image_to_video":
            image = _normalize_media_ref(inputs.get("image_url"), inputs.get("image_path"))
            if not image:
                raise ValueError("image_to_video requires image_url or image_path")
            payload["image"] = image
        elif operation == "reference_to_video":
            refs = [{"url": url} for url in (inputs.get("reference_image_urls") or [])]
            refs.extend(
                {"url": _file_to_data_uri(path)}
                for path in (inputs.get("reference_image_paths") or [])
            )
            if not refs:
                raise ValueError(
                    "reference_to_video requires reference_image_urls or reference_image_paths"
                )
            payload["reference_images"] = refs
            payload["duration"] = int(inputs.get("duration", 5))
            if inputs.get("aspect_ratio"):
                payload["aspect_ratio"] = inputs["aspect_ratio"]
            if inputs.get("resolution"):
                payload["resolution"] = self._normalize_resolution(inputs["resolution"])

        return payload

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="XAI_API_KEY not set. " + self.install_instructions,
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
            response = requests.post(
                "https://api.x.ai/v1/videos/generations",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            request_id = response.json()["request_id"]

            timeout_seconds = int(inputs.get("timeout_seconds", 900))
            poll_interval = int(inputs.get("poll_interval_seconds", 5))
            deadline = time.time() + timeout_seconds

            result_data: dict[str, Any] | None = None
            while time.time() < deadline:
                result = requests.get(
                    f"https://api.x.ai/v1/videos/{request_id}",
                    headers={"Authorization": headers["Authorization"]},
                    timeout=30,
                )
                result.raise_for_status()
                result_data = result.json()
                status = result_data.get("status")
                if status == "done":
                    break
                if status in {"failed", "expired"}:
                    detail = result_data.get("error") or result_data.get("message") or status
                    return ToolResult(success=False, error=f"Grok video generation {status}: {detail}")
                time.sleep(poll_interval)

            if not result_data or result_data.get("status") != "done":
                return ToolResult(success=False, error="Grok video generation timed out")

            video_url = (result_data.get("video") or {}).get("url")
            if not video_url:
                return ToolResult(success=False, error="xAI video output missing url")

            download = requests.get(video_url, timeout=300)
            download.raise_for_status()
            output_path = Path(inputs.get("output_path", "grok_video_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(download.content)

        except Exception as e:
            return ToolResult(success=False, error=f"Grok video generation failed: {e}")

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "grok",
                "model": payload["model"],
                "prompt": inputs["prompt"],
                "operation": inputs.get("operation", "text_to_video"),
                "request_id": request_id,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=payload["model"],
        )
