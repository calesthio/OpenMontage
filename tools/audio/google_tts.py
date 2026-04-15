"""Google Cloud Text-to-Speech provider tool.

Google TTS offers 700+ voices across 50+ languages, including Standard,
WaveNet, Neural2, Studio, and Journey voice types — strong for localization.
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


class GoogleTTS(BaseTool):
    name = "google_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "google_tts"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set GOOGLE_API_KEY to your Google Cloud API key with Text-to-Speech enabled.\n"
        "  Enable the API at https://console.cloud.google.com/apis/library/texttospeech.googleapis.com\n"
        "  Or use GOOGLE_APPLICATION_CREDENTIALS for service account auth."
    )
    fallback = "openai_tts"
    fallback_tools = ["openai_tts", "elevenlabs_tts", "piper_tts"]
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "ssml_support",
        "multilingual",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "ssml": True,
    }
    best_for = [
        "localization — 700+ voices across 50+ languages",
        "affordable high-quality TTS (Neural2, WaveNet)",
        "Google ecosystem integration",
    ]
    not_good_for = [
        "voice cloning",
        "fully offline production",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "voice": {
                "type": "string",
                "default": "en-US-Chirp3-HD-Orus",
                "description": "Voice name. Default tier is Chirp 3 HD (2024, most natural). Examples: en-US-Chirp3-HD-Orus (male, rich/cinematic), en-US-Chirp3-HD-Aoede (female, warm). Legacy tiers: en-US-Studio-O, en-US-Neural2-D, en-US-Journey-D.",
            },
            "language_code": {
                "type": "string",
                "default": "en-US",
                "description": "BCP-47 language code (e.g. en-US, es-ES, ja-JP, fr-FR)",
            },
            "speaking_rate": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.25,
                "maximum": 4.0,
                "description": "Speaking speed. 1.0 = normal, 0.5 = half speed, 2.0 = double speed",
            },
            "pitch": {
                "type": "number",
                "default": 0.0,
                "minimum": -20.0,
                "maximum": 20.0,
                "description": "Pitch adjustment in semitones. 0.0 = default",
            },
            "audio_encoding": {
                "type": "string",
                "default": "MP3",
                "enum": ["MP3", "LINEAR16", "OGG_OPUS", "MULAW", "ALAW"],
                "description": "Audio output encoding format",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice", "language_code", "speaking_rate", "pitch"]
    side_effects = ["writes audio file to output_path", "calls Google Cloud TTS API"]
    user_visible_verification = ["Listen to generated audio for natural speech quality"]

    # Extension mapping for audio encodings
    _EXT_MAP = {
        "MP3": "mp3",
        "LINEAR16": "wav",
        "OGG_OPUS": "ogg",
        "MULAW": "wav",
        "ALAW": "wav",
    }

    def _get_api_key(self) -> str | None:
        return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key() or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    # Voices requiring the v1beta1 endpoint (Chirp 3 HD, Journey)
    _BETA_VOICE_PREFIXES = ("Chirp", "Journey")

    def _needs_beta_api(self, voice: str) -> bool:
        """Check if voice requires the v1beta1 endpoint."""
        return any(prefix in voice for prefix in self._BETA_VOICE_PREFIXES)

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        text = inputs.get("text", "")
        char_count = len(text)
        voice = inputs.get("voice", "en-US-Chirp3-HD-Orus")
        # Pricing per million characters (approximate)
        if "Chirp3-HD" in voice:
            rate_per_char = 0.000030  # $30/1M chars
        elif "Studio" in voice:
            rate_per_char = 0.000160  # $160/1M chars
        elif "Neural2" in voice or "Journey" in voice:
            rate_per_char = 0.000016  # $16/1M chars
        elif "WaveNet" in voice:
            rate_per_char = 0.000016  # $16/1M chars
        else:
            rate_per_char = 0.000004  # $4/1M chars (Standard)
        return round(char_count * rate_per_char, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="No Google API key found. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"Google TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        import requests

        text = inputs["text"]
        voice_name = inputs.get("voice", "en-US-Chirp3-HD-Orus")
        language_code = inputs.get("language_code", "en-US")
        speaking_rate = inputs.get("speaking_rate", 1.0)
        pitch = inputs.get("pitch", 0.0)
        audio_encoding = inputs.get("audio_encoding", "MP3")

        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": language_code,
                "name": voice_name,
            },
            "audioConfig": {
                "audioEncoding": audio_encoding,
                "speakingRate": speaking_rate,
                "pitch": pitch,
            },
        }

        # Chirp 3 HD and Journey voices require the v1beta1 endpoint
        api_version = "v1beta1" if self._needs_beta_api(voice_name) else "v1"
        url = f"https://texttospeech.googleapis.com/{api_version}/text:synthesize"

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            params={"key": api_key},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        audio_content = base64.b64decode(response.json()["audioContent"])

        ext = self._EXT_MAP.get(audio_encoding, "mp3")
        output_path = Path(inputs.get("output_path", f"tts_output.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_content)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice": voice_name,
                "language_code": language_code,
                "text_length": len(text),
                "output": str(output_path),
                "format": audio_encoding,
                "speaking_rate": speaking_rate,
                "pitch": pitch,
            },
            artifacts=[str(output_path)],
            model=f"google-tts/{voice_name}",
        )
