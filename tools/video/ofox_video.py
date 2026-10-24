"""OfoxAI unified video-generation gateway adapter.

OfoxAI (https://app.ofox.ai) is an OpenAI-compatible gateway that fronts many
upstream video models (Seedance, Wan, Hailuo, HappyHorse) behind one key and
one schema.  The API is asynchronous: create a task, poll it, then download the
finished clip from the CDN mirror URL.

Contract (https://ofox.ai/docs/api/videos):
  POST   /v1/videos          -> {"id", "status", "polling_url"}
  GET    /v1/videos/{id}     -> {"status", "mirror_urls", "unsigned_urls", "usage"}
  DELETE /v1/videos/{id}     -> cancel

Auth is ``Authorization: Bearer $OFOX_API_KEY``.  One request schema covers
text-to-video, image-to-video, and first/last-frame interpolation; the mode is
inferred from ``frame_images``.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

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


class OfoxVideo(BaseTool):
    """Generate video through the OfoxAI gateway's official REST API."""

    name = "ofox_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "ofox"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    BASE_URL = "https://api.ofox.ai"

    # Model matrix from https://ofox.ai/docs/api/videos/models (2026-09).
    # Values: (max_duration_seconds, {resolutions}, {aspect_ratios}).
    MODELS = {
        "alibaba/happyhorse-1.0": (15, {"720p", "1080p"}, {"16:9", "9:16", "1:1"}),
        "alibaba/happyhorse-1.1": (15, {"720p", "1080p"}, {"16:9", "9:16", "1:1"}),
        "alibaba/wan-2.6": (15, {"720p", "1080p"}, {"16:9", "9:16", "1:1"}),
        "alibaba/wan-2.7": (15, {"720p", "1080p"}, {"16:9", "9:16", "1:1"}),
        "alibaba/wan-3.0": (
            30,
            {"480p", "720p", "1080p"},
            {"16:9", "9:16", "1:1", "4:3", "3:4", "adaptive"},
        ),
        "alibaba/wan-3.0-prime": (
            30,
            {"480p", "720p", "1080p"},
            {"16:9", "9:16", "1:1", "4:3", "3:4", "adaptive"},
        ),
        "bytedance/seedance-2.0": (
            15,
            {"480p", "720p", "1080p", "4k"},
            {"16:9", "9:16", "1:1", "adaptive"},
        ),
        "bytedance/seedance-2.0-fast": (
            15,
            {"480p", "720p"},
            {"16:9", "9:16", "1:1", "adaptive"},
        ),
        "bytedance/seedance-2.0-mini": (
            15,
            {"480p", "720p"},
            {"16:9", "9:16", "1:1", "adaptive"},
        ),
        "bytedance/seedance-2.5": (
            30,
            {"480p", "720p", "1080p"},
            {"16:9", "9:16", "1:1", "4:3", "3:4", "adaptive", "21:9"},
        ),
        "minimax/hailuo-3": (
            15,
            {"768p", "2k"},
            {"16:9", "9:16", "1:1", "4:3", "3:4", "adaptive", "21:9"},
        ),
        "minimax/hailuo-3-max": (
            15,
            {"480p", "768p"},
            {"16:9", "9:16", "1:1", "4:3", "3:4", "adaptive", "21:9"},
        ),
    }
    DEFAULT_MODEL = "bytedance/seedance-2.5"
    TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "expired"})
    TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")

    dependencies = ["env:OFOX_API_KEY"]
    install_instructions = (
        "Set OFOX_API_KEY to your OfoxAI API key (the token body only, without "
        "the 'Bearer ' prefix). Get a key at https://app.ofox.ai. Optional: "
        "OFOX_BASE_URL to override the gateway host."
    )
    agent_skills = ["ai-video-gen"]

    capabilities = [
        "text_to_video",
        "image_to_video",
        "first_last_frame",
        "task_create",
        "task_query",
        "task_cancel",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "first_last_frame": True,
        "reference_image": True,
        "native_audio": True,
        "aspect_ratio": True,
        # Gateway documents HTTPS image URLs only — no local Base64 upload.
        "local_image_data_uri": False,
    }
    best_for = [
        "one key across many upstream video models (Seedance, Wan, Hailuo)",
        "text-to-video and image-to-video with synchronized audio",
        "swapping models without changing the request schema",
    ]
    not_good_for = [
        "offline generation",
        "local image files (gateway requires public image URLs)",
        "unapproved paid generation",
    ]
    fallback_tools = ["seedance_ark", "seedance_video", "wan_video"]

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
                "enum": ["text_to_video", "image_to_video", "first_last_frame"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "description": (
                    "OfoxAI model ID, e.g. 'bytedance/seedance-2.5'. "
                    f"Defaults to {DEFAULT_MODEL}."
                ),
            },
            "duration": {
                "type": "integer",
                "minimum": 1,
                "description": "Video length in seconds (model-capped).",
                "default": 5,
            },
            "resolution": {"type": "string", "default": "720p"},
            "aspect_ratio": {"type": "string", "default": "16:9"},
            "generate_audio": {"type": "boolean", "default": True},
            "provider_type": {
                "type": "string",
                "description": "Optional upstream provider to pin, e.g. 'byteplus'.",
            },
            "first_frame_url": {
                "type": "string",
                "description": "Public HTTPS image URL for image-to-video.",
            },
            "last_frame_url": {
                "type": "string",
                "description": "Public HTTPS image URL for first/last-frame mode.",
            },
            "callback_url": {
                "type": "string",
                "description": "Optional HTTPS webhook for async completion.",
            },
            "poll_interval_seconds": {
                "type": "number",
                "minimum": 1,
                "maximum": 60,
                "default": 3,
            },
            "timeout_seconds": {"type": "number", "minimum": 1, "default": 1200},
            "output_path": {"type": "string"},
            "estimated_cost_usd": {
                "type": "number",
                "minimum": 0,
                "description": (
                    "Optional caller-supplied cost estimate for budget checks. "
                    "Gateway pricing is per-model and returned only on completion."
                ),
            },
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
        "model",
        "duration",
        "aspect_ratio",
        "resolution",
        "generate_audio",
        "first_frame_url",
        "last_frame_url",
    ]
    side_effects = [
        "submits a paid task to the OfoxAI gateway",
        "writes the completed video to output_path",
    ]
    user_visible_verification = [
        "Watch the downloaded clip for visual continuity and synchronized audio",
        "Confirm the local artifact before the upstream URL expires",
    ]

    # --- configuration -----------------------------------------------------

    def _get_api_key(self) -> str | None:
        return os.environ.get("OFOX_API_KEY")

    def _get_base_url(self) -> str:
        base_url = os.environ.get("OFOX_BASE_URL", self.BASE_URL).rstrip("/")
        if not base_url.startswith("https://"):
            raise ValueError("OFOX_BASE_URL must be an https:// URL")
        return base_url

    def get_status(self) -> ToolStatus:
        api_key = self._get_api_key()
        if not api_key or api_key.lower().startswith("bearer "):
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Gateway pricing is model-specific and only returned on completion.

        Honor a caller-supplied estimate for budget reservation; otherwise
        report 0.0 (the actual cost is reconciled from usage.video_cost).
        """
        raw = inputs.get("estimated_cost_usd")
        if raw is None:
            return 0.0
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("estimated_cost_usd must be a number") from exc
        if value < 0:
            raise ValueError("estimated_cost_usd must not be negative")
        return round(value, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 180.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate and describe the request locally; never submit a paid POST."""
        action = str(inputs.get("task_action", "generate"))
        result: dict[str, Any] = {
            "tool": self.name,
            "task_action": action,
            "status": self.get_status().value,
            "would_execute": False,
            "paid_submission": False,
        }
        try:
            base_url = self._get_base_url()
            api_key = self._get_api_key()
            if api_key and api_key.lower().startswith("bearer "):
                raise ValueError(
                    "OFOX_API_KEY must contain only the token body; remove "
                    "the 'Bearer ' prefix"
                )
            result["api_contract"] = {
                "create": f"POST {base_url}/v1/videos",
                "query": f"GET {base_url}/v1/videos/{{id}}",
                "cancel": f"DELETE {base_url}/v1/videos/{{id}}",
            }
            if action in {"query", "cancel"}:
                self._validate_task_id(inputs.get("task_id"))
            else:
                payload = self._build_payload(inputs)
                result.update(
                    {
                        "model": payload["model"],
                        "operation": inputs.get("operation", "text_to_video"),
                        "resolution": payload.get("resolution"),
                        "aspect_ratio": payload.get("aspect_ratio"),
                        "duration": payload.get("duration"),
                        "generate_audio": payload.get("generate_audio"),
                        "has_frame_images": "frame_images" in payload,
                        "estimated_cost_usd": self.estimate_cost(inputs),
                        "cost_estimate_note": (
                            "Gateway pricing is per-model and returned on "
                            "completion via usage.video_cost; preflight cost is "
                            "0.0 unless estimated_cost_usd is supplied."
                        ),
                    }
                )
            result["valid"] = True
        except (TypeError, ValueError, OSError) as exc:
            result["valid"] = False
            result["error"] = self._safe_error(exc)
        return result

    # --- execution ---------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        """Create, query, cancel, or synchronously finish an OfoxAI task."""
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
                # Parse any local cost config before the paid POST so a bad
                # estimate never creates an untracked task.
                estimated_cost_usd = self.estimate_cost(inputs)
        except (TypeError, ValueError, OSError) as exc:
            return ToolResult(success=False, error=self._safe_error(exc))

        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="OFOX_API_KEY not set. " + self.install_instructions,
            )
        if api_key.lower().startswith("bearer "):
            return ToolResult(
                success=False,
                error=(
                    "OFOX_API_KEY must contain only the token body; remove "
                    "the 'Bearer ' prefix"
                ),
            )

        try:
            if action == "query":
                task = self._query_task(str(inputs["task_id"]), api_key)
                return ToolResult(
                    success=True,
                    data={"task": task},
                    cost_usd=self._cost_from_task(task),  # type: ignore[arg-type]
                    model=task.get("model"),
                )

            if action == "cancel":
                task_id = str(inputs["task_id"])
                self._cancel_task(task_id, api_key)
                return ToolResult(
                    success=True,
                    data={"task_id": task_id, "status": "cancel_requested"},
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
            if status != "completed":
                detail = self._task_error(task)
                safe_detail = (
                    self._safe_error(RuntimeError(detail), api_key) if detail else ""
                )
                return ToolResult(
                    success=False,
                    data={"task_id": task_id, "status": status},
                    error=(
                        f"OfoxAI task {status or 'failed'}"
                        + (f": {safe_detail}" if safe_detail else "")
                    ),
                    duration_seconds=round(time.time() - started, 2),
                    model=str(task.get("model") or model),
                )

            video_url = self._result_url(task)
            if not video_url:
                raise RuntimeError("OfoxAI task completed without a video URL")
            output_path = Path(inputs.get("output_path", "ofox_video_output.mp4"))
            self._download_video(video_url, api_key, output_path)

            from tools.video._shared import probe_output

            probed = probe_output(output_path)
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
                    "mirror_urls": task.get("mirror_urls") or [],
                    "unsigned_urls": task.get("unsigned_urls") or [],
                    "output": str(output_path),
                    "output_path": str(output_path),
                    "format": "mp4",
                    "resolution": task.get("resolution", payload.get("resolution")),
                    "aspect_ratio": task.get(
                        "aspect_ratio", payload.get("aspect_ratio")
                    ),
                    "duration": task.get("duration", payload.get("duration")),
                    "usage": task.get("usage") or {},
                    **probed,
                },
                artifacts=[str(output_path)],
                cost_usd=self._cost_from_task(task),  # type: ignore[arg-type]
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
                error=f"OfoxAI request failed: {self._safe_error(exc, api_key)}",
                duration_seconds=round(time.time() - started, 2),
            )

    # --- payload -----------------------------------------------------------

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        operation = str(inputs.get("operation", "text_to_video"))
        if operation not in {"text_to_video", "image_to_video", "first_last_frame"}:
            raise ValueError(
                "operation must be text_to_video, image_to_video, or "
                "first_last_frame"
            )

        model = str(inputs.get("model") or self.DEFAULT_MODEL)
        limits = self.MODELS.get(model)
        if limits is None:
            known = ", ".join(sorted(self.MODELS))
            raise ValueError(f"unknown model '{model}'; choose one of: {known}")
        max_duration, resolutions, ratios = limits

        resolution = str(inputs.get("resolution", "720p")).lower()
        if resolution not in resolutions:
            raise ValueError(
                f"{model} supports resolutions {sorted(resolutions)}, not "
                f"'{resolution}'"
            )

        aspect_ratio = str(inputs.get("aspect_ratio", "16:9"))
        if aspect_ratio not in ratios:
            raise ValueError(
                f"{model} supports aspect ratios {sorted(ratios)}, not "
                f"'{aspect_ratio}'"
            )

        duration = self._normalize_duration(inputs.get("duration", 5), max_duration)
        prompt = str(inputs.get("prompt") or "").strip()

        payload: dict[str, Any] = {
            "model": model,
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "generate_audio": bool(inputs.get("generate_audio", True)),
        }
        if prompt:
            payload["prompt"] = prompt

        first_url = inputs.get("first_frame_url")
        last_url = inputs.get("last_frame_url")

        if operation == "text_to_video":
            if not prompt:
                raise ValueError("prompt is required for text_to_video")
            if first_url or last_url:
                raise ValueError(
                    "text_to_video does not accept frame images; use "
                    "image_to_video or first_last_frame"
                )
        elif operation == "image_to_video":
            if not first_url:
                raise ValueError("image_to_video requires first_frame_url")
            if last_url:
                raise ValueError(
                    "image_to_video takes only first_frame_url; use "
                    "first_last_frame for a last frame"
                )
            payload["frame_images"] = [self._frame(first_url, "first_frame")]
        else:  # first_last_frame
            if not (first_url and last_url):
                raise ValueError(
                    "first_last_frame requires both first_frame_url and "
                    "last_frame_url"
                )
            payload["frame_images"] = [
                self._frame(first_url, "first_frame"),
                self._frame(last_url, "last_frame"),
            ]

        if inputs.get("provider_type"):
            payload["provider"] = {"type": str(inputs["provider_type"])}
        if inputs.get("callback_url"):
            payload["callback_url"] = self._require_https(
                str(inputs["callback_url"]), "callback_url"
            )
        return payload

    def _frame(self, url: Any, frame_type: str) -> dict[str, Any]:
        return {
            "type": "image_url",
            "image_url": {"url": self._require_https(str(url), "frame image URL")},
            "frame_type": frame_type,
        }

    @staticmethod
    def _require_https(value: str, label: str) -> str:
        if not value.startswith("https://"):
            raise ValueError(f"{label} must be a public https:// URL: {value}")
        return value

    @staticmethod
    def _normalize_duration(value: Any, max_seconds: int) -> int:
        if isinstance(value, bool):
            raise ValueError(f"duration must be an integer from 1 to {max_seconds}")
        try:
            duration = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"duration must be an integer from 1 to {max_seconds}"
            ) from exc
        if str(value).strip() != str(duration):
            raise ValueError(f"duration must be an integer from 1 to {max_seconds}")
        if not 1 <= duration <= max_seconds:
            raise ValueError(f"duration must be between 1 and {max_seconds}")
        return duration

    def _validate_task_id(self, task_id: Any) -> None:
        if not task_id or not isinstance(task_id, str):
            raise ValueError("task_id is required for query/cancel")
        if not self.TASK_ID_PATTERN.match(task_id):
            raise ValueError("task_id contains invalid characters")

    # --- HTTP --------------------------------------------------------------

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _create_task(self, payload: dict[str, Any], api_key: str) -> str:
        url = f"{self._get_base_url()}/v1/videos"
        response = requests.post(
            url, headers=self._headers(api_key), json=payload, timeout=60
        )
        response.raise_for_status()
        body = response.json()
        task_id = body.get("id")
        if not task_id:
            raise RuntimeError("OfoxAI create response missing task id")
        return str(task_id)

    def _query_task(self, task_id: str, api_key: str) -> dict[str, Any]:
        url = f"{self._get_base_url()}/v1/videos/{task_id}"
        last_error: Exception | None = None
        attempts = self.retry_policy.max_retries + 1
        for attempt in range(attempts):
            try:
                response = requests.get(
                    url, headers=self._headers(api_key), timeout=60
                )
                if response.status_code >= 500:
                    raise RuntimeError(f"HTTP {response.status_code}")
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # noqa: BLE001 - retried below
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(self.retry_policy.backoff_seconds)
        assert last_error is not None
        raise last_error

    def _cancel_task(self, task_id: str, api_key: str) -> None:
        url = f"{self._get_base_url()}/v1/videos/{task_id}"
        response = requests.delete(url, headers=self._headers(api_key), timeout=60)
        response.raise_for_status()

    def _poll_task(
        self, task_id: str, api_key: str, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        # Gateway asks callers to poll no faster than once per second.
        interval = max(1.0, float(inputs.get("poll_interval_seconds", 3)))
        timeout = float(inputs.get("timeout_seconds", 1200))
        deadline = time.time() + timeout
        while True:
            task = self._query_task(task_id, api_key)
            status = str(task.get("status", "")).lower()
            if status in self.TERMINAL_STATUSES:
                return task
            if time.time() >= deadline:
                raise TimeoutError(
                    f"OfoxAI task {task_id} did not finish within {timeout:.0f}s "
                    f"(last status: {status or 'unknown'})"
                )
            time.sleep(interval)

    def _download_video(self, url: str, api_key: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Mirror URLs are pre-signed; upstream URLs need no auth either. Send the
        # bearer only to the gateway's own host to avoid leaking it to a CDN.
        headers = {}
        if urlsplit(url).netloc.endswith("ofox.ai"):
            headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(url, headers=headers, timeout=300)
        response.raise_for_status()
        output_path.write_bytes(response.content)

    # --- result parsing ----------------------------------------------------

    @staticmethod
    def _result_url(task: dict[str, Any]) -> str | None:
        # CDN mirror is persistent/stable; fall back to the temporary upstream.
        for key in ("mirror_urls", "unsigned_urls"):
            urls = task.get(key)
            if isinstance(urls, list) and urls:
                return str(urls[0])
        # Some gateway responses may nest a single url under output/result.
        for key in ("output", "result"):
            node = task.get(key)
            if isinstance(node, dict) and node.get("url"):
                return str(node["url"])
        return None

    @staticmethod
    def _cost_from_task(task: dict[str, Any]) -> float | None:
        usage = task.get("usage")
        if not isinstance(usage, dict):
            return None
        raw = usage.get("video_cost")
        if raw is None:
            return None
        try:
            return round(float(raw), 6)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _task_error(task: dict[str, Any]) -> str:
        error = task.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or error)
        if error:
            return str(error)
        return ""

    # --- redaction ---------------------------------------------------------

    def _safe_error(self, exc: Exception, api_key: str | None = None) -> str:
        message = str(exc)
        if api_key:
            message = message.replace(api_key, "[redacted]")
        # Strip query strings that may carry signed-URL credentials.
        message = re.sub(
            r"(https?://[^\s?]+)\?[^\s]*",
            lambda m: f"{m.group(1)}?[redacted]",
            message,
        )
        return message
