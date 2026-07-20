"""DashScope (Alibaba Cloud Bailian) text-to-speech via Qwen-TTS models.

Uses the DashScope-native multimodal-generation endpoint (same as image gen).
The response contains a temporary audio URL (WAV, valid ~24h) that must be
downloaded separately — unlike OpenAI TTS which returns raw audio bytes.
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


class DashscopeTTS(BaseTool):
    name = "dashscope_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "dashscope"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set DASHSCOPE_API_KEY to your Alibaba Cloud DashScope API key.\n"
        "  Get one at https://dashscope.aliyun.com/"
    )
    fallback = "piper_tts"
    fallback_tools = [
        "doubao_tts",
        "elevenlabs_tts",
        "openai_tts",
        "piper_tts",
    ]
    agent_skills = ["dashscope"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "multilingual",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "natural Mandarin and multilingual narration via Qwen-TTS",
        "cost-effective TTS via Alibaba Cloud",
        "Chinese-language voiceover production",
    ]
    not_good_for = [
        "fully offline production",
        "voice clone matching",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "Text to convert to speech "
                    "(max 600 chars for qwen3-tts-flash)."
                ),
            },
            "model": {
                "type": "string",
                "enum": [
                    "qwen3-tts-flash",
                    "qwen3-tts-instruct-flash",
                    "qwen-tts-2025-05-22",
                ],
                "default": "qwen3-tts-flash",
            },
            "voice": {
                "type": "string",
                "default": "Cherry",
                "description": (
                    'DashScope voice name. Examples: "Cherry", "Ethan", '
                    '"Chelsie".'
                ),
            },
            "language_type": {
                "type": "string",
                "default": "Auto",
                "enum": ["Auto", "Chinese", "English", "Japanese", "Korean"],
                "description": "Language hint for the TTS model.",
            },
            "instructions": {
                "type": "string",
                "description": (
                    "Natural language delivery instructions "
                    "(only for qwen3-tts-instruct-flash)."
                ),
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["text", "voice", "model", "language_type", "instructions"]
    side_effects = [
        "writes audio file to output_path",
        "calls DashScope (Alibaba Cloud) TTS API",
    ]
    user_visible_verification = [
        "Listen to generated audio for naturalness and pacing"
    ]

    ENDPOINT = (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
        "multimodal-generation/generation"
    )

    def get_status(self) -> ToolStatus:
        if os.environ.get("DASHSCOPE_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Conservative per-character estimate; DashScope bills by character.
        return round(len(inputs.get("text", "")) * 0.000015, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="DASHSCOPE_API_KEY not set. " + self.install_instructions,
            )

        import requests

        from tools.analysis.audio_probe import probe_duration

        start = time.time()
        try:
            payload = self._build_payload(inputs)
            response = requests.post(
                self.ENDPOINT,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            audio_info = data.get("output", {}).get("audio", {})
            audio_url = audio_info.get("url")
            if not audio_url:
                return ToolResult(
                    success=False,
                    error="DashScope TTS returned no audio URL",
                )

            # Download the audio from the temporary URL (valid ~24h).
            download = requests.get(audio_url, timeout=120)
            download.raise_for_status()

            output_path = Path(
                inputs.get("output_path", "dashscope_tts.wav")
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(download.content)

            audio_duration = probe_duration(output_path)
            usage = data.get("usage", {})

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"DashScope TTS failed: {self._safe_error(e)}",
            )

        return ToolResult(
            success=True,
            data={
                "provider": "dashscope",
                "model": payload["model"],
                "voice": payload["input"]["voice"],
                "language_type": payload["input"].get("language_type", "Auto"),
                "text_length": len(inputs["text"]),
                "audio_duration_seconds": (
                    round(audio_duration, 2) if audio_duration else None
                ),
                "output": str(output_path),
                "audio_url": audio_url,
                "usage": usage,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=payload["model"],
        )

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        input_data: dict[str, Any] = {
            "text": inputs["text"],
            "voice": inputs.get("voice", "Cherry"),
            "language_type": inputs.get("language_type", "Auto"),
        }
        if inputs.get("instructions"):
            input_data["instructions"] = inputs["instructions"]
            input_data["optimize_instructions"] = True

        return {
            "model": inputs.get("model", "qwen3-tts-flash"),
            "input": input_data,
        }

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        return str(exc).replace(
            os.environ.get("DASHSCOPE_API_KEY", ""), "[redacted]"
        )
