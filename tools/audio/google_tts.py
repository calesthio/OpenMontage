"""Google Text-to-Speech provider tool.

Supports two modes:
- AI Studio mode (GEMINI_API_KEY / GOOGLE_API_KEY): uses the Gemini TTS endpoint
  at generativelanguage.googleapis.com — no Cloud TTS API needed.
- Cloud TTS mode (GOOGLE_APPLICATION_CREDENTIALS): uses texttospeech.googleapis.com
  with service-account auth — 700+ voices across 50+ languages.
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
        "AI Studio mode (recommended — no Cloud API setup needed):\n"
        "  Set GEMINI_API_KEY (or GOOGLE_API_KEY) to your Google AI Studio key.\n"
        "  Get one free at https://aistudio.google.com/app/apikey\n"
        "  Available Gemini voices: Aoede, Charon, Fenrir, Kore, Orbit, Puck, Zephyr,\n"
        "    Leda, Orus, Perseus, Autonoe, Callirrhoe, Despina, Enceladus, Iapetus,\n"
        "    Rasalas, Schedar, Sulafat, Umbriel, Vindemiatrix, Wasat, Zubenelgenubi\n"
        "  Default voice when using AI Studio mode: Kore\n\n"
        "Cloud TTS mode (service account, 700+ voices):\n"
        "  Set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON key path.\n"
        "  Enable the API at https://console.cloud.google.com/apis/library/texttospeech.googleapis.com\n"
        "  Available voice tiers: Chirp 3 HD, Studio, Neural2, Journey, WaveNet, Standard\n\n"
        "Priority: GEMINI_API_KEY > GOOGLE_API_KEY > GOOGLE_APPLICATION_CREDENTIALS"
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

    def _detect_mode(self) -> str:
        """Return the auth mode to use, in priority order.

        Priority: GEMINI_API_KEY > GOOGLE_API_KEY > GOOGLE_APPLICATION_CREDENTIALS
        Returns "gemini_studio" or "cloud_tts".
        """
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return "gemini_studio"
        return "cloud_tts"

    def get_status(self) -> ToolStatus:
        if (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        ):
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
        mode = self._detect_mode()

        start = time.time()
        try:
            if mode == "gemini_studio":
                api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    return ToolResult(
                        success=False,
                        error="No Gemini/Google API key found. " + self.install_instructions,
                    )
                result = self._synthesize_gemini_studio(
                    text=inputs["text"],
                    voice=inputs.get("voice", "Kore"),
                    language_code=inputs.get("language_code", "en-US"),
                    inputs=inputs,
                )
            else:
                # cloud_tts — existing logic
                api_key = self._get_api_key()
                creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                if not api_key and not creds:
                    return ToolResult(
                        success=False,
                        error="No Google credentials found. " + self.install_instructions,
                    )
                result = self._generate(inputs, api_key or "")
        except Exception as exc:
            return ToolResult(success=False, error=f"Google TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        if result.data is not None:
            result.data["mode"] = mode
        return result

    def _synthesize_gemini_studio(
        self,
        text: str,
        voice: str,
        language_code: str,
        inputs: dict[str, Any],
    ) -> ToolResult:
        """Synthesize speech via the Gemini AI Studio TTS endpoint.

        Uses generativelanguage.googleapis.com — does NOT require Cloud TTS API.
        Returns a ToolResult with the audio written to output_path.
        Audio is returned as WAV by the API (base64-encoded in inlineData).
        """
        import requests

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash-preview-tts:generateContent"
        )
        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": voice,
                        }
                    }
                },
            },
        }

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            params={"key": api_key},
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        inline_data = (
            response.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        )
        audio_bytes = base64.b64decode(inline_data)

        # AI Studio TTS returns WAV audio
        output_path = Path(inputs.get("output_path", "tts_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice": voice,
                "language_code": language_code,
                "text_length": len(text),
                "output": str(output_path),
                "format": "WAV",
            },
            artifacts=[str(output_path)],
            model=f"gemini-tts/{voice}",
        )

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
