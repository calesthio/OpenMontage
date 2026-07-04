"""MiniMax (Hailuo AI) video generation via the official Token Plan API.

This tool calls the MiniMax official API directly (api.minimaxi.com / api.minimax.io),
NOT through fal.ai. It is distinct from ``minimax_video`` (which routes through
FAL_KEY) so that the cost route is explicit: users with a MiniMax Token Plan
subscription use this tool to consume their own quota instead of FAL credits.

API flow: POST /v1/video_generation -> poll GET /v1/query/video_generation ->
GET /v1/files/retrieve -> download.
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


class MinimaxTokenPlanVideo(BaseTool):
    name = "minimax_tokenplan_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "minimax"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set MINIMAX_TOKEN_PLAN_API_KEY (preferred) or MINIMAX_API_KEY to your MiniMax Token Plan API key.\n"
        "  Get one at https://platform.minimax.io/user-center/basic-information/interface-key\n"
        "  Optionally set MINIMAX_REGION=global to use api.minimax.io instead of api.minimaxi.com."
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "native_audio": False,
        "watermark_control": True,
        "prompt_optimizer": True,
    }
    best_for = [
        "direct MiniMax Token Plan quota usage (no FAL credits)",
        "Hailuo 2.3 text-to-video and image-to-video",
        "auditable cost route — calls official MiniMax API, not a proxy",
    ]
    not_good_for = [
        "users without a MiniMax Token Plan subscription (use minimax_video via FAL instead)",
        "offline generation",
    ]
    fallback_tools = ["minimax_video", "kling_video", "veo_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "Video description (text-to-video) or motion description "
                    "(image-to-video). Max 2000 chars."
                ),
            },
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "enum": ["MiniMax-Hailuo-2.3", "MiniMax-Hailuo-2.3-Fast"],
                "default": "MiniMax-Hailuo-2.3",
                "description": (
                    "MiniMax-Hailuo-2.3 supports text-to-video and image-to-video. "
                    "MiniMax-Hailuo-2.3-Fast is faster but only supports "
                    "image-to-video."
                ),
            },
            "duration": {
                "type": "integer",
                "minimum": 4,
                "maximum": 10,
                "default": 6,
                "description": "Video length in seconds.",
            },
            "resolution": {
                "type": "string",
                "enum": ["768P", "720P", "1080P"],
                "default": "768P",
                "description": "Video resolution. 768P is the Token Plan default.",
            },
            "first_frame_image": {
                "type": "string",
                "description": (
                    "First frame image URL for image-to-video. "
                    "Must be publicly accessible."
                ),
            },
            "prompt_optimizer": {
                "type": "boolean",
                "default": True,
                "description": "Auto-optimize the prompt for better results.",
            },
            "fast_pretreatment": {
                "type": "boolean",
                "default": False,
                "description": "Shorten the prompt optimizer duration.",
            },
            "aigc_watermark": {
                "type": "boolean",
                "default": False,
                "description": "Embed an AI-generated content watermark.",
            },
            "callback_url": {
                "type": "string",
                "description": (
                    "Webhook URL to receive async task status updates. "
                    "The server sends a validation challenge first."
                ),
            },
            "output_path": {"type": "string"},
            "poll_interval_seconds": {
                "type": "number",
                "minimum": 2,
                "default": 5.0,
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 60,
                "default": 600,
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["rate_limit", "timeout"],
    )
    idempotency_key_fields = [
        "prompt",
        "model",
        "operation",
        "duration",
        "resolution",
        "first_frame_image",
        "prompt_optimizer",
        "fast_pretreatment",
        "aigc_watermark",
    ]
    side_effects = [
        "writes video file to output_path",
        "calls MiniMax official Token Plan API (submit + poll + download)",
    ]
    user_visible_verification = [
        "Watch generated clip for motion coherence and prompt adherence",
    ]

    def _base_url(self) -> str:
        region = os.environ.get("MINIMAX_REGION", "cn").strip().lower()
        if region == "global":
            return "https://api.minimax.io"
        return "https://api.minimaxi.com"

    def _api_key(self) -> str | None:
        key = os.environ.get("MINIMAX_TOKEN_PLAN_API_KEY") or os.environ.get("MINIMAX_API_KEY")
        if key and not key.strip().startswith("#"):
            return key.strip()
        return None

    def get_status(self) -> ToolStatus:
        if self._api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # MiniMax bills per second of generated video; ~$0.05/sec.
        duration = int(inputs.get("duration", 6))
        return round(0.05 * duration, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        duration = int(inputs.get("duration", 6))
        return 60.0 + duration * 10.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="MINIMAX_TOKEN_PLAN_API_KEY or MINIMAX_API_KEY not set. " + self.install_instructions,
            )

        operation = inputs.get("operation", "text_to_video")
        model = inputs.get("model", "MiniMax-Hailuo-2.3")

        if model == "MiniMax-Hailuo-2.3-Fast" and operation == "text_to_video":
            return ToolResult(
                success=False,
                error=(
                    "MiniMax-Hailuo-2.3-Fast does not support text-to-video. "
                    "Use MiniMax-Hailuo-2.3 or switch operation to image_to_video."
                ),
            )

        if operation == "image_to_video" and not inputs.get("first_frame_image"):
            return ToolResult(
                success=False,
                error="image_to_video requires first_frame_image (public URL).",
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key=api_key)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"MiniMax Token Plan video generation failed: {self._safe_error(exc)}",
            )

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _generate(
        self, inputs: dict[str, Any], *, api_key: str
    ) -> ToolResult:
        import requests

        from tools.video._shared import probe_output

        base = self._base_url()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = self._build_payload(inputs)
        submit_resp = requests.post(
            f"{base}/v1/video_generation",
            headers=headers,
            json=payload,
            timeout=30,
        )
        submit_data = self._json_or_raise(submit_resp)
        self._check_base_resp(submit_resp.status_code, submit_data)

        task_id = submit_data.get("task_id")
        if not task_id:
            raise RuntimeError(
                "MiniMax API returned no task_id"
            )

        poll_data = self._poll_task(
            requests_module=requests,
            base_url=base,
            headers=headers,
            task_id=task_id,
            poll_interval=float(inputs.get("poll_interval_seconds", 5.0)),
            timeout_seconds=int(inputs.get("timeout_seconds", 600)),
        )

        file_id = poll_data.get("file_id")
        if not file_id:
            raise RuntimeError(
                "MiniMax task succeeded but file_id missing"
            )

        retrieve_resp = requests.get(
            f"{base}/v1/files/retrieve",
            headers=headers,
            params={"file_id": file_id},
            timeout=30,
        )
        retrieve_resp.raise_for_status()
        retrieve_data = self._json_or_raise(retrieve_resp)
        self._check_base_resp(retrieve_resp.status_code, retrieve_data)
        download_url = (
            retrieve_data.get("file", {}).get("download_url")
            or retrieve_data.get("download_url")
        )
        if not download_url:
            raise RuntimeError(
                "MiniMax file retrieve returned no download URL"
            )

        download = requests.get(download_url, timeout=120)
        download.raise_for_status()

        output_path = Path(inputs.get("output_path", "minimax_tokenplan.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(download.content)

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "minimax",
                "route": "token_plan",
                "model": payload["model"],
                "prompt": inputs["prompt"],
                "operation": inputs.get("operation", "text_to_video"),
                "duration": payload.get("duration", 6),
                "resolution": payload.get("resolution", "768P"),
                "aigc_watermark": payload.get("aigc_watermark", False),
                "task_id": task_id,
                "file_id": file_id,
                "output": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            model=payload["model"],
        )

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        operation = inputs.get("operation", "text_to_video")
        payload: dict[str, Any] = {
            "model": inputs.get("model", "MiniMax-Hailuo-2.3"),
            "prompt": inputs["prompt"],
            "duration": int(inputs.get("duration", 6)),
            "resolution": inputs.get("resolution", "768P"),
            "prompt_optimizer": bool(inputs.get("prompt_optimizer", True)),
            "aigc_watermark": bool(inputs.get("aigc_watermark", False)),
        }
        if inputs.get("fast_pretreatment") is not None:
            payload["fast_pretreatment"] = bool(inputs["fast_pretreatment"])
        if operation == "image_to_video" and inputs.get("first_frame_image"):
            payload["first_frame_image"] = inputs["first_frame_image"]
        if inputs.get("callback_url"):
            payload["callback_url"] = inputs["callback_url"]
        return payload

    def _poll_task(
        self,
        *,
        requests_module: Any,
        base_url: str,
        headers: dict[str, str],
        task_id: str,
        poll_interval: float,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            time.sleep(poll_interval)
            resp = requests_module.get(
                f"{base_url}/v1/query/video_generation",
                headers=headers,
                params={"task_id": task_id},
                timeout=30,
            )
            data = self._json_or_raise(resp)
            self._check_base_resp(resp.status_code, data)
            status = data.get("status", "")
            if status == "Success":
                return data
            if status == "Fail":
                msg = data.get("error_message") or data.get("status_msg") or "unknown error"
                raise RuntimeError(f"MiniMax task failed: {msg}")
        raise TimeoutError(
            f"MiniMax task {task_id} did not finish within {timeout_seconds}s"
        )

    @staticmethod
    def _json_or_raise(response: Any) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Non-JSON response from MiniMax API: HTTP {response.status_code}"
            ) from exc

    @staticmethod
    def _check_base_resp(http_status: int, payload: dict[str, Any]) -> None:
        if http_status < 400:
            base = payload.get("base_resp", {})
            code = base.get("status_code", 0)
            if code == 0:
                return
            msg = base.get("status_msg", "unknown error")
            raise RuntimeError(f"MiniMax API error: code {code}: {msg}")
        code = payload.get("base_resp", {}).get("status_code") or payload.get("status_code")
        msg = payload.get("base_resp", {}).get("status_msg") or payload.get("status_msg", "unknown error")
        raise RuntimeError(f"MiniMax API error: HTTP {http_status}, code {code}: {msg}")

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        msg = str(exc)
        for var in ("MINIMAX_TOKEN_PLAN_API_KEY", "MINIMAX_API_KEY"):
            val = os.environ.get(var, "")
            if val:
                msg = msg.replace(val, "[redacted]")
        return msg
