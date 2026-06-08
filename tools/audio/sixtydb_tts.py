"""60db.ai text-to-speech provider tool.

Wraps the REST endpoint `POST https://api.60db.ai/tts-synthesize`.
Mirrors the ElevenLabsTTS contract so callers can swap providers via
tts_selector without changing input shape.
"""

from __future__ import annotations

import base64
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


class SixtyDbTTS(BaseTool):
    name = "sixtydb_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "sixtydb"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set the SIXTYDB_API_KEY environment variable:\n"
        "  export SIXTYDB_API_KEY=your_key_here\n"
        "Get a key at https://60db.ai"
    )
    fallback = "elevenlabs_tts"
    fallback_tools = ["elevenlabs_tts", "openai_tts", "piper_tts"]
    agent_skills = ["sixtydb", "text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "audio_enhancement",
        "multilingual_indic",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "Indic-language narration (Hindi, Bengali, Tamil, Telugu, etc.)",
        "low-cost API-based TTS",
        "enhanced-quality voiceover with built-in audio enhance",
    ]
    not_good_for = [
        "fully offline production",
        "voice cloning workflows",
    ]

    # Schema kept on 0..1 ranges for parity with ElevenLabs / tts_selector.
    # Values are rescaled to 0..100 inside _generate() before hitting the API.
    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to convert to speech (max 5000 chars).",
                "maxLength": 5000,
            },
            "voice_id": {
                "type": "string",
                "description": "60db voice UUID (defaults to system voice).",
            },
            "model_id": {
                "type": "string",
                "description": "Accepted for cross-provider parity; 60db ignores this field.",
            },
            "stability": {
                "type": "number",
                "default": 0.5,
                "minimum": 0,
                "maximum": 1,
                "description": "0..1 — auto-scaled to 0..100 for 60db.",
            },
            "similarity_boost": {
                "type": "number",
                "default": 0.75,
                "minimum": 0,
                "maximum": 1,
                "description": "0..1 — auto-scaled to 0..100 for 60db (sent as 'similarity').",
            },
            "style": {
                "type": "number",
                "default": 0.0,
                "minimum": 0,
                "maximum": 1,
                "description": "Accepted for parity; 60db has no equivalent and ignores this.",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.5,
                "maximum": 2.0,
            },
            "enhance": {
                "type": "boolean",
                "default": True,
                "description": "60db audio quality enhancement.",
            },
            "output_path": {"type": "string"},
            "output_format": {
                "type": "string",
                "default": "mp3_44100_128",
                "description": (
                    "Accepts bare 60db values (mp3|wav|ogg|flac) or ElevenLabs-style "
                    "tokens (mp3_44100_128, pcm_16000, …); only the codec prefix is used."
                ),
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice_id", "speed", "stability", "similarity_boost"]
    side_effects = ["writes audio file to output_path", "calls 60db API"]
    user_visible_verification = ["Listen to generated audio for natural speech quality"]

    DEFAULT_VOICE_ID = "fbb75ed2-975a-40c7-9e06-38e30524a9a1"
    API_URL = "https://api.60db.ai/tts-synthesize"
    # WebSocket pricing doc: $0.00002/char; treat as best estimate for REST.
    COST_PER_CHAR_USD = 0.00002

    # Accepted bare codecs per 60db spec.
    _SUPPORTED_CODECS = {"mp3", "wav", "ogg", "flac"}

    def get_status(self) -> ToolStatus:
        if os.environ.get("SIXTYDB_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return round(len(inputs.get("text", "")) * self.COST_PER_CHAR_USD, 6)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("SIXTYDB_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="No 60db API key. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _normalize_format(cls, raw: str) -> str:
        """Map either bare ('mp3') or ElevenLabs-style ('mp3_44100_128') to a
        60db-accepted codec name."""
        if not raw:
            return "mp3"
        prefix = raw.lower().split("_", 1)[0]
        # 60db accepts mp3/wav/ogg/flac; pcm has no 60db equivalent → fall back to wav.
        if prefix == "pcm":
            return "wav"
        return prefix if prefix in cls._SUPPORTED_CODECS else "mp3"

    @staticmethod
    def _scale_unit_to_pct(value: Any, default_unit: float) -> int:
        """Convert a 0..1 input into the 0..100 integer scale the API uses."""
        try:
            v = float(value if value is not None else default_unit)
        except (TypeError, ValueError):
            v = default_unit
        v = max(0.0, min(1.0, v))
        return int(round(v * 100))

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        import requests

        text = inputs["text"]
        voice_id = inputs.get("voice_id") or self.DEFAULT_VOICE_ID
        output_codec = self._normalize_format(inputs.get("output_format", "mp3_44100_128"))

        payload: dict[str, Any] = {
            "text": text,
            "voice_id": voice_id,
            "enhance": bool(inputs.get("enhance", True)),
            "speed": float(inputs.get("speed", 1.0)),
            "stability": self._scale_unit_to_pct(inputs.get("stability"), 0.5),
            "similarity": self._scale_unit_to_pct(inputs.get("similarity_boost"), 0.75),
            "output_format": output_codec,
        }

        response = requests.post(
            self.API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        body = response.json()

        if not body.get("success", True) or not body.get("audio_base64"):
            return ToolResult(
                success=False,
                error=f"60db returned no audio: {body.get('message', 'unknown error')}",
            )

        try:
            audio_bytes = base64.b64decode(body["audio_base64"])
        except (ValueError, TypeError) as exc:
            return ToolResult(success=False, error=f"60db audio_base64 decode failed: {exc}")

        ext = body.get("output_format", output_codec) or output_codec
        output_path = Path(inputs.get("output_path", f"tts_output.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice_id": voice_id,
                "text_length": len(text),
                "output": str(output_path),
                "format": ext,
                "sample_rate": body.get("sample_rate"),
                "encoding": body.get("encoding"),
                "reported_duration_seconds": body.get("duration_seconds"),
            },
            artifacts=[str(output_path)],
            model="60db-tts-synthesize",
        )
