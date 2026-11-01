"""Generate music with ElevenLabs Music through fal.ai.

This provider uses OpenMontage's shared ``FAL_KEY`` credential and the fal.ai
queue API, then downloads the generated MP3 to a project-local path.
"""

from __future__ import annotations

import math
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


class FalElevenLabsMusic(BaseTool):
    """Generate a precisely timed music track through fal.ai."""

    name = "fal_elevenlabs_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "fal.ai"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:FAL_KEY"]
    install_instructions = (
        "Set FAL_KEY to a fal.ai API key. "
        "Get one at https://fal.ai/dashboard/keys"
    )
    fallback_tools = ["music_gen", "google_music"]
    agent_skills = ["music", "elevenlabs"]

    capabilities = [
        "generate_background_music",
        "generate_instrumental",
    ]
    supports = {
        "instrumental": True,
        "style_control": True,
        "exact_duration": True,
    }
    best_for = [
        "precisely timed instrumental background music",
        "high-quality ElevenLabs Music through a shared fal.ai account",
        "short-form social video soundtracks",
    ]
    not_good_for = [
        "offline generation",
        "free music sourcing",
        "sub-3-second sound effects",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt", "duration_seconds"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Music description including mood, style, and instruments",
            },
            "duration_seconds": {
                "type": "number",
                "minimum": 3,
                "maximum": 600,
                "description": "Exact target length in seconds",
            },
            "force_instrumental": {
                "type": "boolean",
                "default": True,
                "description": "Generate music without vocals",
            },
            "output_path": {
                "type": "string",
                "default": "fal_music_output.mp3",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=256,
        vram_mb=0,
        disk_mb=50,
        network_required=True,
    )
    retry_policy = RetryPolicy(
        max_retries=0,
        retryable_errors=["rate_limit", "timeout"],
    )
    idempotency_key_fields = ["prompt", "duration_seconds", "force_instrumental"]
    side_effects = [
        "writes an MP3 file to output_path",
        "submits one paid fal.ai generation request",
    ]
    user_visible_verification = [
        "Listen to the generated music for mood, mix, and duration",
    ]

    _MODEL = "fal-ai/elevenlabs/music"
    _QUEUE_URL = f"https://queue.fal.run/{_MODEL}"
    _POLL_INTERVAL_SECONDS = 5
    _MAX_WAIT_SECONDS = 600

    def _get_api_key(self) -> str | None:
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._get_api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """fal bills $0.80 per output minute, rounded up to a full minute."""
        duration = inputs.get("duration_seconds")
        if duration is None:
            raise ValueError("duration_seconds is required for cost estimation")
        return round(math.ceil(float(duration) / 60.0) * 0.80, 2)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="No fal.ai API key found. " + self.install_instructions,
            )

        duration = inputs.get("duration_seconds")
        if duration is None:
            return ToolResult(success=False, error="duration_seconds is required")
        duration = float(duration)
        if not 3 <= duration <= 600:
            return ToolResult(
                success=False,
                error="duration_seconds must be between 3 and 600",
            )

        import requests

        started = time.time()
        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": inputs["prompt"],
            "music_length_ms": round(duration * 1000),
            "force_instrumental": bool(inputs.get("force_instrumental", True)),
        }

        try:
            submit_response = requests.post(
                self._QUEUE_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit_response.raise_for_status()
            queue_data = submit_response.json()
            status_url = queue_data["status_url"]
            response_url = queue_data["response_url"]

            deadline = time.monotonic() + self._MAX_WAIT_SECONDS
            while True:
                if time.monotonic() >= deadline:
                    return ToolResult(
                        success=False,
                        error="fal.ai music generation timed out while waiting in the queue",
                        duration_seconds=round(time.time() - started, 2),
                    )
                time.sleep(self._POLL_INTERVAL_SECONDS)
                status_response = requests.get(status_url, headers=headers, timeout=20)
                status_response.raise_for_status()
                status = status_response.json().get("status", "UNKNOWN")
                if status == "COMPLETED":
                    break
                if status in {"FAILED", "CANCELLED"}:
                    return ToolResult(
                        success=False,
                        error=f"fal.ai music generation {status.lower()}",
                        duration_seconds=round(time.time() - started, 2),
                    )

            result_response = requests.get(response_url, headers=headers, timeout=30)
            result_response.raise_for_status()
            result_data = result_response.json()
            audio_url = result_data["audio"]["url"]

            audio_response = requests.get(audio_url, timeout=120)
            audio_response.raise_for_status()
            output_path = Path(inputs.get("output_path", "fal_music_output.mp3"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_response.content)
        except Exception as exc:
            safe_error = str(exc).replace(api_key, "[REDACTED]")
            return ToolResult(
                success=False,
                error=f"fal.ai ElevenLabs Music generation failed: {safe_error}",
                duration_seconds=round(time.time() - started, 2),
            )

        return ToolResult(
            success=True,
            data={
                "provider": "fal.ai",
                "model": self._MODEL,
                "prompt": inputs["prompt"],
                "duration_seconds": duration,
                "force_instrumental": payload["force_instrumental"],
                "output": str(output_path),
                "format": "mp3",
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - started, 2),
            model=self._MODEL,
        )
