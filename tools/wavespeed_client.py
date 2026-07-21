"""Reusable WaveSpeed API client for image/video generation tools."""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any, Callable

import requests


DEFAULT_BASE_URL = "https://api.wavespeed.ai/api/v3"
IMAGE_TASK_TYPES = {"text_to_image"}
VIDEO_TASK_TYPES = {"image_to_video", "text_to_video"}
COMPLETED_STATUSES = {"completed", "complete", "succeeded", "success", "finished"}
FAILED_STATUSES = {"failed", "error", "cancelled", "canceled"}
RUNNING_STATUSES = {"pending", "queued", "running", "processing", "starting", "submitted"}


class WaveSpeedError(RuntimeError):
    """Base exception with optional metadata safe to write to disk."""

    def __init__(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.metadata = metadata or {}


class WaveSpeedAuthError(WaveSpeedError):
    """Missing or rejected WaveSpeed credentials."""


class WaveSpeedMissingModelError(WaveSpeedError):
    """No model_id was supplied or configured."""


class WaveSpeedHTTPError(WaveSpeedError):
    """Unexpected HTTP response from WaveSpeed."""


class WaveSpeedTaskFailedError(WaveSpeedError):
    """WaveSpeed prediction finished in a failed state."""


class WaveSpeedTimeoutError(WaveSpeedError):
    """WaveSpeed prediction exceeded max wait."""


class WaveSpeedMalformedResponseError(WaveSpeedError):
    """WaveSpeed response did not match the expected task/result shape."""


@dataclass(frozen=True)
class WaveSpeedPrediction:
    """Structured metadata for a completed WaveSpeed task."""

    provider: str
    model_id: str
    task_id: str
    task_type: str
    status: str
    outputs: list[str]
    submit_response: dict[str, Any]
    result_response: dict[str, Any]


class WaveSpeedClient:
    """Small synchronous client for WaveSpeed submit/poll workflows."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("WAVESPEED_API_KEY")
        self.base_url = (base_url or os.environ.get("WAVESPEED_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.session = session or requests.Session()
        self._sleep = sleep or time.sleep
        self._monotonic = monotonic or time.monotonic

    @property
    def headers(self) -> dict[str, str]:
        if not self.api_key:
            raise WaveSpeedAuthError("WAVESPEED_API_KEY is not set. Add it to your environment or .env file.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def submit_task(self, model_id: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        model_id = (model_id or "").strip()
        if not model_id:
            raise WaveSpeedMissingModelError("WaveSpeed model_id is missing. Configure a profile model_id or pass --model-id.")

        url = f"{self.base_url}/{model_id.lstrip('/')}"
        response = self.session.post(url, headers=self.headers, json=payload, timeout=30)
        data = self._json_response(response, context="submit")
        task_id = self._extract_task_id(data)
        if not task_id:
            raise WaveSpeedMalformedResponseError(
                "WaveSpeed submit response did not include a prediction/task id.",
                metadata={"submit_response": data, "model_id": model_id},
            )
        return task_id, data

    def get_result(self, task_id: str) -> dict[str, Any]:
        url = f"{self.base_url}/predictions/{task_id}/result"
        response = self.session.get(url, headers=self.headers, timeout=30)
        return self._json_response(response, context="poll", task_id=task_id)

    def run_prediction(
        self,
        *,
        model_id: str,
        task_type: str,
        payload: dict[str, Any],
        poll_interval_seconds: float | None = None,
        max_wait_seconds: float | None = None,
    ) -> WaveSpeedPrediction:
        """Submit a task and poll until completed, failed, or timed out."""

        interval = poll_interval_seconds
        if interval is None:
            interval = self._default_poll_interval(task_type)
        interval = max(float(interval), 1.0)
        max_wait = float(max_wait_seconds) if max_wait_seconds is not None else _env_float("WAVESPEED_MAX_WAIT_SECONDS", 900.0)

        task_id, submit_response = self.submit_task(model_id, payload)
        started = self._monotonic()
        last_response: dict[str, Any] = {}

        while True:
            result_response = self.get_result(task_id)
            last_response = result_response
            status = self._normalize_status(result_response)
            outputs = self._extract_outputs(result_response)

            if status in COMPLETED_STATUSES or (not status and outputs):
                if not outputs:
                    raise WaveSpeedMalformedResponseError(
                        "WaveSpeed completed but returned no output URLs.",
                        metadata={
                            "task_id": task_id,
                            "model_id": model_id,
                            "status": "completed",
                            "submit_response": submit_response,
                            "result_response": result_response,
                        },
                    )
                return WaveSpeedPrediction(
                    provider="wavespeed",
                    model_id=model_id,
                    task_id=task_id,
                    task_type=task_type,
                    status="completed",
                    outputs=outputs,
                    submit_response=submit_response,
                    result_response=result_response,
                )

            if status in FAILED_STATUSES:
                error_text = self._extract_error(result_response) or "WaveSpeed task failed."
                raise WaveSpeedTaskFailedError(
                    error_text,
                    metadata={
                        "task_id": task_id,
                        "model_id": model_id,
                        "status": "failed",
                        "submit_response": submit_response,
                        "result_response": result_response,
                    },
                )

            if status and status not in RUNNING_STATUSES:
                raise WaveSpeedMalformedResponseError(
                    f"WaveSpeed returned unknown status {status!r}.",
                    metadata={
                        "task_id": task_id,
                        "model_id": model_id,
                        "status": status,
                        "submit_response": submit_response,
                        "result_response": result_response,
                    },
                )

            elapsed = self._monotonic() - started
            if elapsed >= max_wait:
                raise WaveSpeedTimeoutError(
                    f"WaveSpeed task {task_id} timed out after {max_wait:.0f} seconds.",
                    metadata={
                        "task_id": task_id,
                        "model_id": model_id,
                        "status": "timeout",
                        "submit_response": submit_response,
                        "result_response": last_response,
                    },
                )
            self._sleep(min(interval, max(1.0, max_wait - elapsed)))

    def download_url(self, url: str, timeout: int = 180) -> bytes:
        response = self.session.get(url, timeout=timeout)
        self._raise_for_status(response, context="download")
        return response.content

    @staticmethod
    def _default_poll_interval(task_type: str) -> float:
        if task_type in IMAGE_TASK_TYPES:
            return max(_env_float("WAVESPEED_POLL_INTERVAL_IMAGE_SECONDS", 2.0), 1.0)
        if task_type in VIDEO_TASK_TYPES:
            return max(_env_float("WAVESPEED_POLL_INTERVAL_VIDEO_SECONDS", 5.0), 1.0)
        return 5.0

    def _json_response(self, response: requests.Response, *, context: str, task_id: str | None = None) -> dict[str, Any]:
        self._raise_for_status(response, context=context, task_id=task_id)
        try:
            data = response.json()
        except ValueError as exc:
            raise WaveSpeedMalformedResponseError(
                f"WaveSpeed {context} response was not valid JSON.",
                metadata={"status_code": getattr(response, "status_code", None), "task_id": task_id},
            ) from exc
        if not isinstance(data, dict):
            raise WaveSpeedMalformedResponseError(
                f"WaveSpeed {context} response must be a JSON object.",
                metadata={"response": data, "task_id": task_id},
            )
        return data

    @staticmethod
    def _raise_for_status(response: requests.Response, *, context: str, task_id: str | None = None) -> None:
        status_code = getattr(response, "status_code", None)
        if status_code in (401, 403):
            raise WaveSpeedAuthError(
                f"WaveSpeed {context} request was rejected with HTTP {status_code}. Check WAVESPEED_API_KEY.",
                metadata={"status_code": status_code, "task_id": task_id},
            )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise WaveSpeedHTTPError(
                f"WaveSpeed {context} request failed with HTTP {status_code}.",
                metadata={"status_code": status_code, "task_id": task_id},
            ) from exc

    @staticmethod
    def _extract_task_id(data: dict[str, Any]) -> str | None:
        for key in ("id", "task_id", "prediction_id"):
            value = data.get(key)
            if value:
                return str(value)
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("id", "task_id", "prediction_id"):
                value = nested.get(key)
                if value:
                    return str(value)
        return None

    @staticmethod
    def _normalize_status(data: dict[str, Any]) -> str:
        value = data.get("status") or data.get("state")
        nested = data.get("data")
        if not value and isinstance(nested, dict):
            value = nested.get("status") or nested.get("state")
        return str(value or "").strip().lower()

    @staticmethod
    def _extract_error(data: dict[str, Any]) -> str | None:
        for key in ("error", "message", "failure", "failure_reason"):
            value = data.get(key)
            if value:
                return str(value)
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("error", "message", "failure", "failure_reason"):
                value = nested.get(key)
                if value:
                    return str(value)
        return None

    # Keys that designate provider *outputs*. Deliberately excludes ambiguous
    # keys such as "image"/"images"/"video"/"videos": for image_to_video,
    # image_edit, and lip_sync the /result payload can echo the *input* asset
    # URL under one of those keys, and treating that as an output would write the
    # source back out as the result. WaveSpeed returns results under
    # (data.)outputs; keep extraction scoped to output-designated keys only.
    OUTPUT_KEYS = ("output", "outputs", "result", "results")

    @classmethod
    def _extract_outputs(cls, data: dict[str, Any]) -> list[str]:
        candidates: list[Any] = []
        for key in cls.OUTPUT_KEYS:
            if key in data:
                candidates.append(data[key])
        nested = data.get("data")
        if isinstance(nested, dict):
            candidates.extend(cls._extract_outputs(nested))

        urls: list[str] = []
        for item in candidates:
            urls.extend(cls._urls_from_value(item))

        deduped: list[str] = []
        seen: set[str] = set()
        for url in urls:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped

    @classmethod
    def _urls_from_value(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value] if value.startswith(("http://", "https://")) else []
        if isinstance(value, list):
            urls: list[str] = []
            for item in value:
                urls.extend(cls._urls_from_value(item))
            return urls
        if isinstance(value, dict):
            urls: list[str] = []
            for key in ("url", "uri", "download_url"):
                item = value.get(key)
                if isinstance(item, str) and item.startswith(("http://", "https://")):
                    urls.append(item)
            for item in value.values():
                urls.extend(cls._urls_from_value(item))
            return urls
        return []


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default
