"""DolphinLitePark MaaS platform video generation tool.

Calls the internal MaaS gateway at /v1/video/generations using an async
polling pattern. Supports text-to-video, image-to-video, reference-to-video
and video-edit across 16 models from Volcengine Seedance, DashScope Wan /
HappyHorse, H100/LTX and the fanya alias.

Gateway base URL: https://api.aiapbot.com (override via MAAS_API_BASE)
Auth:            Authorization: Bearer <MAAS_API_KEY>
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


# Default poll interval recommended by the gateway (seconds)
_POLL_INTERVAL = 5
# Give up after this many seconds total
_POLL_TIMEOUT = 600


class MaasVideo(BaseTool):
    name = "maas_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "maas"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MAAS_API_KEY"]
    install_instructions = (
        "Set MAAS_API_KEY to your DolphinLitePark API key (sk-dlp-...).\n"
        "Optionally set MAAS_API_BASE to override the gateway URL\n"
        "(default: https://api.aiapbot.com)."
    )
    agent_skills = ["ai-video-gen", "seedance-2-0"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video", "video_edit"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "video_edit": True,
        "native_audio": True,
        "cinematic_quality": True,
        "multiple_resolutions": True,
    }
    best_for = [
        "internal MaaS quota — billed in CNY, no external API key needed",
        "Seedance 2.0 cinematic T2V/I2V (volcengine/doubao-seedance-2.0)",
        "HappyHorse 1.0 high-end production (720p–1080p)",
        "Wan 2.7 cost-effective I2V and video-edit",
        "LTX-2.3 via self-hosted H100 GPU cluster",
    ]
    not_good_for = [
        "offline / air-gapped environments",
        "access without a valid MAAS_API_KEY (sk-dlp-...)",
    ]
    fallback_tools = ["seedance_video", "wan_video", "kling_video"]

    # ── Model catalogue (sourced from maas.aiapbot.com/models, 2026-06-28) ──
    # 16 video models across 4 provider families.
    # Pricing is in CNY per second of generated video.
    MODELS = {
        # ── Volcengine Seedance ───────────────────────────────────────────────
        # Recommended default: cinematic quality, 3D camera motion
        "volcengine/doubao-seedance-2.0":        {"ops": ["t2v", "i2v"], "price_480p": 0.60, "price_720p": 1.00},
        "volcengine/doubao-seedance-2.0-fast":   {"ops": ["t2v", "i2v"], "price_480p": 0.63, "price_720p": 1.42},
        "volcengine/doubao-seedance-1.5-pro":    {"ops": ["t2v", "i2v"], "price_720p": 1.04},
        "volcengine/doubao-seedance-1.0-pro":    {"ops": ["t2v", "i2v"], "price_720p": 0.65},
        "volcengine/doubao-seedance-1.0-pro-fast": {"ops": ["t2v"],      "price_720p": 1.19},
        # fanya alias → same Seedance 2.0 backend
        "fanya/seedance2.0":                     {"ops": ["t2v", "i2v"], "price_480p": 0.75, "price_720p": 1.25},
        # ── DashScope Wan 2.7 ────────────────────────────────────────────────
        "wan2.7-i2v":                            {"ops": ["i2v"],        "price_720p": 0.22},
        "wan2.7-videoedit":                      {"ops": ["video_edit"], "price_720p": 0.22},
        # ── DashScope Wanx 2.1 (per-clip billing, not per-second) ───────────
        "wanx2.1-t2v-plus":                      {"ops": ["t2v"],        "price_per_clip": 0.83},
        "wanx2.1-t2v-turbo":                     {"ops": ["t2v"],        "price_per_clip": 0.50},
        "wanx2.1-i2v-plus":                      {"ops": ["i2v"],        "price_per_clip": 0.83},
        # ── DashScope HappyHorse 1.0 (high-end) ─────────────────────────────
        "happyhorse-1.0-t2v":                    {"ops": ["t2v"],        "price_720p": 1.17, "price_1080p": 2.08},
        "happyhorse-1.0-i2v":                    {"ops": ["i2v"],        "price_720p": 1.17, "price_1080p": 2.08},
        "happyhorse-1.0-r2v":                    {"ops": ["r2v"],        "price_720p": 1.17, "price_1080p": 2.08},
        "happyhorse-1.0-video-edit":             {"ops": ["video_edit"], "price_720p": 1.17, "price_1080p": 2.08},
        # ── H100 Self-hosted GPU Cluster ─────────────────────────────────────
        "h100/ltx-2.3":                          {"ops": ["t2v"],        "price_480p": 0.50, "price_720p": 0.70},
    }
    DEFAULT_MODEL = "volcengine/doubao-seedance-2.0"

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Video generation prompt"},
            "model": {
                "type": "string",
                "description": (
                    "Gateway model ID. Available models (16 total):\n"
                    "T2V: volcengine/doubao-seedance-2.0 (default), volcengine/doubao-seedance-2.0-fast, "
                    "volcengine/doubao-seedance-1.5-pro, volcengine/doubao-seedance-1.0-pro, "
                    "volcengine/doubao-seedance-1.0-pro-fast, fanya/seedance2.0, "
                    "wanx2.1-t2v-plus, wanx2.1-t2v-turbo, happyhorse-1.0-t2v, h100/ltx-2.3\n"
                    "I2V: wan2.7-i2v, wanx2.1-i2v-plus, happyhorse-1.0-i2v\n"
                    "R2V: happyhorse-1.0-r2v\n"
                    "Edit: wan2.7-videoedit, happyhorse-1.0-video-edit"
                ),
                "default": "volcengine/doubao-seedance-2.0",
            },
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video", "video_edit"],
                "default": "text_to_video",
            },
            "duration_seconds": {
                "type": "integer",
                "enum": [5, 10],
                "default": 5,
                "description": "Clip duration in seconds",
            },
            "resolution": {
                "type": "string",
                "enum": ["480p", "720p", "1080p"],
                "default": "720p",
                "description": "Output resolution (affects billing tier)",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1"],
                "default": "16:9",
            },
            "audio": {
                "type": "boolean",
                "default": True,
                "description": "Include audio track in generated video",
            },
            "image_url": {
                "type": "string",
                "description": "Public image URL for image_to_video operation",
            },
            "output_path": {"type": "string", "description": "Local path to save the MP4"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "rate_limit"])
    idempotency_key_fields = ["prompt", "model", "duration_seconds", "resolution"]
    side_effects = ["writes video file to output_path", "calls MaaS gateway API"]
    user_visible_verification = [
        "Watch generated clip for motion coherence and visual quality"
    ]

    def _api_key(self) -> str | None:
        return os.environ.get("MAAS_API_KEY")

    def _base_url(self) -> str:
        return os.environ.get("MAAS_API_BASE", "https://api.aiapbot.com").rstrip("/")

    def get_status(self) -> ToolStatus:
        if self._api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Return estimated cost in CNY (not USD — MaaS bills internally in CNY)."""
        model = inputs.get("model", self.DEFAULT_MODEL)
        info = self.MODELS.get(model, {})
        duration = inputs.get("duration_seconds", 5)
        resolution = inputs.get("resolution", "720p")

        if "price_per_clip" in info:
            return info["price_per_clip"]

        price_key = f"price_{resolution}"
        rate = info.get(price_key) or info.get("price_720p") or info.get("price_480p") or 0.0
        return round(rate * duration, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        duration = inputs.get("duration_seconds", 5)
        # Seedance 2.0 typically takes 60-120s; longer clips take more time
        return 90.0 + (duration - 5) * 15.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="MAAS_API_KEY not set. " + self.install_instructions,
            )

        base_url = self._base_url()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        model = inputs.get("model", self.DEFAULT_MODEL)
        operation = inputs.get("operation", "text_to_video")
        duration = inputs.get("duration_seconds", 5)
        resolution = inputs.get("resolution", "720p")

        payload: dict[str, Any] = {
            "model": model,
            "prompt": inputs["prompt"],
            "duration_seconds": duration,
            "resolution": resolution,
            "audio": inputs.get("audio", True),
        }
        if inputs.get("aspect_ratio"):
            payload["ratio"] = inputs["aspect_ratio"]
        if operation == "image_to_video" and inputs.get("image_url"):
            payload["image_url"] = inputs["image_url"]

        start = time.time()

        # ── Step 1: Submit job ────────────────────────────────────────────────
        try:
            resp = requests.post(
                f"{base_url}/v1/video/generations",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            return ToolResult(success=False, error=f"MaaS submit failed: {e}")

        job_data = resp.json()
        job_id = job_data.get("job_id")
        if not job_id:
            return ToolResult(
                success=False,
                error=f"No job_id in gateway response: {job_data}",
            )

        # ── Step 2: Poll for completion ───────────────────────────────────────
        deadline = start + _POLL_TIMEOUT
        while time.time() < deadline:
            time.sleep(_POLL_INTERVAL)
            try:
                poll_resp = requests.get(
                    f"{base_url}/v1/video/jobs/{job_id}",
                    headers=headers,
                    timeout=15,
                )
                poll_resp.raise_for_status()
            except Exception as e:
                return ToolResult(success=False, error=f"MaaS poll failed: {e}")

            status_data = poll_resp.json()
            status = status_data.get("status", "unknown")

            if status == "succeeded":
                break
            if status in ("failed", "cancelled"):
                err = status_data.get("error") or f"Job {status}"
                return ToolResult(success=False, error=f"MaaS video generation {status}: {err}")
            # still processing — keep polling

        else:
            return ToolResult(
                success=False,
                error=f"MaaS video generation timed out after {_POLL_TIMEOUT}s (job_id={job_id})",
            )

        # ── Step 3: Download result ───────────────────────────────────────────
        output_path = Path(inputs.get("output_path", f"maas_{job_id}.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            dl_resp = requests.get(
                f"{base_url}/v1/video/jobs/{job_id}/result",
                headers=headers,
                stream=True,
                timeout=120,
            )
            dl_resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in dl_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            return ToolResult(success=False, error=f"MaaS video download failed: {e}")

        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": "maas",
                "model": model,
                "prompt": inputs["prompt"],
                "operation": operation,
                "resolution": resolution,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "job_id": job_id,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
