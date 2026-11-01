"""Tencent Hunyuan (腾讯混元) cloud video generation via TokenHub API.

Calls the Tencent TokenHub API (tokenhub.tencentmaas.com) using simple Bearer
token authentication. This is the OpenAI-compatible API gateway for Tencent
Hunyuan video models — no TC3-HMAC-SHA256 signing required.

API flow: POST /v1/api/video/submit -> poll /v1/api/video/query ->
download data.url.

Authentication uses a TokenHub API key obtained from the Tencent Cloud
TokenHub console (https://console.cloud.tencent.com/tokenhub).
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

_HOST = "tokenhub.tencentmaas.com"
_SUBMIT_PATH = "/v1/api/video/submit"
_QUERY_PATH = "/v1/api/video/query"

# TokenHub model identifiers
_MODEL_T2V = "hy-video-1.5"       # text-to-video
_MODEL_I2V = "yt-video-2.0"       # image-to-video


class HunyuanCloudVideo(BaseTool):
    """Tencent Hunyuan cloud video generation via TokenHub API."""

    name = "hunyuan_cloud_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "hunyuan_cloud"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:TENCENT_TOKENHUB_API_KEY"]
    install_instructions = (
        "Set TENCENT_TOKENHUB_API_KEY to your Tencent Cloud TokenHub API key.\n"
        "  Get it at https://console.cloud.tencent.com/tokenhub"
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "native_audio": False,
        "seed": False,
    }
    best_for = [
        "Hunyuan text-to-video and image-to-video via Tencent TokenHub API",
        "simple Bearer-token auth (no TC3 signing required)",
        "direct Tencent Cloud quota usage (not through a third-party gateway)",
        "Chinese-language prompt understanding"
    ]
    not_good_for = [
        "offline generation or air-gapped environments",
        "users without Tencent Cloud account and real-name verification"
    ]
    fallback_tools = ["jimeng_video", "kling_official_video", "minimax_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "maxLength": 200,
                "description": (
                    "Video description. Max 200 UTF-8 characters. "
                    "Supports Chinese and English. Be specific about subject, action, "
                    "setting, and style."
                ),
            },
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
                "description": "Generation mode.",
            },
            "model": {
                "type": "string",
                "enum": ["hy-video-1.5", "yt-video-2.0"],
                "description": (
                    "TokenHub model ID. hy-video-1.5 for text-to-video, "
                    "yt-video-2.0 for image-to-video. Defaults to the recommended "
                    "model for the chosen operation."
                ),
            },
            "image_url": {
                "type": "string",
                "description": (
                    "Reference image URL for image-to-video. "
                    "Must be publicly accessible. Max 10MB. "
                    "Formats: jpg/png/jpeg/webp/bmp/tiff. "
                    "Resolution: 50-5000 pixels per side, aspect ratio 1:4 to 4:1."
                ),
            },
            "image_path": {
                "type": "string",
                "description": (
                    "Local path to a reference image for image-to-video. "
                    "Will be base64-encoded and sent inline. "
                    "Mutually exclusive with image_url."
                ),
            },
            "resolution": {
                "type": "string",
                "enum": ["720p", "1080p"],
                "default": "720p",
                "description": "Output resolution.",
            },
            "logo_add": {
                "type": "integer",
                "enum": [0, 1],
                "default": 1,
                "description": (
                    "Add 'AI-generated' watermark. 1 = add watermark (default), "
                    "0 = no watermark (requires console approval from Tencent)."
                ),
            },
            "output_path": {
                "type": "string",
                "description": "Output file path for the generated video (MP4).",
            },
            "poll_interval_seconds": {
                "type": "number",
                "minimum": 2,
                "default": 5.0,
                "description": "Seconds between status polls.",
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 60,
                "default": 600,
                "description": "Maximum seconds to wait for generation.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True,
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["rate_limit", "timeout"],
    )
    idempotency_key_fields = [
        "prompt",
        "operation",
        "model",
        "image_url",
        "image_path",
        "resolution",
        "logo_add",
    ]
    side_effects = [
        "writes video file to output_path",
        "calls Tencent TokenHub API (Bearer-token submit + poll + download)",
    ]
    user_visible_verification = [
        "Watch generated clip for motion coherence and prompt adherence",
        "Check for watermark if logo_add=0 was requested",
    ]

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _api_key() -> str | None:
        val = os.environ.get("TENCENT_TOKENHUB_API_KEY", "")
        if val and not val.strip().startswith("#"):
            return val.strip()
        return None

    # ------------------------------------------------------------------
    # Tool contract methods
    # ------------------------------------------------------------------

    def get_status(self) -> ToolStatus:
        if self._api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Estimate cost in USD based on model and resolution.

        Tencent TokenHub credit-based pricing (1 credit = 1.2 RMB ≈ $0.167 USD):
        - HY-Video-1.5: 1.5 credits/generation → $0.25
        - YT-Video-2.0 480p:       2   credits/generation → $0.33
        - YT-Video-2.0 720p/1080p: 5   credits/generation → $0.83

        Source: https://cloud.tencent.com.cn/document/product/1823/130054
        """
        model = self._resolve_model(inputs)
        resolution = inputs.get("resolution", "720p")

        _CREDIT_TO_USD = 1.2 / 7.2  # 1 credit = 1.2 RMB, ~7.2 RMB/USD

        if model == _MODEL_I2V:
            # YT-Video-2.0 has resolution-tiered pricing
            if resolution in ("720p", "1080p"):
                credits = 5.0
            else:
                credits = 2.0  # 480p and below
        else:
            # HY-Video-1.5 (and fallback for unknown models)
            credits = 1.5

        return round(credits * _CREDIT_TO_USD, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Estimate wall-clock time in seconds.

        Empirical estimate: most cloud video generation APIs (Kling, Pika, etc.)
        queue + generate in 60-180s. No official latency published by Tencent.
        180s is a safe upper-bound for timeout planning.
        """
        return 180.0

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="TENCENT_TOKENHUB_API_KEY not set. " + self.install_instructions,
            )

        operation = inputs.get("operation", "text_to_video")
        model = self._resolve_model(inputs)
        expected_model = _MODEL_I2V if operation == "image_to_video" else _MODEL_T2V
        if model != expected_model:
            return ToolResult(
                success=False,
                error=(
                    f"Model '{model}' is not compatible with operation '{operation}'. "
                    f"Use '{expected_model}'."
                ),
            )
        if operation == "image_to_video" and not inputs.get("image_url") and not inputs.get("image_path"):
            return ToolResult(
                success=False,
                error="image_to_video requires image_url (public URL) or image_path (local file).",
            )

        if inputs.get("image_url") and inputs.get("image_path"):
            return ToolResult(
                success=False,
                error="Provide only one of image_url or image_path, not both.",
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key=api_key)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Hunyuan TokenHub video generation failed: {self._safe_error(exc)}",
            )

        result.duration_seconds = round(time.time() - start, 2)
        return result

    # ------------------------------------------------------------------
    # Generation pipeline
    # ------------------------------------------------------------------

    def _generate(
        self, inputs: dict[str, Any], *, api_key: str,
    ) -> ToolResult:
        import requests

        from tools.video._shared import probe_output

        payload = self._build_payload(inputs)
        model = self._resolve_model(inputs)
        task_id = self._submit_task(payload, model=model, api_key=api_key)
        video_url = self._poll_task(
            task_id,
            model=model,
            api_key=api_key,
            poll_interval=float(inputs.get("poll_interval_seconds", 5.0)),
            timeout_seconds=int(inputs.get("timeout_seconds", 600)),
        )

        download = requests.get(video_url, timeout=120)
        download.raise_for_status()

        output_path = Path(
            inputs.get("output_path", f"hunyuan_cloud_{task_id}.mp4")
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(download.content)

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "hunyuan_cloud",
                "route": "tokenhub",
                "model": model,
                "prompt": inputs["prompt"],
                "operation": inputs.get("operation", "text_to_video"),
                "resolution": inputs.get("resolution", "720p"),
                "logo_add": payload.get("logo_add", 1),
                "task_id": task_id,
                "video_url": video_url,
                "output": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            model=model,
        )

    # ------------------------------------------------------------------
    # Payload construction
    # ------------------------------------------------------------------

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Build the request body for TokenHub video submit."""
        operation = inputs.get("operation", "text_to_video")
        payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
        }

        # Optional parameters (TokenHub uses lowercase_with_underscores)
        if inputs.get("resolution"):
            payload["resolution"] = inputs["resolution"]
        if "logo_add" in inputs:
            payload["logo_add"] = int(inputs["logo_add"])

        # Image for image-to-video
        if operation == "image_to_video":
            if inputs.get("image_url"):
                payload["image_url"] = inputs["image_url"]
            elif inputs.get("image_path"):
                payload["image"] = self._encode_image(inputs["image_path"])

        return payload

    @staticmethod
    def _resolve_model(inputs: dict[str, Any]) -> str:
        """Resolve the TokenHub model ID.

        Order of precedence:
        1. Explicit ``model`` input
        2. Default based on operation (hy-video-1.5 for T2V, yt-video-2.0 for I2V)
        """
        if inputs.get("model"):
            return inputs["model"]
        operation = inputs.get("operation", "text_to_video")
        return _MODEL_I2V if operation == "image_to_video" else _MODEL_T2V

    @staticmethod
    def _encode_image(path: str) -> str:
        """Read a local image file and return a base64-encoded string."""
        import base64

        image_path = Path(path)
        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")

        raw = image_path.read_bytes()
        max_raw = 6 * 1024 * 1024  # 6MB raw ≈ 8MB base64
        if len(raw) > max_raw:
            raise ValueError(
                f"Image too large ({len(raw)} bytes). Max ~6MB raw (8MB base64-encoded)."
            )

        return base64.b64encode(raw).decode("ascii")

    # ------------------------------------------------------------------
    # API communication (TokenHub OpenAI-compatible)
    # ------------------------------------------------------------------

    @staticmethod
    def _auth_headers(api_key: str) -> dict[str, str]:
        """Build common request headers for TokenHub API calls."""
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _submit_task(
        self, payload: dict[str, Any], *, model: str, api_key: str,
    ) -> str:
        """Submit a video generation task and return the task ID."""
        import requests

        body = {
            "model": model,
            **payload,
        }
        url = f"https://{_HOST}{_SUBMIT_PATH}"
        resp = requests.post(
            url,
            json=body,
            headers=self._auth_headers(api_key),
            timeout=30,
        )
        data = self._json_or_raise(resp)
        self._check_response(data)

        task_id = data.get("id")
        if not task_id:
            raise RuntimeError(
                f"TokenHub submit returned no task id: {data}"
            )
        return task_id

    def _poll_task(
        self,
        task_id: str,
        *,
        model: str,
        api_key: str,
        poll_interval: float,
        timeout_seconds: int,
    ) -> str:
        """Poll /v1/api/video/query until completion, return video download URL."""
        import requests

        url = f"https://{_HOST}{_QUERY_PATH}"

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            time.sleep(poll_interval)

            resp = requests.post(
                url,
                json={"model": model, "id": task_id},
                headers=self._auth_headers(api_key),
                timeout=30,
            )
            data = self._json_or_raise(resp)
            self._check_response(data)

            status = data.get("status", "")

            if status == "completed":
                result_data = data.get("data") or {}
                video_url = result_data.get("url")
                if not video_url:
                    raise RuntimeError(
                        f"TokenHub task {task_id} completed but no data.url: {data}"
                    )
                return video_url

            if status == "failed":
                error_info = data.get("error") or {}
                error_msg = error_info.get("message", "unknown error")
                raise RuntimeError(
                    f"TokenHub task {task_id} failed: {error_msg}"
                )

            # queued / running / in_progress — continue polling
            if status not in ("queued", "running", "in_progress"):
                raise RuntimeError(
                    f"TokenHub task {task_id} returned unknown status: {status}"
                )

        raise TimeoutError(
            f"TokenHub task {task_id} did not finish within {timeout_seconds}s"
        )

    # ------------------------------------------------------------------
    # Error handling helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        """Redact secret values from exception messages."""
        msg = str(exc)
        for var in ("TENCENT_TOKENHUB_API_KEY",):
            val = os.environ.get(var, "")
            if val:
                msg = msg.replace(val, "[redacted]")
        return msg

    @staticmethod
    def _json_or_raise(response: Any) -> dict[str, Any]:
        """Parse JSON response body or raise with HTTP status."""
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Non-JSON response from TokenHub API: HTTP {response.status_code}"
            ) from exc

    @staticmethod
    def _check_response(payload: dict[str, Any]) -> None:
        """Check the TokenHub API response for errors.

        TokenHub returns errors at the top level with an ``error`` field.
        """
        error = payload.get("error")
        if error:
            message = error.get("message", "unknown error")
            code = error.get("code", error.get("type", "unknown"))
            raise RuntimeError(
                f"TokenHub API error: code={code}, message={message}"
            )
