"""Google Veo 3.1 video generation via Flow2API (local gateway).

Supports text-to-video (T2V), image-to-video (I2V), and reference-to-video (R2V)
through a local Flow2API proxy that bridges to Google VideoFX.
"""

from __future__ import annotations

import os
import time
import base64
import mimetypes
import uuid
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


class Flow2ApiVideo(BaseTool):
    name = "flow2api_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "flow2api"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set FLOW2API_API_KEY to your Flow2API API key.\n"
        "  Set FLOW2API_BASE_URL to your Flow2API server address (default http://127.0.0.1:8000)"
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "native_audio": True,
        "dialogue_generation": True,
        "ambient_sound": True,
    }
    best_for = [
        "cinematic quality video from Google Veo 3.1",
        "text-to-video with synchronized audio",
        "image-to-video motion animation",
        "multi-image reference video with character consistency",
        "free daily quota (1000 credits/day via Flow2API)",
    ]
    not_good_for = ["offline generation", "ultra-fast iteration without API"]
    fallback_tools = ["veo_video", "kling_video", "minimax_video", "wan_video"]

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
            "quality": {
                "type": "string",
                "enum": ["fast", "quality", "ultra"],
                "default": "fast",
                "description": "fast=quick generation, quality=standard, ultra=best quality",
            },
            "duration": {
                "type": "string",
                "enum": ["4s", "6s"],
                "default": "4s",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16"],
                "default": "16:9",
                "description": "16:9=landscape, 9:16=portrait",
            },
            "resolution": {
                "type": "string",
                "enum": ["720p", "1080p", "4k"],
                "default": "720p",
            },
            "image_path": {
                "type": "string",
                "description": "Local image path for image_to_video",
            },
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local reference image paths for reference_to_video",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "operation", "quality", "duration", "aspect_ratio"]
    side_effects = ["writes video file to output_path", "calls Flow2API server"]
    user_visible_verification = [
        "Watch generated clip for visual quality and motion",
        "Listen for audio synchronization and quality",
    ]

    def _get_api_key(self) -> str | None:
        return os.environ.get("FLOW2API_API_KEY")

    def _get_base_url(self) -> str:
        return os.environ.get("FLOW2API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Flow2API uses credits, not USD. Rough estimate: 1 credit ≈ $0.01 equivalent
        quality = inputs.get("quality", "fast")
        duration = int(str(inputs.get("duration", "4s")).replace("s", ""))
        resolution = inputs.get("resolution", "720p")

        if quality == "fast":
            credits = duration * 15
        elif quality == "ultra":
            credits = duration * 50
        else:
            credits = duration * 30

        if resolution == "4k":
            credits *= 2
        elif resolution == "1080p":
            credits = int(credits * 1.5)

        return credits * 0.01

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        quality = inputs.get("quality", "fast")
        if quality == "fast":
            return 60.0
        elif quality == "ultra":
            return 300.0
        return 120.0

    @staticmethod
    def _file_to_data_uri(path_str: str) -> str:
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        mime_type, _ = mimetypes.guess_type(path.name)
        if not mime_type:
            mime_type = "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _resolve_model_name(self, operation: str, quality: str, duration: str,
                            aspect_ratio: str, resolution: str) -> str:
        """Build the Flow2API model name from parameters."""
        is_landscape = aspect_ratio == "16:9"
        orient = "landscape" if is_landscape else ""
        dur = duration.replace("s", "")  # "4" or "6"
        res_suffix = ""
        if resolution == "4k":
            res_suffix = "_4k"
        elif resolution == "1080p":
            res_suffix = "_1080p"

        if operation == "text_to_video":
            prefix = "veo_3_1_t2v"
        elif operation == "image_to_video":
            prefix = "veo_3_1_i2v_s"
        elif operation == "reference_to_video":
            prefix = "veo_3_1_r2v"
        else:
            prefix = "veo_3_1_t2v"

        if quality == "fast":
            if operation == "text_to_video":
                if is_landscape:
                    return f"{prefix}_fast_landscape_{dur}s"
                return f"{prefix}_fast_{dur}s"
            elif operation == "image_to_video":
                if is_landscape:
                    return f"{prefix}_fast_landscape_{dur}s_fl"
                return f"{prefix}_fast_{dur}s_fl"
            elif operation == "reference_to_video":
                if is_landscape:
                    return f"{prefix}_fast_landscape"
                return f"{prefix}_fast"
        elif quality == "ultra":
            if is_landscape:
                return f"{prefix}_fast_landscape_ultra{res_suffix}"
            return f"{prefix}_fast_ultra{res_suffix}"
        else:  # quality == "quality"
            if is_landscape:
                return f"{prefix}_landscape_{dur}s{res_suffix}"
            return f"{prefix}_{dur}s{res_suffix}"

        return f"veo_3_1_t2v_fast_{dur}s"

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="FLOW2API_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        base_url = self._get_base_url()
        operation = inputs.get("operation", "text_to_video")
        quality = inputs.get("quality", "fast")
        duration = inputs.get("duration", "4s")
        aspect_ratio = inputs.get("aspect_ratio", "16:9")
        resolution = inputs.get("resolution", "720p")
        prompt = inputs["prompt"]

        model_name = self._resolve_model_name(
            operation, quality, duration, aspect_ratio, resolution
        )

        # Build OpenAI-compatible chat completion payload
        content_parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        if operation == "image_to_video":
            image_path = inputs.get("image_path")
            if not image_path:
                return ToolResult(
                    success=False,
                    error="image_to_video requires image_path",
                )
            data_uri = self._file_to_data_uri(image_path)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": data_uri},
            })

        if operation == "reference_to_video":
            ref_paths = inputs.get("reference_image_paths", [])
            if not ref_paths:
                return ToolResult(
                    success=False,
                    error="reference_to_video requires reference_image_paths",
                )
            for p in ref_paths:
                data_uri = self._file_to_data_uri(p)
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": data_uri},
                })

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": content_parts}],
        }

        # Set generationConfig for orientation
        gen_config: dict[str, Any] = {}
        if aspect_ratio == "9:16":
            gen_config["responseModalities"] = ["VIDEO"]
            gen_config["imageConfig"] = {"aspectRatio": "0.5625"}
        payload["generationConfig"] = gen_config

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Video generation timeout (from DB config: 1500s max)
        video_timeout = int(os.environ.get("FLOW2API_VIDEO_TIMEOUT", "300"))

        try:
            response = requests.post(
                f"{base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=video_timeout,
            )

            if response.status_code == 503:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_msg = error_data.get("error", {}).get("message", response.text[:500])
                return ToolResult(
                    success=False,
                    error=f"Flow2API token unavailable (503): {error_msg}. "
                          "Google token may be expired — refresh via Chrome extension or configure captcha solver.",
                )

            response.raise_for_status()
            data = response.json()

            # Parse response: video URL is typically in choices[0].message.content
            # or in a dedicated field
            video_url = None
            choices = data.get("choices", [])
            if choices:
                msg_content = choices[0].get("message", {}).get("content", "")
                if isinstance(msg_content, str) and msg_content.startswith("http"):
                    video_url = msg_content.strip()
                elif isinstance(msg_content, list):
                    for part in msg_content:
                        if isinstance(part, dict):
                            # Check various possible fields
                            if part.get("type") == "video":
                                video_url = part.get("video", {}).get("url")
                            elif part.get("type") == "output_url":
                                video_url = part.get("output_url")
                            elif "url" in part and "video" in str(part.get("url", "")).lower():
                                video_url = part["url"]
                            elif "video" in part:
                                v = part["video"]
                                if isinstance(v, dict):
                                    video_url = v.get("url")
                                elif isinstance(v, str):
                                    video_url = v

            # Also check top-level fields
            if not video_url:
                video_url = data.get("video") or data.get("url") or data.get("output")

            if not video_url:
                return ToolResult(
                    success=False,
                    error=f"Flow2API returned no video URL. Response: {str(data)[:1000]}",
                )

            # Download the video
            video_response = requests.get(video_url, timeout=120)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", f"flow2api_video_{uuid.uuid4().hex[:8]}.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except requests.exceptions.Timeout:
            return ToolResult(
                success=False,
                error=f"Flow2API video generation timed out after {video_timeout}s. "
                      "Video generation may still be processing — try increasing FLOW2API_VIDEO_TIMEOUT.",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Flow2API video generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "flow2api",
                "model": model_name,
                "prompt": prompt,
                "output": str(output_path),
                "operation": operation,
                "quality": quality,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
                "video_url": video_url,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model_name,
        )
