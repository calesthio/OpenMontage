"""MiniMax video generation via the official first-party API.

MiniMax-H3 uses the v2 content-based API. Hailuo 2.3 and earlier models keep
using the v1 generation, query, and file-retrieval flow. Both API versions
support the global and mainland China hosts through ``MINIMAX_REGION``.
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

REGION_BASE_URLS = {
    "global": "https://api.minimax.io",
    "global_en": "https://api.minimax.io",
    "cn": "https://api.minimaxi.com",
    "cn_zh": "https://api.minimaxi.com",
}
DEFAULT_REGION = "global"

V2_MODELS = ["MiniMax-H3"]
V1_MODELS = [
    "MiniMax-Hailuo-2.3",
    "MiniMax-Hailuo-2.3-Fast",
    "MiniMax-Hailuo-02",
    "T2V-01-Director",
    "T2V-01",
    "I2V-01-Director",
    "I2V-01-live",
    "I2V-01",
]
MODELS = V2_MODELS + V1_MODELS
DEFAULT_MODEL = "MiniMax-H3"

V2_RATIO_VALUES = ["adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]
_V2_IN_PROGRESS = {"queued", "running"}
_V2_SUCCESS = "succeeded"
_V2_FAILURES = {"failed", "cancelled"}
_V1_SUCCESS = "Success"
_V1_FAILURE = "Fail"


class MiniMaxVideo(BaseTool):
    name = "minimax_video"
    version = "0.3.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "minimax"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MINIMAX_API_KEY"]
    install_instructions = (
        "Set MINIMAX_API_KEY to your MiniMax API key.\n"
        "  Get one at https://platform.minimax.io/ (global) or "
        "https://platform.minimaxi.com/ (CN).\n"
        "  Optionally set MINIMAX_REGION=cn to route to the mainland China host, "
        "or MINIMAX_BASE_URL to override the endpoint entirely."
    )
    agent_skills = ["minimax-h3", "ai-video-gen"]

    capabilities = [
        "text_to_video",
        "image_to_video",
        "first_last_frame_to_video",
        "reference_to_video",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "first_last_frame_to_video": True,
        "reference_to_video": True,
        "reference_image": True,
        "reference_video": True,
        "reference_audio": True,
        "native_audio": True,
        "camera_direction": True,
    }
    best_for = [
        (
            "2K text, image, first/last-frame, and reference video generation "
            "with MiniMax-H3"
        ),
        "prompt-following with camera directions and high-texture footage",
        "direct first-party API access with global and mainland China routing",
    ]
    not_good_for = ["offline generation", "clips longer than 15 seconds"]
    fallback_tools = ["kling_video", "veo_video", "wan_video"]

    input_schema = {
        "type": "object",
        "required": [],
        "properties": {
            "prompt": {"type": "string", "maxLength": 7000},
            "operation": {
                "type": "string",
                "enum": [
                    "text_to_video",
                    "image_to_video",
                    "first_last_frame_to_video",
                    "reference_to_video",
                ],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "enum": MODELS,
                "default": DEFAULT_MODEL,
            },
            "first_frame_image": {
                "type": "string",
                "description": "Public URL or data URI used as the first frame.",
            },
            "last_frame_image": {
                "type": "string",
                "description": (
                    "Public URL or data URI used as the last frame by MiniMax-H3."
                ),
            },
            "end_image_url": {
                "type": "string",
                "description": "Alias for last_frame_image.",
            },
            "image_url": {
                "type": "string",
                "description": "Selector-compatible alias for first_frame_image.",
            },
            "reference_image_url": {
                "type": "string",
                "description": (
                    "First-frame alias or a reference image for reference_to_video."
                ),
            },
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
            },
            "reference_video_url": {
                "type": "string",
                "description": "Reference video URL for MiniMax-H3.",
            },
            "reference_video_urls": {
                "type": "array",
                "items": {"type": "string"},
            },
            "reference_audio_urls": {
                "type": "array",
                "items": {"type": "string"},
            },
            "prompt_optimizer": {"type": "boolean", "default": True},
            "fast_pretreatment": {"type": "boolean"},
            "duration": {
                "type": "integer",
                "minimum": 4,
                "maximum": 15,
                "description": (
                    "Clip length in seconds; MiniMax-H3 accepts integers from 4 to 15."
                ),
            },
            "resolution": {
                "type": "string",
                "description": (
                    "MiniMax-H3 requires 2K; v1 models accept their documented "
                    "resolutions."
                ),
            },
            "ratio": {"type": "string", "enum": V2_RATIO_VALUES},
            "aspect_ratio": {
                "type": "string",
                "enum": V2_RATIO_VALUES,
                "description": "Selector-compatible alias for ratio.",
            },
            "callback_url": {"type": "string"},
            "aigc_watermark": {
                "type": "boolean",
                "description": "Mainland China MiniMax-H3 watermark option.",
            },
            "poll_interval_seconds": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 60,
                "default": 5,
                "description": "Seconds between task-status requests.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 1,
                "maximum": 3600,
                "default": 900,
                "description": (
                    "Maximum time to wait for remote generation. Timeout errors "
                    "include task_id so the job can be recovered manually."
                ),
            },
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
        "model",
        "operation",
        "first_frame_image",
        "last_frame_image",
        "end_image_url",
        "image_url",
        "reference_image_url",
        "reference_image_urls",
        "reference_video_url",
        "reference_video_urls",
        "reference_audio_urls",
        "prompt_optimizer",
        "fast_pretreatment",
        "duration",
        "resolution",
        "ratio",
        "aspect_ratio",
        "callback_url",
        "aigc_watermark",
    ]
    side_effects = ["writes video file to output_path", "calls MiniMax video API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence and prompt adherence"
    ]

    def _get_api_key(self) -> str | None:
        return os.environ.get("MINIMAX_API_KEY")

    def _region(self) -> str:
        region = os.environ.get("MINIMAX_REGION", DEFAULT_REGION).strip().lower()
        return "cn" if region in {"cn", "cn_zh"} else "global"

    def _base_url(self) -> str:
        override = os.environ.get("MINIMAX_BASE_URL")
        if override:
            return override.rstrip("/")
        region = os.environ.get("MINIMAX_REGION", DEFAULT_REGION).strip().lower()
        return REGION_BASE_URLS.get(region, REGION_BASE_URLS[DEFAULT_REGION])

    def _uses_cn_api(self, base_url: str) -> bool:
        return self._region() == "cn" or "api.minimaxi.com" in base_url

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", DEFAULT_MODEL)
        if model == "MiniMax-H3":
            duration = inputs.get("duration", 5)
            if isinstance(duration, str) and duration.isdigit():
                duration = int(duration)
            seconds = (
                duration
                if isinstance(duration, int) and not isinstance(duration, bool)
                else 5
            )
            reference_images = len(inputs.get("reference_image_urls") or [])
            additional_images = max(0, reference_images - 5)
            return round((seconds * 0.13) + (additional_images * 0.03), 2)
        if "Fast" in model:
            return 0.08
        return 0.15

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", DEFAULT_MODEL)
        if model == "MiniMax-H3":
            return 90.0
        if "Fast" in model:
            return 30.0
        return 60.0

    @staticmethod
    def _base_resp_error(payload: dict[str, Any]) -> str | None:
        """Return an error string when a v1 base_resp signals failure."""
        base_resp = payload.get("base_resp") or {}
        status_code = base_resp.get("status_code")
        if status_code in (None, 0):
            return None
        status_msg = base_resp.get("status_msg", "")
        return f"MiniMax API error {status_code}: {status_msg}".strip()

    @staticmethod
    def _media_content(content_type: str, url: str, role: str) -> dict[str, Any]:
        return {
            "type": content_type,
            content_type: {"url": url},
            "role": role,
        }

    @staticmethod
    def _url_values(inputs: dict[str, Any], singular: str, plural: str) -> list[str]:
        values: list[str] = []
        if inputs.get(singular):
            values.append(str(inputs[singular]))
        values.extend(str(value) for value in (inputs.get(plural) or []) if value)
        return values

    def _build_v2_payload(
        self,
        inputs: dict[str, Any],
        base_url: str,
    ) -> tuple[dict[str, Any] | None, str | None]:
        operation = inputs.get("operation", "text_to_video")
        prompt = str(inputs.get("prompt") or "")
        if not prompt:
            return None, "MiniMax-H3 requires 'prompt'."
        if len(prompt) > 7000:
            return None, "MiniMax-H3 prompt must not exceed 7000 characters."

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        first_frame = (
            inputs.get("first_frame_image")
            or inputs.get("image_url")
            or inputs.get("reference_image_url")
        )
        last_frame = inputs.get("last_frame_image") or inputs.get("end_image_url")

        if operation in {"image_to_video", "first_last_frame_to_video"}:
            if not first_frame:
                return None, f"{operation} requires 'first_frame_image'."
            content.append(
                self._media_content("image_url", str(first_frame), "first_frame")
            )
            if operation == "first_last_frame_to_video" and not last_frame:
                return None, "first_last_frame_to_video requires 'last_frame_image'."
            if last_frame:
                content.append(
                    self._media_content("image_url", str(last_frame), "last_frame")
                )
        elif operation == "reference_to_video":
            reference_images = self._url_values(
                inputs, "reference_image_url", "reference_image_urls"
            )
            reference_videos = self._url_values(
                inputs, "reference_video_url", "reference_video_urls"
            )
            reference_audio = [
                str(value)
                for value in (inputs.get("reference_audio_urls") or [])
                if value
            ]
            if not reference_images and not reference_videos and not reference_audio:
                return None, "reference_to_video requires at least one reference URL."
            if reference_audio and not (reference_images or reference_videos):
                return (
                    None,
                    "Reference audio requires at least one reference image or video.",
                )
            content.extend(
                self._media_content("image_url", url, "reference_image")
                for url in reference_images
            )
            content.extend(
                self._media_content("video_url", url, "reference_video")
                for url in reference_videos
            )
            content.extend(
                self._media_content("audio_url", url, "reference_audio")
                for url in reference_audio
            )
        elif operation != "text_to_video":
            return None, f"MiniMax-H3 does not support operation '{operation}'."

        duration = inputs.get("duration", 5)
        if isinstance(duration, str) and duration.isdigit():
            duration = int(duration)
        if (
            isinstance(duration, bool)
            or not isinstance(duration, int)
            or not 4 <= duration <= 15
        ):
            return None, "MiniMax-H3 duration must be an integer from 4 to 15 seconds."

        resolution = inputs.get("resolution", "2K")
        if resolution != "2K":
            return None, "MiniMax-H3 resolution must be '2K'."

        ratio = inputs.get("ratio") or inputs.get("aspect_ratio")
        if not ratio:
            ratio = "16:9" if operation == "text_to_video" else "adaptive"
        if ratio not in V2_RATIO_VALUES:
            return None, f"Unsupported MiniMax-H3 ratio '{ratio}'."
        if operation == "text_to_video" and ratio == "adaptive":
            return None, "MiniMax-H3 text_to_video does not support the adaptive ratio."

        payload: dict[str, Any] = {
            "model": "MiniMax-H3",
            "content": content,
            "resolution": resolution,
            "duration": duration,
            "ratio": ratio,
        }
        if inputs.get("callback_url"):
            payload["callback_url"] = inputs["callback_url"]
        if self._uses_cn_api(base_url) and "aigc_watermark" in inputs:
            payload["aigc_watermark"] = inputs["aigc_watermark"]
        return payload, None

    @staticmethod
    def _build_v1_payload(
        inputs: dict[str, Any], model: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        operation = inputs.get("operation", "text_to_video")
        if operation not in {"text_to_video", "image_to_video"}:
            return None, f"{model} does not support operation '{operation}'."

        payload: dict[str, Any] = {"model": model}
        if operation == "image_to_video":
            first_frame = (
                inputs.get("first_frame_image")
                or inputs.get("reference_image_url")
                or inputs.get("image_url")
            )
            if not first_frame:
                return None, "image_to_video requires 'first_frame_image'."
            payload["first_frame_image"] = first_frame
            if inputs.get("prompt"):
                payload["prompt"] = inputs["prompt"]
        else:
            if not inputs.get("prompt"):
                return None, "text_to_video requires 'prompt'."
            payload["prompt"] = inputs["prompt"]

        if "prompt_optimizer" in inputs:
            payload["prompt_optimizer"] = inputs["prompt_optimizer"]
        for field in ("fast_pretreatment", "duration", "resolution", "callback_url"):
            if inputs.get(field) is not None:
                payload[field] = inputs[field]
        return payload, None

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="MINIMAX_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        base_url = self._base_url()
        model = inputs.get("model", DEFAULT_MODEL)
        if model not in MODELS:
            return ToolResult(
                success=False, error=f"Unsupported MiniMax model '{model}'."
            )

        if model in V2_MODELS:
            payload, validation_error = self._build_v2_payload(inputs, base_url)
            api_version = "v2"
        else:
            payload, validation_error = self._build_v1_payload(inputs, model)
            api_version = "v1"
        if validation_error:
            return ToolResult(success=False, error=validation_error)
        assert payload is not None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        def _redact(text: str) -> str:
            return text.replace(api_key, "***") if api_key else text

        task_id: str | None = None
        file_id: str | None = None
        task_data: dict[str, Any] = {}
        poll_interval = max(float(inputs.get("poll_interval_seconds", 5)), 0.1)
        timeout_seconds = max(float(inputs.get("timeout_seconds", 900)), 1.0)
        poll_deadline = time.monotonic() + timeout_seconds

        def _timeout_result() -> ToolResult:
            return ToolResult(
                success=False,
                error=(
                    f"MiniMax video generation timed out after {timeout_seconds:g}s; "
                    f"the remote task may still complete. Resume or inspect task_id "
                    f"'{task_id}'."
                ),
                data={
                    "provider": "minimax",
                    "model": model,
                    "api_version": api_version,
                    "task_id": task_id,
                    "status": "timed_out",
                },
                model=model,
            )

        try:
            submit_resp = requests.post(
                f"{base_url}/{api_version}/video_generation",
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()
            if api_version == "v1":
                base_err = self._base_resp_error(submit_data)
                if base_err:
                    return ToolResult(success=False, error=base_err)
            task_id = submit_data.get("task_id")
            if not task_id:
                return ToolResult(
                    success=False, error="MiniMax API did not return a task_id."
                )

            download_url: str | None = None
            if api_version == "v2":
                while True:
                    if time.monotonic() >= poll_deadline:
                        return _timeout_result()
                    time.sleep(
                        min(poll_interval, max(poll_deadline - time.monotonic(), 0))
                    )
                    if time.monotonic() >= poll_deadline:
                        return _timeout_result()
                    status_resp = requests.get(
                        f"{base_url}/v2/query/video_generation/{task_id}",
                        headers=headers,
                        timeout=15,
                    )
                    status_resp.raise_for_status()
                    task_data = status_resp.json().get("task") or {}
                    status = task_data.get("status")
                    if status == _V2_SUCCESS:
                        download_url = (task_data.get("content") or {}).get("url")
                        break
                    if status in _V2_FAILURES:
                        error = task_data.get("error") or "unknown error"
                        return ToolResult(
                            success=False,
                            error=f"MiniMax-H3 video generation {status}: {error}",
                        )
                    if status not in _V2_IN_PROGRESS:
                        return ToolResult(
                            success=False,
                            error=(
                                f"MiniMax-H3 returned unknown task status '{status}'."
                            ),
                        )
            else:
                while True:
                    if time.monotonic() >= poll_deadline:
                        return _timeout_result()
                    time.sleep(
                        min(poll_interval, max(poll_deadline - time.monotonic(), 0))
                    )
                    if time.monotonic() >= poll_deadline:
                        return _timeout_result()
                    status_resp = requests.get(
                        f"{base_url}/v1/query/video_generation",
                        headers=headers,
                        params={"task_id": task_id},
                        timeout=15,
                    )
                    status_resp.raise_for_status()
                    status_data = status_resp.json()
                    base_err = self._base_resp_error(status_data)
                    if base_err:
                        return ToolResult(success=False, error=base_err)
                    status = status_data.get("status", "")
                    if status == _V1_SUCCESS:
                        file_id = status_data.get("file_id")
                        break
                    if status == _V1_FAILURE:
                        return ToolResult(
                            success=False, error="MiniMax video generation failed."
                        )

                if not file_id:
                    return ToolResult(
                        success=False,
                        error="MiniMax API did not return a file_id on success.",
                    )
                file_resp = requests.get(
                    f"{base_url}/v1/files/retrieve",
                    headers=headers,
                    params={"file_id": file_id},
                    timeout=30,
                )
                file_resp.raise_for_status()
                file_data = file_resp.json()
                base_err = self._base_resp_error(file_data)
                if base_err:
                    return ToolResult(success=False, error=base_err)
                download_url = (file_data.get("file") or {}).get("download_url")

            if not download_url:
                return ToolResult(
                    success=False, error="MiniMax API did not return a download URL."
                )

            video_response = requests.get(download_url, timeout=120)
            video_response.raise_for_status()
            output_path = Path(inputs.get("output_path", "minimax_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)
        except Exception as e:  # noqa: BLE001 - surface a redacted error to the caller
            return ToolResult(
                success=False,
                error=f"MiniMax video generation failed: {_redact(str(e))}",
                data={
                    "provider": "minimax",
                    "model": model,
                    "api_version": api_version,
                    "task_id": task_id,
                }
                if task_id
                else {},
                model=model,
            )

        data: dict[str, Any] = {
            "provider": "minimax",
            "model": model,
            "api_version": api_version,
            "region": base_url,
            "task_id": task_id,
            "prompt": inputs.get("prompt", ""),
            "output": str(output_path),
        }
        if file_id:
            data["file_id"] = file_id
        if task_data:
            data["task"] = task_data

        return ToolResult(
            success=True,
            data=data,
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
