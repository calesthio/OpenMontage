"""OpenAI Sora video generation via the OpenAI Video API."""

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


_DEFAULT_MODEL = "sora-2"
_DEFAULT_SIZE = "720x1280"
_DEFAULT_SECONDS = "4"
_ALLOWED_MODELS = ["sora-2", "sora-2-pro"]
_ALLOWED_SIZES = ["1280x720", "720x1280", "1024x1792", "1792x1024"]
_ALLOWED_SECONDS = ["4", "8", "12"]
_MIN_OPENAI_VERSION = (2, 44, 0)


class SoraVideo(BaseTool):
    name = "sora_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "openai"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set OPENAI_API_KEY to your OpenAI API key with Sora API access.\n"
        "  pip install 'openai>=2.44.0'"
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "native_audio": True,
        "camera_direction": True,
        "social_ads": True,
        "short_clips": True,
    }
    best_for = [
        "OpenAI Sora 2 / Sora 2 Pro clips from the project .env credentials",
        "short cinematic product-ad inserts with native ambience or dialogue",
        "4, 8, or 12 second social-video clips that OpenMontage can stitch and compose",
    ]
    not_good_for = ["offline generation", "long continuous scenes", "projects without Sora API access"]
    fallback_tools = ["veo_video", "gemini_omni_video", "seedance_video", "kling_video", "minimax_video"]

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
                "enum": _ALLOWED_MODELS,
                "default": _DEFAULT_MODEL,
            },
            "size": {
                "type": "string",
                "enum": _ALLOWED_SIZES,
                "default": _DEFAULT_SIZE,
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16"],
                "default": "9:16",
                "description": "Selector-friendly alias used to choose 1280x720 or 720x1280 when size is omitted.",
            },
            "seconds": {
                "type": "string",
                "enum": _ALLOWED_SECONDS,
                "default": _DEFAULT_SECONDS,
            },
            "duration": {
                "type": "string",
                "description": "Alias for seconds. Must be one of 4, 8, or 12.",
            },
            "input_reference_path": {
                "type": "string",
                "description": "Optional jpg/png/webp reference image for image-to-video.",
            },
            "reference_image_path": {
                "type": "string",
                "description": "Alias for input_reference_path.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=1000, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "size", "seconds"]
    side_effects = ["writes video file to output_path", "calls OpenAI Video API"]
    user_visible_verification = ["Watch generated clip for motion coherence, artifacts, and audio quality"]

    def get_status(self) -> ToolStatus:
        if not os.environ.get("OPENAI_API_KEY"):
            return ToolStatus.UNAVAILABLE
        if not self._openai_sdk_supports_videos():
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        seconds = int(self._normalize_seconds(inputs))
        # Placeholder estimate until the registry has live OpenAI video pricing.
        return 0.50 * (seconds / 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        seconds = int(self._normalize_seconds(inputs))
        return 120.0 * (seconds / 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not os.environ.get("OPENAI_API_KEY"):
            return ToolResult(
                success=False,
                error="OPENAI_API_KEY not set. " + self.install_instructions,
            )
        if not self._openai_sdk_supports_videos():
            return ToolResult(
                success=False,
                error="OpenAI SDK with Videos API support is required. " + self.install_instructions,
            )

        from openai import OpenAI

        start = time.time()
        model = self._normalize_model(inputs)
        size = self._normalize_size(inputs, model)
        seconds = self._normalize_seconds(inputs)
        prompt = str(inputs["prompt"]).strip()
        output_path = Path(inputs.get("output_path", "sora_output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "seconds": seconds,
        }

        reference_path = inputs.get("input_reference_path") or inputs.get("reference_image_path")
        if inputs.get("operation") == "image_to_video" or reference_path:
            if not reference_path:
                return ToolResult(success=False, error="image_to_video requires input_reference_path")
            reference = Path(str(reference_path))
            if not reference.exists():
                return ToolResult(success=False, error=f"Input reference not found: {reference}")
            payload["input_reference"] = {"image_url": self._file_to_data_uri(reference)}

        client = OpenAI()
        try:
            video = client.videos.create_and_poll(**payload)
            video_id = self._get_video_id(video)
            if not video_id:
                return ToolResult(success=False, error=f"OpenAI Sora response did not include a video id: {video}")

            status = self._get_status_value(video)
            if status != "completed":
                return ToolResult(success=False, error=f"OpenAI Sora generation ended with status: {status}")

            content = client.videos.download_content(video_id, variant="video")
            self._write_download(content, output_path)
        except Exception as exc:
            return ToolResult(success=False, error=f"OpenAI Sora video generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "openai",
                "model": model,
                "video_id": video_id,
                "prompt": prompt,
                "output": str(output_path),
                "size": size,
                "seconds": seconds,
                "format": "mp4",
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )

    @classmethod
    def _openai_sdk_supports_videos(cls) -> bool:
        try:
            import openai
            from openai import OpenAI
        except Exception:
            return False

        if cls._version_tuple(getattr(openai, "__version__", "")) < _MIN_OPENAI_VERSION:
            return False
        return hasattr(OpenAI(), "videos")

    @staticmethod
    def _version_tuple(version: str) -> tuple[int, int, int]:
        parts = []
        for part in version.split(".")[:3]:
            digits = "".join(ch for ch in part if ch.isdigit())
            parts.append(int(digits or "0"))
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)

    @staticmethod
    def _normalize_model(inputs: dict[str, Any]) -> str:
        model = str(inputs.get("model", _DEFAULT_MODEL)).strip().lower()
        if model not in _ALLOWED_MODELS:
            raise ValueError("model must be one of: sora-2, sora-2-pro")
        return model

    @staticmethod
    def _normalize_size(inputs: dict[str, Any], model: str) -> str:
        default_size = "1280x720" if inputs.get("aspect_ratio") == "16:9" else _DEFAULT_SIZE
        size = str(inputs.get("size", default_size)).strip().lower()
        allowed = {"1280x720", "720x1280"} if model == "sora-2" else set(_ALLOWED_SIZES)
        if size not in allowed:
            raise ValueError(f"size must be one of: {', '.join(sorted(allowed))} for model {model}")
        return size

    @staticmethod
    def _normalize_seconds(inputs: dict[str, Any]) -> str:
        seconds = str(inputs.get("seconds") or inputs.get("duration") or _DEFAULT_SECONDS).strip().lower()
        seconds = seconds[:-1] if seconds.endswith("s") else seconds
        if seconds not in _ALLOWED_SECONDS:
            raise ValueError("seconds must be one of: 4, 8, 12")
        return seconds

    @staticmethod
    def _get_status_value(video: Any) -> str:
        if isinstance(video, dict):
            return str(video.get("status") or video.get("state") or "unknown")
        return str(getattr(video, "status", None) or getattr(video, "state", None) or "unknown")

    @staticmethod
    def _get_video_id(video: Any) -> str | None:
        if isinstance(video, dict):
            value = video.get("id")
            return value if isinstance(value, str) else None
        value = getattr(video, "id", None)
        return value if isinstance(value, str) else None

    @staticmethod
    def _file_to_data_uri(path: Path) -> str:
        mime_type, _ = mimetypes.guess_type(path.name)
        if not mime_type:
            mime_type = "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _write_download(content: Any, output_path: Path) -> None:
        if hasattr(content, "write_to_file"):
            content.write_to_file(output_path)
            return
        if hasattr(content, "read"):
            output_path.write_bytes(content.read())
            return
        if hasattr(content, "content"):
            output_path.write_bytes(content.content)
            return
        output_path.write_bytes(bytes(content))
