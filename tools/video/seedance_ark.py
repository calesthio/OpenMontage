"""Direct Volcengine Ark adapter for the Seedance 2.0 and 2.5 model families.

The Ark API is asynchronous: create a task, poll its status, then download the
24-hour result URL immediately.  This provider is intentionally independent
from the existing fal.ai and Replicate Seedance adapters.
"""

from __future__ import annotations

import base64
import binascii
import io
import math
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

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


class SeedanceArkVideo(BaseTool):
    """Generate Seedance 2.0 video through Volcengine Ark's official REST API."""

    name = "seedance_ark"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "ark"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    MODEL_IDS = {
        "2.5": "doubao-seedance-2-5-260628",
        "standard": "doubao-seedance-2-0-260128",
        "fast": "doubao-seedance-2-0-fast-260128",
        "mini": "doubao-seedance-2-0-mini-260615",
    }
    TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
    TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled", "expired"})
    IMAGE_SUFFIX_TO_MIME = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".gif": "image/gif",
    }
    AUDIO_SUFFIX_TO_MIME = {
        ".wav": "audio/wav",
        ".mp3": "audio/mp3",
    }
    MAX_IMAGE_BYTES = 30 * 1024 * 1024
    MAX_AUDIO_BYTES = 15 * 1024 * 1024
    MAX_REQUEST_BYTES = 64 * 1024 * 1024

    # Official 2026-07-26 on-demand prices, CNY per million completion tokens.
    PRICE_CNY_PER_MILLION = {
        "standard": {
            "without_video": {
                "480p": 46.0,
                "720p": 46.0,
                "1080p": 51.0,
                "4k": 26.0,
            },
            "with_video": {
                "480p": 28.0,
                "720p": 28.0,
                "1080p": 31.0,
                "4k": 16.0,
            },
        },
        "fast": {
            "without_video": {"480p": 37.0, "720p": 37.0},
            "with_video": {"480p": 22.0, "720p": 22.0},
        },
        "mini": {
            "without_video": {"480p": 23.0, "720p": 23.0},
            "with_video": {"480p": 14.0, "720p": 14.0},
        },
    }
    OUTPUT_DIMENSIONS = {
        "480p": {
            "16:9": (864, 496),
            "4:3": (752, 560),
            "1:1": (640, 640),
            "3:4": (560, 752),
            "9:16": (496, 864),
            "21:9": (992, 432),
        },
        "720p": {
            "16:9": (1280, 720),
            "4:3": (1112, 834),
            "1:1": (960, 960),
            "3:4": (834, 1112),
            "9:16": (720, 1280),
            "21:9": (1470, 630),
        },
        "1080p": {
            "16:9": (1920, 1080),
            "4:3": (1664, 1248),
            "1:1": (1440, 1440),
            "3:4": (1248, 1664),
            "9:16": (1080, 1920),
            "21:9": (2206, 946),
        },
        "4k": {
            "16:9": (3840, 2160),
            "4:3": (3326, 2494),
            "1:1": (2880, 2880),
            "3:4": (2494, 3326),
            "9:16": (2160, 3840),
            "21:9": (4398, 1886),
        },
    }

    dependencies = ["env:ARK_API_KEY"]
    install_instructions = (
        "Set ARK_API_KEY to the API Key body from Volcengine Ark (without "
        "the 'Bearer ' prefix). Optional: ARK_SEEDANCE_MODEL and ARK_BASE_URL."
    )
    agent_skills = ["seedance-2-0", "seedance-2-5", "ai-video-gen"]

    capabilities = [
        "text_to_video",
        "image_to_video",
        "reference_to_video",
        "task_create",
        "task_query",
        "task_cancel",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "multiple_reference_images": True,
        "reference_image": True,
        "reference_video": True,
        "reference_audio": True,
        "native_audio": True,
        "local_image_data_uri": True,
        "local_audio_data_uri": True,
        "local_video": False,
        "return_last_frame": True,
        "web_search": True,
        "aspect_ratio": True,
    }
    best_for = [
        "direct Volcengine Ark Seedance 2.0 generation without a gateway",
        "multimodal reference video with native synchronized audio",
        "Standard 1080p or 4K output and Fast/Mini lower-cost output",
    ]
    not_good_for = [
        "offline generation",
        "unapproved paid generation",
        "direct local reference-video upload",
    ]
    fallback_tools = ["seedance_video", "seedance_replicate", "jimeng_video"]

    input_schema = {
        "type": "object",
        "properties": {
            "task_action": {
                "type": "string",
                "enum": ["generate", "create", "query", "cancel"],
                "default": "generate",
            },
            "task_id": {
                "type": "string",
                "description": "Required for task_action=query/cancel.",
            },
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "model_variant": {
                "type": "string",
                "enum": ["2.5", "standard", "fast", "mini"],
                "default": "standard",
            },
            "model": {
                "type": "string",
                "description": (
                    "Optional Ark Model ID or Endpoint ID. Overrides "
                    "ARK_SEEDANCE_MODEL and model_variant."
                ),
            },
            "custom_price_cny_per_million_tokens": {
                "type": "number",
                "exclusiveMinimum": 0,
                "description": (
                    "Required for a custom Endpoint or unknown future model "
                    "so budget checks never treat unknown pricing as free."
                ),
            },
            "duration": {
                "description": "Integer seconds 4-15, or -1/'auto'.",
                "default": 5,
            },
            "aspect_ratio": {
                "type": "string",
                "enum": [
                    "adaptive",
                    "21:9",
                    "16:9",
                    "4:3",
                    "1:1",
                    "3:4",
                    "9:16",
                ],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "1080p", "4k"],
                "default": "720p",
            },
            "generate_audio": {"type": "boolean", "default": True},
            "watermark": {"type": "boolean", "default": False},
            "return_last_frame": {"type": "boolean", "default": False},
            "callback_url": {"type": "string"},
            "execution_expires_after": {
                "type": "integer",
                "minimum": 3600,
                "maximum": 259200,
            },
            "priority": {"type": "integer", "minimum": 0, "maximum": 9},
            "safety_identifier": {"type": "string", "maxLength": 64},
            "web_search": {
                "type": "boolean",
                "description": "Officially limited to pure text input.",
            },
            "reference_image_path": {"type": "string"},
            "reference_image_url": {"type": "string"},
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
            },
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
            },
            "end_image_path": {"type": "string"},
            "end_image_url": {"type": "string"},
            "reference_video_url": {"type": "string"},
            "reference_video_urls": {
                "type": "array",
                "items": {"type": "string"},
            },
            "reference_video_path": {
                "type": "string",
                "description": "Rejected: Ark does not document video Base64.",
            },
            "reference_video_durations": {
                "type": "array",
                "items": {"type": "number", "minimum": 2, "maximum": 15},
                "description": "Optional durations used for preflight cost estimation.",
            },
            "reference_audio_url": {"type": "string"},
            "reference_audio_urls": {
                "type": "array",
                "items": {"type": "string"},
            },
            "reference_audio_path": {"type": "string"},
            "reference_audio_paths": {
                "type": "array",
                "items": {"type": "string"},
            },
            "reference_audio_durations": {
                "type": "array",
                "items": {"type": "number", "minimum": 2, "maximum": 15},
                "description": (
                    "Optional durations for remote audio preflight; local "
                    "audio is probed automatically."
                ),
            },
            "poll_interval_seconds": {
                "type": "number",
                "minimum": 0,
                "maximum": 60,
                "default": 3,
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 1,
                "default": 1200,
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=512,
        vram_mb=0,
        disk_mb=2048,
        network_required=True,
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["rate_limit", "timeout", "server_error"],
    )
    idempotency_key_fields = [
        "prompt",
        "operation",
        "model_variant",
        "model",
        "duration",
        "aspect_ratio",
        "resolution",
        "generate_audio",
        "watermark",
        "reference_image_url",
        "reference_image_path",
        "reference_image_urls",
        "reference_image_paths",
        "reference_video_urls",
        "reference_audio_urls",
    ]
    side_effects = [
        "submits a paid task to the Volcengine Ark API",
        "writes the completed video to output_path",
    ]
    user_visible_verification = [
        "Watch the downloaded clip for visual continuity and synchronized audio",
        "Confirm the local artifact before the 24-hour remote URL expires",
    ]

    def _get_api_key(self) -> str | None:
        return os.environ.get("ARK_API_KEY")

    def _get_base_url(self) -> str:
        base_url = os.environ.get("ARK_BASE_URL", self.BASE_URL).rstrip("/")
        if not base_url.startswith("https://"):
            raise ValueError("ARK_BASE_URL must be an https:// URL")
        return base_url

    def get_status(self) -> ToolStatus:
        api_key = self._get_api_key()
        if not api_key or api_key.lower().startswith("bearer "):
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_token_usage(self, inputs: dict[str, Any]) -> int:
        """Estimate billable completion tokens using Ark's published formula."""
        _, variant = self._resolve_model(inputs)
        max_duration = 30 if variant == "2.5" else 15
        duration = self._normalize_duration(inputs.get("duration", 5), max_duration)
        output_seconds = max_duration if duration == -1 else duration
        video_refs = list(inputs.get("reference_video_urls") or [])
        if inputs.get("reference_video_url"):
            video_refs.append(inputs["reference_video_url"])
        video_durations = list(inputs.get("reference_video_durations") or [])
        # A video reference changes both the token formula and the price tier.
        # When duration metadata is absent, use the official 15-second combined
        # maximum as a conservative preflight upper bound instead of reporting
        # a deceptively cheap output-only estimate.
        if video_refs and len(video_durations) != len(video_refs):
            input_video_seconds = 15.0
        else:
            input_video_seconds = sum(float(value) for value in video_durations)
        resolution = str(inputs.get("resolution", "720p")).lower()
        ratio = str(inputs.get("aspect_ratio", "16:9"))
        if ratio == "adaptive":
            ratio = "16:9"
        width, height = self.OUTPUT_DIMENSIONS[resolution][ratio]
        return round(
            (input_video_seconds + output_seconds) * width * height * 24 / 1024
        )

    def estimate_cost_cny(self, inputs: dict[str, Any]) -> float:
        model, variant = self._resolve_model(inputs)
        del model
        if variant is None or variant == "2.5":
            rate = self._get_custom_price(inputs, required=True)
            return round(
                self.estimate_token_usage(inputs) * rate / 1_000_000,
                4,
            )
        resolution = str(inputs.get("resolution", "720p")).lower()
        with_video = bool(
            inputs.get("reference_video_url") or inputs.get("reference_video_urls")
        )
        condition = "with_video" if with_video else "without_video"
        try:
            rate = self.PRICE_CNY_PER_MILLION[variant][condition][resolution]
        except KeyError:
            # A custom Endpoint/Model may have different pricing.  Returning
            # zero is safer than presenting a fabricated official estimate.
            return 0.0
        return round(self.estimate_token_usage(inputs) * rate / 1_000_000, 4)

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        cny_per_usd = self._get_cny_per_usd()
        return round(self.estimate_cost_cny(inputs) / cny_per_usd, 4)

    @staticmethod
    def _get_custom_price(inputs: dict[str, Any], *, required: bool) -> float:
        try:
            raw = inputs["custom_price_cny_per_million_tokens"]
        except KeyError as exc:
            if not required:
                return 0.0
            raise ValueError(
                "pricing is unknown for a custom Ark Endpoint/Model; "
                "set custom_price_cny_per_million_tokens before a paid create"
            ) from exc
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "custom_price_cny_per_million_tokens must be a finite "
                "number greater than 0"
            ) from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError(
                "custom_price_cny_per_million_tokens must be a finite "
                "number greater than 0"
            )
        return value

    @staticmethod
    def _get_cny_per_usd() -> float:
        try:
            value = float(os.environ.get("ARK_CNY_PER_USD", "7.2"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "ARK_CNY_PER_USD must be a finite number greater than 0"
            ) from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError("ARK_CNY_PER_USD must be a finite number greater than 0")
        return value

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        _, variant = self._resolve_model(inputs)
        return 90.0 if variant in {"fast", "mini"} else 180.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate and estimate locally; never submit Ark's paid POST."""
        action = str(inputs.get("task_action", "generate"))
        result: dict[str, Any] = {
            "tool": self.name,
            "task_action": action,
            "status": self.get_status().value,
            "would_execute": False,
            "paid_submission": False,
            "api_contract": {
                "create": f"POST {self.BASE_URL}/contents/generations/tasks",
                "query": (
                    f"GET {self.BASE_URL}/contents/generations/tasks/{{task_id}}"
                ),
                "cancel": (
                    f"DELETE {self.BASE_URL}/contents/generations/tasks/{{task_id}}"
                ),
            },
        }
        try:
            base_url = self._get_base_url()
            api_key = self._get_api_key()
            if api_key and api_key.lower().startswith("bearer "):
                raise ValueError(
                    "ARK_API_KEY must contain only the API Key body; remove "
                    "the 'Bearer ' prefix"
                )
            result["api_contract"] = {
                "create": (f"POST {base_url}/contents/generations/tasks"),
                "query": (f"GET {base_url}/contents/generations/tasks/{{task_id}}"),
                "cancel": (f"DELETE {base_url}/contents/generations/tasks/{{task_id}}"),
            }
            if action in {"query", "cancel"}:
                self._validate_task_id(inputs.get("task_id"))
            else:
                payload = self._build_payload(inputs)
                result.update(
                    {
                        "model": payload["model"],
                        "operation": inputs.get("operation", "text_to_video"),
                        "resolution": payload.get("resolution", "720p"),
                        "ratio": payload.get("ratio", "16:9"),
                        "duration": payload.get("duration", 5),
                        "generate_audio": payload.get("generate_audio", True),
                        "media_counts": self._media_counts(payload["content"]),
                        "estimated_tokens": self.estimate_token_usage(inputs),
                        "estimated_cost_cny": self.estimate_cost_cny(inputs),
                        "estimated_cost_usd": self.estimate_cost(inputs),
                        "cost_estimate_note": (
                            "Official formula estimate; actual usage comes "
                            "from usage.completion_tokens and minimum billable "
                            "tokens may apply. Missing reference-video duration "
                            "is estimated at the official 15-second maximum."
                        ),
                        "cost_estimate_status": (
                            "unknown_custom_model"
                            if self._resolve_model(inputs)[1] is None
                            else "estimated"
                        ),
                    }
                )
            result["valid"] = True
        except (TypeError, ValueError, OSError) as exc:
            result["valid"] = False
            result["error"] = self._safe_error(exc)
        return result

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        """Create, query, cancel, or synchronously finish an Ark task."""
        started = time.time()
        action = str(inputs.get("task_action", "generate"))
        task_id: str | None = None
        estimated_cost_usd = 0.0
        try:
            if action not in {"generate", "create", "query", "cancel"}:
                raise ValueError(
                    "task_action must be generate, create, query, or cancel"
                )
            if action in {"query", "cancel"}:
                self._validate_task_id(inputs.get("task_id"))
            else:
                payload = self._build_payload(inputs)
                # Complete all local cost/config parsing before the paid POST.
                # A malformed exchange-rate override must never create an
                # untracked task and then fail while constructing ToolResult.
                estimated_cost_usd = self.estimate_cost(inputs)
        except (TypeError, ValueError, OSError) as exc:
            return ToolResult(success=False, error=self._safe_error(exc))

        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="ARK_API_KEY not set. " + self.install_instructions,
            )
        if api_key.lower().startswith("bearer "):
            return ToolResult(
                success=False,
                error=(
                    "ARK_API_KEY must contain only the API Key body; remove "
                    "the 'Bearer ' prefix"
                ),
            )

        try:
            if action == "query":
                task = self._query_task(str(inputs["task_id"]), api_key)
                actual_cost_usd = self._cost_from_task(task, inputs)
                cost_status = (
                    "actual_from_usage"
                    if actual_cost_usd is not None
                    else "unknown_custom_model_or_missing_usage"
                )
                return ToolResult(
                    success=True,
                    data={
                        "task": task,
                        "cost_estimate_status": cost_status,
                    },
                    cost_usd=actual_cost_usd,  # type: ignore[arg-type]
                    model=task.get("model"),
                )

            if action == "cancel":
                task_id = str(inputs["task_id"])
                self._cancel_task(task_id, api_key)
                return ToolResult(
                    success=True,
                    data={
                        "task_id": task_id,
                        "status": "cancel_requested",
                    },
                )

            task_id = self._create_task(payload, api_key)
            model = str(payload["model"])
            if action == "create":
                return ToolResult(
                    success=True,
                    data={
                        "task_id": task_id,
                        "status": "submitted",
                        "provider": self.provider,
                        "model": model,
                    },
                    cost_usd=estimated_cost_usd,
                    model=model,
                )

            task = self._poll_task(task_id, api_key, inputs)
            status = str(task.get("status", "")).lower()
            if status != "succeeded":
                detail = self._task_error(task)
                safe_detail = (
                    self._safe_error(RuntimeError(detail), api_key) if detail else ""
                )
                return ToolResult(
                    success=False,
                    data={"task_id": task_id, "status": status},
                    error=(
                        f"Ark Seedance task {status or 'failed'}"
                        + (f": {safe_detail}" if safe_detail else "")
                    ),
                    duration_seconds=round(time.time() - started, 2),
                    model=str(task.get("model") or model),
                )

            content = task.get("content") or {}
            video_url = content.get("video_url")
            if not video_url:
                raise RuntimeError("Ark task succeeded without content.video_url")
            output_path = Path(inputs.get("output_path", "seedance_ark_output.mp4"))
            self._download_video(str(video_url), output_path)

            from tools.video._shared import probe_output

            probed = probe_output(output_path)
            cost_usd = self._cost_from_task(task, inputs)
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "task_id": task_id,
                    "status": status,
                    "model": task.get("model") or model,
                    "prompt": inputs.get("prompt"),
                    "operation": inputs.get("operation", "text_to_video"),
                    "video_url": video_url,
                    "last_frame_url": content.get("last_frame_url"),
                    "output": str(output_path),
                    "output_path": str(output_path),
                    "format": "mp4",
                    "resolution": task.get("resolution", payload.get("resolution")),
                    "aspect_ratio": task.get("ratio", payload.get("ratio")),
                    "duration": task.get("duration", payload.get("duration")),
                    "generate_audio": task.get("generate_audio"),
                    "usage": task.get("usage") or {},
                    "estimated_cost_cny": self._cost_from_task_cny(task, inputs),
                    **probed,
                },
                artifacts=[str(output_path)],
                cost_usd=cost_usd,
                duration_seconds=round(time.time() - started, 2),
                model=str(task.get("model") or model),
            )
        except Exception as exc:
            error_data: dict[str, Any] = {}
            if task_id:
                error_data = {
                    "task_id": task_id,
                    "status": "submitted_result_unknown",
                    "recovery_action": "query",
                }
            elif action in {"query", "cancel"} and inputs.get("task_id"):
                error_data = {"task_id": str(inputs["task_id"])}
            return ToolResult(
                success=False,
                data=error_data,
                error=(
                    f"Ark Seedance request failed: {self._safe_error(exc, api_key)}"
                ),
                duration_seconds=round(time.time() - started, 2),
            )

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        operation = str(inputs.get("operation", "text_to_video"))
        if operation not in {
            "text_to_video",
            "image_to_video",
            "reference_to_video",
        }:
            raise ValueError(
                "operation must be text_to_video, image_to_video, or reference_to_video"
            )

        model, variant = self._resolve_model(inputs)
        resolution = str(inputs.get("resolution", "720p")).lower()
        if resolution not in self.OUTPUT_DIMENSIONS:
            raise ValueError("resolution must be 480p, 720p, 1080p, or 4k")
        if variant in {"2.5", "fast", "mini"} and resolution not in {
            "480p",
            "720p",
        }:
            raise ValueError(f"{variant} supports only 480p or 720p resolution")

        ratio = str(inputs.get("aspect_ratio", "16:9"))
        valid_ratios = {
            "adaptive",
            "21:9",
            "16:9",
            "4:3",
            "1:1",
            "3:4",
            "9:16",
        }
        if ratio not in valid_ratios:
            raise ValueError(
                "aspect_ratio must be adaptive, 21:9, 16:9, 4:3, 1:1, 3:4, or 9:16"
            )

        max_duration = 30 if variant == "2.5" else 15
        duration = self._normalize_duration(inputs.get("duration", 5), max_duration)
        prompt = str(inputs.get("prompt") or "").strip()
        content: list[dict[str, Any]] = []
        if prompt:
            content.append({"type": "text", "text": prompt})

        if inputs.get("reference_video_path"):
            raise ValueError(
                "reference_video_path is not supported by Ark; upload the "
                "video to a public/signed HTTPS URL or Ark asset first"
            )

        if operation == "text_to_video":
            if not prompt:
                raise ValueError("prompt is required for text_to_video")
            if self._has_any_media(inputs):
                raise ValueError(
                    "text_to_video does not accept reference media; use "
                    "image_to_video or reference_to_video"
                )
        elif operation == "image_to_video":
            first_refs = self._single_image_refs(inputs)
            if len(first_refs) != 1:
                raise ValueError("image_to_video requires exactly one reference image")
            content.append(self._image_content(first_refs[0], role="first_frame"))
            end_refs = [
                value
                for value in (
                    inputs.get("end_image_url"),
                    inputs.get("end_image_path"),
                )
                if value
            ]
            if len(end_refs) > 1:
                raise ValueError("provide only one of end_image_url/end_image_path")
            if end_refs:
                content.append(self._image_content(end_refs[0], role="last_frame"))
        else:
            image_refs = list(inputs.get("reference_image_urls") or [])
            image_refs.extend(inputs.get("reference_image_paths") or [])
            if inputs.get("reference_image_url"):
                image_refs.append(inputs["reference_image_url"])
            if inputs.get("reference_image_path"):
                image_refs.append(inputs["reference_image_path"])
            max_images = 30 if variant == "2.5" else 9
            max_videos = 10 if variant == "2.5" else 3
            max_audios = 10 if variant == "2.5" else 3
            max_reference_seconds = 30 if variant == "2.5" else 15
            if len(image_refs) > max_images:
                raise ValueError(
                    f"reference_to_video accepts at most {max_images} reference images"
                )

            video_refs = list(inputs.get("reference_video_urls") or [])
            if inputs.get("reference_video_url"):
                video_refs.append(inputs["reference_video_url"])
            if len(video_refs) > max_videos:
                raise ValueError(
                    f"reference_to_video accepts at most {max_videos} reference videos"
                )
            self._validate_remote_refs(video_refs, "reference video")
            video_durations = list(inputs.get("reference_video_durations") or [])
            if video_durations:
                if len(video_durations) != len(video_refs):
                    raise ValueError(
                        "reference_video_durations must match the number of "
                        "reference videos"
                    )
                if any(
                    float(value) < 2 or float(value) > max_reference_seconds
                    for value in video_durations
                ):
                    raise ValueError(
                        f"each reference video duration must be 2 to {max_reference_seconds} seconds"
                    )
                if (
                    sum(float(value) for value in video_durations)
                    > max_reference_seconds
                ):
                    raise ValueError(
                        "all reference videos together must be at most "
                        f"{max_reference_seconds} seconds"
                    )

            audio_refs = list(inputs.get("reference_audio_urls") or [])
            audio_refs.extend(inputs.get("reference_audio_paths") or [])
            if inputs.get("reference_audio_url"):
                audio_refs.append(inputs["reference_audio_url"])
            if inputs.get("reference_audio_path"):
                audio_refs.append(inputs["reference_audio_path"])
            if len(audio_refs) > max_audios:
                raise ValueError(
                    "reference_to_video accepts at most 3 reference audio "
                    f"clips (maximum {max_audios})"
                )
            audio_durations = list(inputs.get("reference_audio_durations") or [])
            if audio_durations:
                if len(audio_durations) != len(audio_refs):
                    raise ValueError(
                        "reference_audio_durations must match the number of "
                        "reference audio clips"
                    )
                if any(
                    float(value) < 2 or float(value) > max_reference_seconds
                    for value in audio_durations
                ):
                    raise ValueError(
                        f"each reference audio duration must be 2 to {max_reference_seconds} seconds"
                    )
                if (
                    sum(float(value) for value in audio_durations)
                    > max_reference_seconds
                ):
                    raise ValueError(
                        "all reference audio clips together must be at most "
                        f"{max_reference_seconds} seconds"
                    )
            local_audio_durations = [
                duration
                for ref in audio_refs
                if (
                    duration := self._local_or_data_audio_duration(
                        str(ref), max_seconds=max_reference_seconds
                    )
                )
                is not None
            ]
            if sum(local_audio_durations) > max_reference_seconds:
                raise ValueError(
                    "all local reference audio clips together must be at "
                    f"most {max_reference_seconds} seconds"
                )
            if audio_refs and not (image_refs or video_refs):
                raise ValueError(
                    "reference audio requires at least one reference image or video"
                )
            if not (image_refs or video_refs):
                raise ValueError(
                    "reference_to_video requires at least one image or video"
                )

            content.extend(
                self._image_content(ref, role="reference_image") for ref in image_refs
            )
            content.extend(
                {
                    "type": "video_url",
                    "video_url": {"url": str(ref)},
                    "role": "reference_video",
                }
                for ref in video_refs
            )
            content.extend(
                self._audio_content(ref, role="reference_audio") for ref in audio_refs
            )

        if inputs.get("web_search") and len(content) != 1:
            raise ValueError("web_search is supported only for pure text input")

        payload: dict[str, Any] = {
            "model": model,
            "content": content,
            "duration": duration,
            "ratio": ratio,
            "resolution": resolution,
            "generate_audio": bool(inputs.get("generate_audio", True)),
            "watermark": bool(inputs.get("watermark", False)),
            "return_last_frame": bool(inputs.get("return_last_frame", False)),
        }
        optional = (
            "callback_url",
            "execution_expires_after",
            "priority",
            "safety_identifier",
        )
        for key in optional:
            if inputs.get(key) is not None:
                payload[key] = inputs[key]
        if inputs.get("web_search"):
            payload["tools"] = [{"type": "web_search"}]

        self._validate_optional_parameters(payload)
        self._validate_request_size(payload)
        return payload

    def _resolve_model(self, inputs: dict[str, Any]) -> tuple[str, str | None]:
        variant = str(inputs.get("model_variant", "standard")).lower()
        if variant not in self.MODEL_IDS:
            raise ValueError("model_variant must be 2.5, standard, fast, or mini")
        model = str(
            inputs.get("model")
            or os.environ.get("ARK_SEEDANCE_MODEL")
            or self.MODEL_IDS[variant]
        )
        if not model or any(char.isspace() for char in model):
            raise ValueError("model must be a non-empty Ark Model/Endpoint ID")
        for known_variant, known_model in self.MODEL_IDS.items():
            if model == known_model:
                return model, known_variant
        # Endpoint IDs and future model IDs can have account-specific pricing.
        # Keep the caller's requested model, but never pretend its price is the
        # public price of model_variant.
        return model, None

    @staticmethod
    def _normalize_duration(value: Any, max_seconds: int = 15) -> int:
        if value == "auto":
            return -1
        if isinstance(value, bool):
            raise ValueError(
                f"duration must be an integer from 4 to {max_seconds} or -1"
            )
        try:
            duration = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"duration must be an integer from 4 to {max_seconds} or -1"
            ) from exc
        if str(value).strip() not in {str(duration), "auto"}:
            raise ValueError(
                f"duration must be an integer from 4 to {max_seconds} or -1"
            )
        if duration != -1 and not 4 <= duration <= max_seconds:
            raise ValueError(f"duration must be between 4 and {max_seconds} or -1")
        return duration

    @staticmethod
    def _single_image_refs(inputs: dict[str, Any]) -> list[Any]:
        refs = [
            inputs.get("reference_image_url") or inputs.get("image_url"),
            inputs.get("reference_image_path") or inputs.get("image_path"),
        ]
        return [ref for ref in refs if ref]

    @staticmethod
    def _has_any_media(inputs: dict[str, Any]) -> bool:
        keys = (
            "reference_image_url",
            "reference_image_path",
            "reference_image_urls",
            "reference_image_paths",
            "reference_video_url",
            "reference_video_path",
            "reference_video_urls",
            "reference_audio_url",
            "reference_audio_path",
            "reference_audio_urls",
            "reference_audio_paths",
            "image_url",
            "image_path",
            "end_image_url",
            "end_image_path",
        )
        return any(inputs.get(key) for key in keys)

    def _image_content(self, ref: Any, *, role: str) -> dict[str, Any]:
        url = self._media_url(
            ref,
            suffix_to_mime=self.IMAGE_SUFFIX_TO_MIME,
            max_bytes=self.MAX_IMAGE_BYTES,
            label="image",
        )
        return {
            "type": "image_url",
            "image_url": {"url": url},
            "role": role,
        }

    def _audio_content(self, ref: Any, *, role: str) -> dict[str, Any]:
        url = self._media_url(
            ref,
            suffix_to_mime=self.AUDIO_SUFFIX_TO_MIME,
            max_bytes=self.MAX_AUDIO_BYTES,
            label="audio",
        )
        return {
            "type": "audio_url",
            "audio_url": {"url": url},
            "role": role,
        }

    def _media_url(
        self,
        ref: Any,
        *,
        suffix_to_mime: dict[str, str],
        max_bytes: int,
        label: str,
    ) -> str:
        value = str(ref)
        if value.startswith("data:"):
            return self._validate_data_uri(
                value,
                suffix_to_mime=suffix_to_mime,
                max_bytes=max_bytes,
                label=label,
            )
        if self._is_remote_or_asset(value):
            return value
        path = Path(value).expanduser()
        if not path.is_file():
            raise ValueError(
                f"{label} reference must be a public URL, asset:// ID, "
                f"or existing local file: {value}"
            )
        size = path.stat().st_size
        if size >= max_bytes:
            raise ValueError(
                f"local {label} must be smaller than {max_bytes // (1024 * 1024)} MB"
            )
        suffix = path.suffix.lower()
        mime = suffix_to_mime.get(suffix)
        if not mime:
            guessed, _ = mimetypes.guess_type(path.name)
            mime = guessed if guessed in suffix_to_mime.values() else None
        if not mime:
            formats = ", ".join(sorted(suffix_to_mime))
            raise ValueError(
                f"unsupported local {label} format; expected one of {formats}"
            )
        if label == "image":
            self._validate_local_image(path)
        elif label == "audio":
            self._probe_local_audio_duration(path)
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _validate_local_image(self, path: Path) -> None:
        self._validate_image_bytes(path.read_bytes(), str(path))

    @staticmethod
    def _validate_image_bytes(data: bytes, source: str) -> None:
        try:
            from PIL import Image

            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
                image.verify()
        except Exception as exc:
            raise ValueError(f"image is unreadable or corrupt: {source}") from exc
        if not (300 <= width <= 6000 and 300 <= height <= 6000):
            raise ValueError(
                "local image width and height must each be 300 to 6000 pixels"
            )
        ratio = width / height
        if not 0.4 <= ratio <= 2.5:
            raise ValueError(
                "local image width/height ratio must be between 0.4 and 2.5"
            )

    def _validate_data_uri(
        self,
        value: str,
        *,
        suffix_to_mime: dict[str, str],
        max_bytes: int,
        label: str,
    ) -> str:
        mime, decoded = self._decode_data_uri(
            value,
            suffix_to_mime=suffix_to_mime,
            max_bytes=max_bytes,
            label=label,
        )
        if label == "image":
            self._validate_image_bytes(decoded, "Data URI")
        elif label == "audio":
            self._probe_audio_bytes(decoded, mime)
        return value

    @staticmethod
    def _decode_data_uri(
        value: str,
        *,
        suffix_to_mime: dict[str, str],
        max_bytes: int,
        label: str,
    ) -> tuple[str, bytes]:
        match = re.fullmatch(
            r"data:([a-z]+/[a-z0-9.+-]+);base64,([A-Za-z0-9+/=]+)",
            value,
            flags=re.IGNORECASE,
        )
        if not match:
            raise ValueError(
                f"{label} Data URI must use a supported MIME type and "
                "strict base64 encoding"
            )
        mime = match.group(1).lower()
        if mime not in set(suffix_to_mime.values()):
            raise ValueError(f"unsupported {label} Data URI MIME type: {mime}")
        try:
            decoded = base64.b64decode(match.group(2), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError(f"invalid base64 in {label} Data URI") from exc
        if len(decoded) >= max_bytes:
            raise ValueError(
                f"decoded {label} Data URI must be smaller than "
                f"{max_bytes // (1024 * 1024)} MB"
            )
        return mime, decoded

    def _local_or_data_audio_duration(
        self, value: str, *, max_seconds: int = 15
    ) -> float | None:
        if value.startswith("data:"):
            mime, decoded = self._decode_data_uri(
                value,
                suffix_to_mime=self.AUDIO_SUFFIX_TO_MIME,
                max_bytes=self.MAX_AUDIO_BYTES,
                label="audio",
            )
            return self._probe_audio_bytes(decoded, mime, max_seconds=max_seconds)
        if self._is_remote_or_asset(value):
            return None
        return self._probe_local_audio_duration(
            Path(value).expanduser(), max_seconds=max_seconds
        )

    def _probe_audio_bytes(
        self, decoded: bytes, mime: str, *, max_seconds: int = 15
    ) -> float:
        suffix = ".wav" if mime == "audio/wav" else ".mp3"
        # Windows does not allow ffprobe to reopen a NamedTemporaryFile while
        # Python still holds the file handle. Close it before probing, then
        # remove it explicitly on every path.
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temp.write(decoded)
            temp.flush()
            temp_path = Path(temp.name)
        try:
            return self._probe_local_audio_duration(temp_path, max_seconds=max_seconds)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _probe_local_audio_duration(path: Path, *, max_seconds: int = 15) -> float:
        if not path.is_file():
            raise ValueError(f"local audio file does not exist: {path}")
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise ValueError("ffprobe is required to validate local reference audio")
        try:
            proc = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            duration = float(proc.stdout.strip()) if proc.returncode == 0 else 0
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise ValueError(f"failed to probe local reference audio: {path}") from exc
        if not 2 <= duration <= max_seconds:
            raise ValueError(
                f"each local reference audio clip must be 2 to {max_seconds} seconds"
            )
        return duration

    @staticmethod
    def _is_remote_or_asset(value: str) -> bool:
        return value.startswith(("https://", "http://", "asset://"))

    def _validate_remote_refs(self, refs: list[Any], label: str) -> None:
        for ref in refs:
            value = str(ref)
            if not value.startswith(("https://", "http://", "asset://")):
                raise ValueError(
                    f"{label} must be a public/signed URL or asset:// ID; "
                    "Ark does not document video Base64 or local paths"
                )

    def _validate_optional_parameters(self, payload: dict[str, Any]) -> None:
        callback = payload.get("callback_url")
        if callback is not None and not str(callback).startswith(
            ("https://", "http://")
        ):
            raise ValueError("callback_url must be an http(s) URL")
        expires = payload.get("execution_expires_after")
        if expires is not None and not 3600 <= int(expires) <= 259200:
            raise ValueError("execution_expires_after must be between 3600 and 259200")
        priority = payload.get("priority")
        if priority is not None and not 0 <= int(priority) <= 9:
            raise ValueError("priority must be between 0 and 9")
        safety = payload.get("safety_identifier")
        if safety is not None and len(str(safety)) > 64:
            raise ValueError("safety_identifier must be at most 64 characters")

    def _validate_request_size(self, payload: dict[str, Any]) -> None:
        # Base64 dominates request size; summing encoded media is a conservative
        # lower-cost check that avoids building a second complete JSON string.
        encoded_bytes = 0
        for item in payload["content"]:
            media = (
                item.get("image_url")
                or item.get("audio_url")
                or item.get("video_url")
                or {}
            )
            url = str(media.get("url", ""))
            if url.startswith("data:"):
                encoded_bytes += len(url.encode("ascii"))
        if encoded_bytes >= self.MAX_REQUEST_BYTES:
            raise ValueError("Ark request body must be smaller than 64 MB")

    @staticmethod
    def _media_counts(content: list[dict[str, Any]]) -> dict[str, int]:
        return {
            kind: sum(1 for item in content if item.get("type") == kind)
            for kind in ("text", "image_url", "video_url", "audio_url")
        }

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _create_task(self, payload: dict[str, Any], api_key: str) -> str:
        import requests

        response = requests.post(
            f"{self._get_base_url()}/contents/generations/tasks",
            headers=self._headers(api_key),
            json=payload,
            timeout=30,
        )
        self._raise_for_status(response)
        data = response.json()
        task_id = data.get("id")
        self._validate_task_id(task_id)
        return str(task_id)

    def _query_task(self, task_id: str, api_key: str) -> dict[str, Any]:
        import requests

        url = f"{self._get_base_url()}/contents/generations/tasks/{task_id}"
        response = None
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                response = requests.get(
                    url,
                    headers=self._headers(api_key),
                    timeout=30,
                )
                retryable_status = (
                    response.status_code == 429 or response.status_code >= 500
                )
                if retryable_status and attempt < self.retry_policy.max_retries:
                    time.sleep(self.retry_policy.backoff_seconds * (2**attempt))
                    continue
                self._raise_for_status(response)
                break
            except requests.RequestException:
                if attempt >= self.retry_policy.max_retries:
                    raise
                time.sleep(self.retry_policy.backoff_seconds * (2**attempt))
        if response is None:
            raise RuntimeError("Ark query returned no response")
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Ark query returned a non-object response")
        return data

    def _cancel_task(self, task_id: str, api_key: str) -> None:
        import requests

        response = requests.delete(
            f"{self._get_base_url()}/contents/generations/tasks/{task_id}",
            headers=self._headers(api_key),
            timeout=30,
        )
        # The official DELETE success body is undefined and may be empty.
        self._raise_for_status(response)

    def _poll_task(
        self,
        task_id: str,
        api_key: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        interval = float(inputs.get("poll_interval_seconds", 3))
        timeout = float(inputs.get("timeout_seconds", 1200))
        if not 0 <= interval <= 60:
            raise ValueError("poll_interval_seconds must be between 0 and 60")
        if timeout <= 0:
            raise ValueError("timeout_seconds must be greater than 0")
        deadline = time.monotonic() + timeout
        while True:
            task = self._query_task(task_id, api_key)
            status = str(task.get("status", "")).lower()
            if status in self.TERMINAL_STATUSES:
                return task
            if status not in {"queued", "running"}:
                raise RuntimeError(
                    f"Ark returned unknown task status: {status or '<empty>'}"
                )
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Ark task {task_id} did not finish within {timeout}s"
                )
            time.sleep(interval)

    @staticmethod
    def _download_video(video_url: str, output_path: Path) -> None:
        import requests

        response = requests.get(video_url, timeout=120)
        response.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        partial = output_path.with_name(output_path.name + ".part")
        partial.write_bytes(response.content)
        partial.replace(output_path)

    @staticmethod
    def _validate_task_id(task_id: Any) -> None:
        value = str(task_id or "")
        if not SeedanceArkVideo.TASK_ID_PATTERN.fullmatch(value):
            raise ValueError("task_id is missing or invalid")

    @staticmethod
    def _raise_for_status(response: Any) -> None:
        try:
            response.raise_for_status()
        except Exception as exc:
            detail = ""
            try:
                payload = response.json()
                error = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(error, dict):
                    detail = ": ".join(
                        str(error.get(key))
                        for key in ("code", "message")
                        if error.get(key)
                    )
            except Exception:
                pass
            raise RuntimeError(f"{exc}" + (f"; {detail}" if detail else "")) from exc

    @staticmethod
    def _task_error(task: dict[str, Any]) -> str:
        error = task.get("error")
        if isinstance(error, dict):
            return ": ".join(
                str(error.get(key)) for key in ("code", "message") if error.get(key)
            )
        return str(error or "")

    def _cost_from_task_cny(
        self, task: dict[str, Any], inputs: dict[str, Any]
    ) -> float | None:
        usage = task.get("usage") or {}
        tokens = usage.get("completion_tokens")
        if (
            not isinstance(tokens, (int, float))
            or not math.isfinite(float(tokens))
            or float(tokens) < 0
        ):
            return None
        model_inputs = dict(inputs)
        if task.get("model"):
            model_inputs["model"] = task["model"]
        _, variant = self._resolve_model(model_inputs)
        resolution = str(
            task.get("resolution") or inputs.get("resolution", "720p")
        ).lower()
        condition = (
            "with_video"
            if inputs.get("input_includes_video")
            or inputs.get("reference_video_url")
            or inputs.get("reference_video_urls")
            else "without_video"
        )
        if variant is None:
            if "custom_price_cny_per_million_tokens" not in inputs:
                return None
            rate = self._get_custom_price(inputs, required=False)
        else:
            try:
                rate = self.PRICE_CNY_PER_MILLION[variant][condition][resolution]
            except KeyError:
                return None
        return round(float(tokens) * rate / 1_000_000, 4)

    def _cost_from_task(
        self, task: dict[str, Any], inputs: dict[str, Any]
    ) -> float | None:
        cost_cny = self._cost_from_task_cny(task, inputs)
        if cost_cny is None:
            return None
        cny_per_usd = self._get_cny_per_usd()
        return round(cost_cny / cny_per_usd, 4)

    def _safe_error(self, exc: Exception, api_key: str | None = None) -> str:
        message = str(exc)
        secrets = {value for value in (api_key, self._get_api_key()) if value}
        for secret in secrets:
            message = message.replace(secret, "[redacted]")
        message = re.sub(
            r"data:(?:image|audio)/[^;\s]+;base64,[A-Za-z0-9+/=]+",
            "[redacted data URI]",
            message,
            flags=re.IGNORECASE,
        )

        def redact_url(match: re.Match[str]) -> str:
            raw = match.group(0)
            trailing = ""
            while raw and raw[-1] in ".,;:)]}":
                trailing = raw[-1] + trailing
                raw = raw[:-1]
            try:
                parsed = urlsplit(raw)
                host = parsed.hostname or ""
                if parsed.port:
                    host = f"{host}:{parsed.port}"
                safe = urlunsplit(
                    (
                        parsed.scheme,
                        host,
                        parsed.path,
                        "[redacted]" if parsed.query else "",
                        "",
                    )
                )
                return safe + trailing
            except ValueError:
                return "[redacted URL]"

        message = re.sub(
            r"https?://[^\s'\"<>]+",
            redact_url,
            message,
            flags=re.IGNORECASE,
        )
        message = re.sub(
            r"(?i)authorization\s*[:=]\s*bearer\s+\S+",
            "Authorization: Bearer [redacted]",
            message,
        )
        return message
