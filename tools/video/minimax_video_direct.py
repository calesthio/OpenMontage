"""MiniMax (Hailuo) video generation via the *direct* MiniMax platform API.

Unlike `minimax_video` (which routes through fal.ai and needs FAL_KEY), this tool
talks straight to the MiniMax open platform using a native MiniMax API key.

Auth/config (read from environment / .env):
  - MINIMAX_API_KEY    : MiniMax platform API key (required)
  - MINIMAX_API_BASE   : API base URL. Default https://api.minimaxi.com (China platform).
                         Use https://api.minimax.io for the global platform.
  - MINIMAX_VIDEO_MODEL: default model id, e.g. MiniMax-Hailuo-02 / T2V-01 / I2V-01.

Flow (async):
  POST {base}/v1/video_generation        -> task_id
  GET  {base}/v1/query/video_generation  -> status (Queueing/Preparing/Processing/Success/Fail) + file_id
  GET  {base}/v1/files/retrieve          -> download_url
  download mp4 to output_path
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

DEFAULT_BASE = "https://api.minimaxi.com"
DEFAULT_MODEL = "MiniMax-Hailuo-02"


class MiniMaxVideoDirect(BaseTool):
    name = "minimax_video_direct"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "minimax"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set MINIMAX_API_KEY to your MiniMax platform API key.\n"
        "  China platform:  https://platform.minimaxi.com  (MINIMAX_API_BASE=https://api.minimaxi.com)\n"
        "  Global platform: https://www.minimax.io         (MINIMAX_API_BASE=https://api.minimax.io)"
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "camera_direction": True,
    }
    best_for = [
        "direct MiniMax/Hailuo access without a fal.ai account",
        "prompt-following with camera directions (framing, motion, composition)",
        "cost-effective 6s/10s clips at 768P or 1080P",
    ]
    not_good_for = ["offline generation", "very long clips"]
    fallback_tools = ["minimax_video", "kling_video", "veo_video", "wan_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Text prompt. Supports [camera] directions."},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "description": "MiniMax model id. Defaults to MINIMAX_VIDEO_MODEL or MiniMax-Hailuo-02.",
            },
            "duration": {"type": "integer", "enum": [6, 10], "default": 6},
            "resolution": {"type": "string", "enum": ["512P", "768P", "1080P"], "default": "768P"},
            "first_frame_image": {
                "type": "string",
                "description": "For image_to_video: a public image URL or a local image path (sent as base64 data URI).",
            },
            "prompt_optimizer": {"type": "boolean", "default": True},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "duration", "resolution"]
    side_effects = ["writes video file to output_path", "calls MiniMax platform API (costs money)"]
    user_visible_verification = ["Watch generated clip for motion coherence and prompt adherence"]

    # ---- config helpers ----
    def _api_key(self) -> str | None:
        return os.environ.get("MINIMAX_API_KEY")

    def _base_url(self) -> str:
        return (os.environ.get("MINIMAX_API_BASE") or DEFAULT_BASE).rstrip("/")

    def _default_model(self) -> str:
        return os.environ.get("MINIMAX_VIDEO_MODEL") or DEFAULT_MODEL

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Rough estimate; MiniMax prices by model/resolution/duration.
        res = inputs.get("resolution", "768P")
        dur = int(inputs.get("duration", 6))
        base = 0.45 if res == "1080P" else 0.30 if res == "768P" else 0.20
        return round(base * (dur / 6.0), 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 120.0 if int(inputs.get("duration", 6)) >= 10 else 80.0

    # ---- helpers ----
    @staticmethod
    def _image_payload(value: str) -> str:
        """Accept a URL as-is; turn a local path into a base64 data URI."""
        if value.startswith("http://") or value.startswith("https://") or value.startswith("data:"):
            return value
        p = Path(value)
        if not p.exists():
            raise FileNotFoundError(f"first_frame_image not found: {value}")
        import base64
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._api_key()
        if not api_key:
            return ToolResult(success=False, error="MINIMAX_API_KEY not set. " + self.install_instructions)

        import requests

        start = time.time()
        base = self._base_url()
        model = inputs.get("model") or self._default_model()
        operation = inputs.get("operation", "text_to_video")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        payload: dict[str, Any] = {
            "model": model,
            "prompt": inputs["prompt"],
            "duration": int(inputs.get("duration", 6)),
            "resolution": inputs.get("resolution", "768P"),
            "prompt_optimizer": bool(inputs.get("prompt_optimizer", True)),
        }
        if operation == "image_to_video":
            img = inputs.get("first_frame_image")
            if not img:
                return ToolResult(success=False, error="image_to_video requires 'first_frame_image'.")
            try:
                payload["first_frame_image"] = self._image_payload(img)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        try:
            # 1) Submit generation task
            submit = requests.post(
                f"{base}/v1/video_generation", headers=headers, json=payload, timeout=60
            )
            submit.raise_for_status()
            sub = submit.json()
            if sub.get("base_resp", {}).get("status_code", 0) != 0:
                return ToolResult(success=False, error=f"MiniMax submit failed: {sub.get('base_resp')}")
            task_id = sub.get("task_id")
            if not task_id:
                return ToolResult(success=False, error=f"MiniMax returned no task_id: {sub}")

            # 2) Poll until done
            file_id = None
            deadline = time.time() + 600  # 10 min hard cap
            while time.time() < deadline:
                time.sleep(5)
                q = requests.get(
                    f"{base}/v1/query/video_generation",
                    headers=headers,
                    params={"task_id": task_id},
                    timeout=30,
                )
                q.raise_for_status()
                qd = q.json()
                status = qd.get("status", "")
                if status == "Success":
                    file_id = qd.get("file_id")
                    break
                if status == "Fail":
                    return ToolResult(success=False, error=f"MiniMax generation failed: {qd.get('base_resp')}")
                # else Queueing / Preparing / Processing -> keep polling
            if not file_id:
                return ToolResult(success=False, error=f"MiniMax task {task_id} timed out before Success.")

            # 3) Retrieve download URL
            fr = requests.get(
                f"{base}/v1/files/retrieve",
                headers=headers,
                params={"file_id": file_id},
                timeout=30,
            )
            fr.raise_for_status()
            frd = fr.json()
            download_url = (frd.get("file") or {}).get("download_url")
            if not download_url:
                return ToolResult(success=False, error=f"MiniMax file retrieve returned no download_url: {frd}")

            # 4) Download mp4
            vid = requests.get(download_url, timeout=300)
            vid.raise_for_status()
            output_path = Path(inputs.get("output_path", "minimax_direct_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(vid.content)

        except requests.HTTPError as e:
            return ToolResult(success=False, error=f"MiniMax HTTP error: {e} :: {getattr(e.response, 'text', '')[:300]}")
        except Exception as e:
            return ToolResult(success=False, error=f"MiniMax direct video generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "minimax",
                "platform": base,
                "model": model,
                "operation": operation,
                "task_id": task_id,
                "file_id": file_id,
                "prompt": inputs["prompt"],
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
