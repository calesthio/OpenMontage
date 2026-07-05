"""RunningHub-hosted Seedance-compatible video generation."""

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
from tools.video.seedance_constraints import (
    ALLOWED_RESOLUTIONS,
    ALLOWED_DURATIONS,
    DEFAULT_DURATION,
    DEFAULT_RESOLUTION,
    MAX_GENERATIONS_PER_BATCH,
    MAX_DURATION_SECONDS,
    seedance_duration,
    seedance_duration_seconds,
    seedance_resolution,
    validate_seedance_constraints,
)


RUNNINGHUB_BASE_URL = "https://www.runninghub.cn"
RUNNINGHUB_MODEL_PATHS = {
    "sparkvideo-2.0-mini": "/openapi/v2/rhart-video/sparkvideo-2.0-mini/multimodal-video",
}


def _listify(*values: Any) -> list[str]:
    out: list[str] = []
    for value in values:
        if not value:
            continue
        if isinstance(value, str):
            out.append(value)
        else:
            out.extend(str(item) for item in value if item)
    return out


def _file_to_data_uri(path: str) -> str:
    file_path = Path(path).expanduser()
    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _money_to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class RunningHubSeedanceVideo(BaseTool):
    name = "runninghub_seedance_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "runninghub"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies: list[str] = []
    install_instructions = (
        "Set RUNNINGHUB_API_KEY to your RunningHub enterprise shared API key."
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "multiple_reference_images": True,
        "reference_image": True,
        "native_audio": True,
        "camera_direction": True,
        "lip_sync": True,
        "multi_shot": True,
        "aspect_ratio": True,
        "seed": True,
        "max_duration_seconds": MAX_DURATION_SECONDS,
        "duration_seconds": [int(value) for value in ALLOWED_DURATIONS],
        "resolutions": list(ALLOWED_RESOLUTIONS),
        "max_generations_per_batch": MAX_GENERATIONS_PER_BATCH,
    }
    best_for = [
        "RunningHub-hosted Seedance-compatible creator-video clips",
        "Chinese creator workflows where RunningHub billing and access are preferred",
        "multimodal references with up to 9 images, 3 videos, and 3 audio clips",
        "real-person mode for reference assets that need stronger continuity",
    ]
    not_good_for = ["offline generation", "projects without RunningHub balance"]
    fallback_tools = ["seedance_video", "seedance_replicate", "kling_video", "minimax_video"]
    quality_score = 0.9

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
            "model_variant": {
                "type": "string",
                "enum": ["sparkvideo-2.0-mini"],
                "default": "sparkvideo-2.0-mini",
            },
            "duration": {
                "type": "string",
                "enum": list(ALLOWED_DURATIONS),
                "default": DEFAULT_DURATION,
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["adaptive", "16:9", "4:3", "1:1", "3:4", "9:16", "21:9"],
                "default": "adaptive",
            },
            "resolution": {
                "type": "string",
                "enum": list(ALLOWED_RESOLUTIONS),
                "default": DEFAULT_RESOLUTION,
            },
            "batch_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_GENERATIONS_PER_BATCH,
                "default": 1,
            },
            "generate_audio": {"type": "boolean", "default": True},
            "real_person_mode": {"type": "boolean", "default": True},
            "conversion_slots": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["all"],
            },
            "return_last_frame": {"type": "boolean", "default": False},
            "seed": {"type": "integer", "default": -1},
            "image_url": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "image_path": {"type": "string"},
            "image_paths": {"type": "array", "items": {"type": "string"}},
            "reference_image_url": {"type": "string"},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "reference_image_path": {"type": "string"},
            "reference_image_paths": {"type": "array", "items": {"type": "string"}},
            "video_url": {"type": "string"},
            "video_urls": {"type": "array", "items": {"type": "string"}},
            "video_path": {"type": "string"},
            "video_paths": {"type": "array", "items": {"type": "string"}},
            "reference_video_urls": {"type": "array", "items": {"type": "string"}},
            "reference_video_paths": {"type": "array", "items": {"type": "string"}},
            "audio_url": {"type": "string"},
            "audio_urls": {"type": "array", "items": {"type": "string"}},
            "audio_path": {"type": "string"},
            "audio_paths": {"type": "array", "items": {"type": "string"}},
            "reference_audio_urls": {"type": "array", "items": {"type": "string"}},
            "reference_audio_paths": {"type": "array", "items": {"type": "string"}},
            "timeout_seconds": {"type": "integer", "default": 900},
            "poll_interval_seconds": {"type": "number", "default": 5},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=512,
        vram_mb=0,
        disk_mb=500,
        network_required=True,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout", "RUNNING"])
    idempotency_key_fields = ["prompt", "model_variant", "duration", "aspect_ratio", "seed"]
    side_effects = ["writes video file to output_path", "calls RunningHub API"]
    user_visible_verification = [
        "Watch generated clip promptly because RunningHub result URLs expire after 24 hours",
    ]

    def _get_api_key(self) -> str | None:
        return os.environ.get("RUNNINGHUB_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._get_api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return max(60.0, seedance_duration_seconds(inputs) * 20.0)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="RUNNINGHUB_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        model_variant = inputs.get("model_variant", "sparkvideo-2.0-mini")
        if model_variant not in RUNNINGHUB_MODEL_PATHS:
            return ToolResult(
                success=False,
                error=f"Unknown RunningHub model_variant: {model_variant}",
            )
        constraint_error = validate_seedance_constraints(inputs)
        if constraint_error:
            return ToolResult(success=False, error=constraint_error)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        base_url = os.environ.get("RUNNINGHUB_BASE_URL", RUNNINGHUB_BASE_URL).rstrip("/")
        payload = self._build_payload(inputs)
        submit_url = f"{base_url}{RUNNINGHUB_MODEL_PATHS[model_variant]}"

        try:
            submit = requests.post(
                submit_url,
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit.raise_for_status()
            submit_data = submit.json()
            task_id = submit_data.get("taskId")
            if not task_id:
                return ToolResult(
                    success=False,
                    error=f"RunningHub response missing taskId: {submit_data}",
                )

            query_data = self._poll_result(
                requests=requests,
                base_url=base_url,
                headers=headers,
                task_id=task_id,
                timeout_seconds=int(inputs.get("timeout_seconds", 900)),
                poll_interval_seconds=float(inputs.get("poll_interval_seconds", 5)),
            )
            result_item = self._select_video_result(query_data)
            video_url = result_item["url"]
            video_response = requests.get(video_url, timeout=180)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "runninghub_seedance_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"RunningHub video generation failed: {exc}",
            )

        usage = query_data.get("usage") or {}
        cost = _money_to_float(usage.get("thirdPartyConsumeMoney")) or _money_to_float(
            usage.get("consumeMoney")
        )
        return ToolResult(
            success=True,
            data={
                "provider": "runninghub",
                "model": model_variant,
                "task_id": task_id,
                "prompt": inputs["prompt"],
                "operation": inputs.get("operation", "text_to_video"),
                "aspect_ratio": inputs.get("aspect_ratio", "adaptive"),
                "resolution": seedance_resolution(inputs),
                "duration": seedance_duration(inputs),
                "generate_audio": inputs.get("generate_audio", True),
                "real_person_mode": inputs.get("real_person_mode", True),
                "result_url": video_url,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": output_path.suffix.lower().lstrip(".") or "mp4",
                "usage": usage,
            },
            artifacts=[str(output_path)],
            cost_usd=cost,
            duration_seconds=round(time.time() - start, 2),
            seed=inputs.get("seed"),
            model=model_variant,
        )

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        image_urls = _listify(
            inputs.get("image_url"),
            inputs.get("image_urls"),
            inputs.get("reference_image_url"),
            inputs.get("reference_image_urls"),
        )
        for path in _listify(
            inputs.get("image_path"),
            inputs.get("image_paths"),
            inputs.get("reference_image_path"),
            inputs.get("reference_image_paths"),
        ):
            image_urls.append(_file_to_data_uri(path))

        video_urls = _listify(
            inputs.get("video_url"),
            inputs.get("video_urls"),
            inputs.get("reference_video_urls"),
        )
        for path in _listify(
            inputs.get("video_path"),
            inputs.get("video_paths"),
            inputs.get("reference_video_paths"),
        ):
            video_urls.append(_file_to_data_uri(path))

        audio_urls = _listify(
            inputs.get("audio_url"),
            inputs.get("audio_urls"),
            inputs.get("reference_audio_urls"),
        )
        for path in _listify(
            inputs.get("audio_path"),
            inputs.get("audio_paths"),
            inputs.get("reference_audio_paths"),
        ):
            audio_urls.append(_file_to_data_uri(path))

        if len(image_urls) > 9:
            raise ValueError(f"RunningHub accepts at most 9 image references; got {len(image_urls)}")
        if len(video_urls) > 3:
            raise ValueError(f"RunningHub accepts at most 3 video references; got {len(video_urls)}")
        if len(audio_urls) > 3:
            raise ValueError(f"RunningHub accepts at most 3 audio references; got {len(audio_urls)}")

        return {
            "prompt": inputs["prompt"],
            "resolution": seedance_resolution(inputs),
            "duration": seedance_duration(inputs),
            "imageUrls": image_urls,
            "videoUrls": video_urls,
            "audioUrls": audio_urls,
            "generateAudio": inputs.get("generate_audio", True),
            "ratio": inputs.get("aspect_ratio", "adaptive"),
            "realPersonMode": inputs.get("real_person_mode", True),
            "conversionSlots": inputs.get("conversion_slots", ["all"]),
            "returnLastFrame": inputs.get("return_last_frame", False),
            "seed": inputs.get("seed", -1),
        }

    def _poll_result(
        self,
        *,
        requests: Any,
        base_url: str,
        headers: dict[str, str],
        task_id: str,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        query_url = f"{base_url}/openapi/v2/query"
        while True:
            if time.time() > deadline:
                raise TimeoutError(f"RunningHub task {task_id} timed out")
            time.sleep(poll_interval_seconds)
            query = requests.post(
                query_url,
                headers=headers,
                json={"taskId": task_id},
                timeout=30,
            )
            query.raise_for_status()
            data = query.json()
            status = data.get("status")
            if status == "SUCCESS":
                return data
            if status == "FAILED":
                message = data.get("errorMessage") or data.get("errorCode") or data.get("failedReason")
                raise RuntimeError(f"RunningHub task {task_id} failed: {message}")
            if status not in {"QUEUED", "RUNNING"}:
                raise RuntimeError(f"RunningHub task {task_id} returned unknown status: {status}")

    def _select_video_result(self, query_data: dict[str, Any]) -> dict[str, Any]:
        results = query_data.get("results") or []
        for item in results:
            if str(item.get("outputType", "")).lower() == "mp4" and item.get("url"):
                return item
        for item in results:
            if item.get("url"):
                return item
        raise RuntimeError("RunningHub task succeeded but returned no downloadable result")
