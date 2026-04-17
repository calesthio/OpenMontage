"""MiniMax text-to-speech provider tool.

Uses the MiniMax T2A v2 API (https://api.minimax.io/v1/t2a_v2).
Audio is returned as hex-encoded bytes.
Requires MINIMAX_API_KEY environment variable.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

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

_TTS_ENDPOINT = "https://api.minimax.io/v1/t2a_v2"

# A representative set of English system voices.  Full list at:
# https://platform.minimax.io/faq/system-voice-id
MINIMAX_VOICE_IDS = [
    "English_Graceful_Lady",
    "English_Insightful_Speaker",
    "English_radiant_girl",
    "English_Persuasive_Man",
    "English_Lucky_Robot",
    "English_expressive_narrator",
]


class MiniMaxTTS(BaseTool):
    name = "minimax_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "minimax"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set the MINIMAX_API_KEY environment variable:\n"
        "  export MINIMAX_API_KEY=your_key_here\n"
        "Get a key at https://platform.minimax.io/"
    )
    fallback = "openai_tts"
    fallback_tools = ["openai_tts", "piper_tts"]
    agent_skills = ["text-to-speech"]

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
        "streaming": True,
    }
    best_for = [
        "cost-effective narration with a broad voice catalogue",
        "multilingual productions using a single API key",
    ]
    not_good_for = [
        "fully offline production",
        "voice cloning workflows",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to convert to speech (max 10,000 characters)",
            },
            "voice_id": {
                "type": "string",
                "default": "English_expressive_narrator",
                "description": (
                    "MiniMax system voice ID. "
                    "See https://platform.minimax.io/faq/system-voice-id for the full list."
                ),
            },
            "model": {
                "type": "string",
                "default": "speech-2.8-hd",
                "enum": ["speech-2.8-hd", "speech-2.8-turbo", "speech-2.6-hd", "speech-2.6-turbo"],
                "description": "TTS model to use. speech-2.8-hd is the recommended default.",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.5,
                "maximum": 2.0,
                "description": "Speech rate multiplier.",
            },
            "vol": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.1,
                "maximum": 10.0,
                "description": "Volume level.",
            },
            "pitch": {
                "type": "integer",
                "default": 0,
                "minimum": -12,
                "maximum": 12,
                "description": "Pitch adjustment in semitones.",
            },
            "format": {
                "type": "string",
                "default": "mp3",
                "enum": ["mp3", "pcm", "flac"],
                "description": "Audio output format.",
            },
            "sample_rate": {
                "type": "integer",
                "default": 32000,
                "enum": [8000, 16000, 22050, 24000, 32000, 44100],
                "description": "Audio sample rate in Hz.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice_id", "model", "format"]
    side_effects = ["writes audio file to output_path", "calls MiniMax API"]
    user_visible_verification = ["Listen to generated audio for intelligibility and tone"]

    def get_status(self) -> ToolStatus:
        if os.environ.get("MINIMAX_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Approx $0.10 per 1,000 characters
        return round(len(inputs.get("text", "")) * 0.0001, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="No MiniMax API key. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"MiniMax TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        text = inputs["text"]
        voice_id = inputs.get("voice_id", "English_expressive_narrator")
        model = inputs.get("model", "speech-2.8-hd")
        fmt = inputs.get("format", "mp3")
        sample_rate = inputs.get("sample_rate", 32000)

        payload: dict[str, Any] = {
            "model": model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": inputs.get("speed", 1.0),
                "vol": inputs.get("vol", 1.0),
                "pitch": inputs.get("pitch", 0),
            },
            "audio_setting": {
                "sample_rate": sample_rate,
                "format": fmt,
                "channel": 1,
            },
        }
        if fmt == "mp3":
            payload["audio_setting"]["bitrate"] = 128000

        response = requests.post(
            _TTS_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        data = response.json()
        base_resp = data.get("base_resp", {})
        status_code = base_resp.get("status_code", -1)
        if status_code != 0:
            status_msg = base_resp.get("status_msg", "unknown error")
            return ToolResult(
                success=False,
                error=f"MiniMax TTS API error {status_code}: {status_msg}",
            )

        hex_audio = data.get("data", {}).get("audio", "")
        if not hex_audio:
            return ToolResult(success=False, error="MiniMax TTS returned empty audio.")

        audio_bytes = bytes.fromhex(hex_audio)

        output_path = Path(inputs.get("output_path", f"minimax_tts.{fmt}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice_id": voice_id,
                "text_length": len(text),
                "audio_bytes": len(audio_bytes),
                "format": fmt,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            model=model,
        )
