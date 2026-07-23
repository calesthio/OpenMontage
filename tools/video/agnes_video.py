"""Agnes AI video generation via Sapiens AI API.

Best for cost-free video generation with text-to-video, image-to-video,
multi-image video, and keyframe animation workflows.
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


class AgnesVideo(BaseTool):
    name = "agnes_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "agnes"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set AGNES_API_KEY to your Agnes AI API key.\n"
        "  Get one at https://www.agnes-ai.com"
    )
    agent_skills = ["agnes-video", "ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video", "multi_image_to_video", "keyframe_animation"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "multi_image_to_video": True,
        "keyframe_animation": True,
        "aspect_ratio": True,
        "seed": True,
        "cinematic_quality": True,
    }
    best_for = [
        "cost-free video generation (currently $0/second)",
        "keyframe animation and smooth transitions between visual states",
        "multi-image video compositing",
        "budget-constrained cinematic b-roll",
    ]
    not_good_for = ["offline generation", "native audio generation", "lip-sync"]
    fallback_tools = ["seedance_video", "kling_video", "veo_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "multi_image_to_video", "keyframe_animation"],
                "default": "text_to_video",
            },
            "width": {
                "type": "integer",
                "default": 1152,
                "description": "Video width. Normalized to nearest standard resolution by the API.",
            },
            "height": {
                "type": "integer",
                "default": 768,
                "description": "Video height. Normalized to nearest standard resolution by the API.",
            },
            "num_frames": {
                "type": "integer",
                "default": 121,
                "description": "Total frames. Must follow 8n+1 rule, max 441. 121=5s@24fps, 241=10s@24fps.",
            },
            "frame_rate": {
                "type": "integer",
                "default": 24,
                "description": "Playback frame rate (1-60).",
            },
            "seed": {"type": "integer"},
            "negative_prompt": {"type": "string"},
            "image_url": {
                "type": "string",
                "description": "Image URL for image_to_video.",
            },
            "image_path": {
                "type": "string",
                "description": "Local image path for image_to_video. Auto-converted to data URI.",
            },
            "image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Multiple image URLs for multi-image video or keyframe animation.",
            },
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local image paths for multi-image video or keyframe animation. Auto-converted to data URIs.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4"],
                "default": "16:9",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "num_frames", "frame_rate", "seed"]
    side_effects = ["writes video file to output_path", "calls Agnes AI API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence and visual quality"
    ]

    BASE_URL = "https://apihub.agnes-ai.com"
    POLL_INTERVAL = 5
    POLL_TIMEOUT = 600

    def _get_api_key(self) -> str | None:
        return os.environ.get("AGNES_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        num_frames = inputs.get("num_frames", 121)
        fps = inputs.get("frame_rate", 24)
        duration = num_frames / fps
        return max(60.0, duration * 12)

    def _resolve_aspect(self, aspect_ratio: str) -> tuple[int, int]:
        mapping = {
            "16:9": (1152, 768),
            "9:16": (768, 1152),
            "1:1": (768, 768),
            "4:3": (1024, 768),
            "3:4": (768, 1024),
        }
        return mapping.get(aspect_ratio, (1152, 768))

    def _upload_image_via_agnes(self, image_path: str) -> str:
        """Get a public URL for a local image by relaying it through the Agnes
        images API. The image is sent as an I2I reference with a preservation
        prompt so the output stays as close to the original as possible.

        Returns a public Agnes storage URL usable by the video API."""
        import requests as _requests

        api_key = self._get_api_key()
        if not api_key:
            raise RuntimeError("AGNES_API_KEY required for image upload")

        import base64

        suffix = Path(image_path).suffix.lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "image/png")
        img_w, img_h = self._image_dimensions(image_path)
        size = f"{img_w}x{img_h}" if img_w and img_h else "1024x1024"
        data_uri = f"data:{mime};base64,{base64.b64encode(Path(image_path).read_bytes()).decode()}"

        resp = _requests.post(
            f"{self.BASE_URL}/v1/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "agnes-image-2.1-flash",
                "prompt": "Preserve the original image exactly as-is with no changes, maintain the exact composition, subject, style, and colors",
                "size": size,
                "extra_body": {
                    "image": [data_uri],
                    "response_format": "url",
                },
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["url"]

    @staticmethod
    def _image_dimensions(image_path: str) -> tuple[int, int]:
        try:
            from PIL import Image

            with Image.open(image_path) as img:
                return img.size
        except Exception:
            return 0, 0

    def _local_to_data_uri(self, image_path: str) -> str:
        """Convert a local image to a data URI for inline embedding.
        Warning: large images may exceed API payload limits. Prefer URL-based upload."""
        import base64

        suffix = Path(image_path).suffix.lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "image/png")
        data = Path(image_path).read_bytes()
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="AGNES_API_KEY not set. " + self.install_instructions,
            )

        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        session = requests.Session()
        retry = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retry))

        start = time.time()
        operation = inputs.get("operation", "text_to_video")
        aspect_ratio = inputs.get("aspect_ratio", "16:9")
        default_w, default_h = self._resolve_aspect(aspect_ratio)
        width = inputs.get("width", default_w)
        height = inputs.get("height", default_h)
        num_frames = inputs.get("num_frames", 121)
        frame_rate = inputs.get("frame_rate", 24)

        payload: dict[str, Any] = {
            "model": "agnes-video-v2.0",
            "prompt": inputs["prompt"],
            "height": height,
            "width": width,
            "num_frames": num_frames,
            "frame_rate": frame_rate,
        }

        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]
        if inputs.get("negative_prompt"):
            payload["negative_prompt"] = inputs["negative_prompt"]

        if operation == "image_to_video":
            if inputs.get("image_url"):
                payload["image"] = inputs["image_url"]
            elif inputs.get("image_path"):
                try:
                    payload["image"] = self._upload_image_via_agnes(inputs["image_path"])
                except Exception:
                    try:
                        from tools.video._shared import upload_image_fal
                        payload["image"] = upload_image_fal(inputs["image_path"])
                    except Exception:
                        payload["image"] = self._local_to_data_uri(inputs["image_path"])

        extra_body: dict[str, Any] = {}
        if operation in ("multi_image_to_video", "keyframe_animation"):
            image_urls = list(inputs.get("image_urls") or [])
            image_paths = list(inputs.get("image_paths") or [])
            for ip in image_paths:
                try:
                    image_urls.append(self._upload_image_via_agnes(ip))
                except Exception:
                    try:
                        from tools.video._shared import upload_image_fal
                        image_urls.append(upload_image_fal(ip))
                    except Exception:
                        image_urls.append(self._local_to_data_uri(ip))
            if image_urls:
                extra_body["image"] = image_urls
            if operation == "keyframe_animation":
                extra_body["mode"] = "keyframes"

        if extra_body:
            payload["extra_body"] = extra_body

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            create_resp = None
            for attempt in range(3):
                try:
                    create_resp = session.post(
                        f"{self.BASE_URL}/v1/videos",
                        headers=headers,
                        json=payload,
                        timeout=120,
                    )
                    create_resp.raise_for_status()
                    break
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                    if attempt == 2:
                        raise
            task_data = create_resp.json()

            video_id = task_data.get("video_id") or task_data.get("task_id")
            if not video_id:
                return ToolResult(
                    success=False,
                    error=f"No video_id/task_id in Agnes AI response: {task_data}",
                )

            deadline = time.time() + self.POLL_TIMEOUT
            interval = self.POLL_INTERVAL
            while time.time() < deadline:
                time.sleep(interval)
                poll_resp = session.get(
                    f"{self.BASE_URL}/agnesapi?video_id={video_id}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=30,
                )
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()
                status = poll_data.get("status", "queued")

                if status == "completed":
                    video_url = poll_data.get("remixed_from_video_id") or poll_data.get("url")
                    if not video_url:
                        return ToolResult(
                            success=False,
                            error=f"Task completed but no video URL: {poll_data}",
                        )
                    break
                if status == "failed":
                    error_msg = poll_data.get("error") or "Unknown error"
                    return ToolResult(
                        success=False,
                        error=f"Agnes AI video generation failed: {error_msg}",
                    )
                interval = min(interval * 1.2, 30.0)
            else:
                return ToolResult(
                    success=False,
                    error=f"Agnes AI video generation timed out after {self.POLL_TIMEOUT}s",
                )

            download_resp = session.get(video_url, timeout=300)
            download_resp.raise_for_status()

            output_path = Path(inputs.get("output_path", "agnes_video.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(download_resp.content)

        except Exception as e:
            return ToolResult(success=False, error=f"Agnes AI video generation failed: {e}")

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        normalized_size = poll_data.get("size", f"{width}x{height}")
        normalized_seconds = poll_data.get("seconds", str(round(num_frames / frame_rate, 1)))

        return ToolResult(
            success=True,
            data={
                "provider": "agnes",
                "model": "agnes-video-v2.0",
                "prompt": inputs["prompt"],
                "operation": operation,
                "aspect_ratio": aspect_ratio,
                "normalized_size": normalized_size,
                "normalized_seconds": normalized_seconds,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                "video_id": video_id,
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model="agnes-video-v2.0",
        )
