"""Gemini native text-to-speech provider tool.

Uses Gemini's generateContent API with response_modalities=["AUDIO"]
for expressive, context-aware speech synthesis. Supports 30 voices
with automatic language detection.
"""

from __future__ import annotations

import base64
import os
import time
import wave
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

# All 30 prebuilt Gemini TTS voices
VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird",
    "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]

MODELS = [
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-preview-tts",
]

# Gemini TTS returns raw PCM: 24kHz, mono, 16-bit signed little-endian
SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2


class GeminiTTS(BaseTool):
    name = "gemini_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "gemini"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set GOOGLE_API_KEY (or GEMINI_API_KEY) to your Google AI Studio key.\n"
        "  Get one at https://aistudio.google.com/apikey\n"
        "  Same key works for Gemini TTS, Imagen, and Google Cloud TTS."
    )
    fallback = "google_tts"
    fallback_tools = ["google_tts", "elevenlabs_tts", "piper_tts"]
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "expressive_delivery",
        "multilingual",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "ssml": False,
    }
    best_for = [
        "expressive narration — understands context and delivers with natural prosody",
        "prompt-directed delivery — 'say cheerfully', 'whisper this', etc.",
        "multilingual with automatic language detection",
    ]
    not_good_for = [
        "SSML markup (not supported)",
        "voice cloning",
        "fully offline production",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "Text to convert to speech. Supports delivery instructions "
                    "inline, e.g. 'Say cheerfully: Have a wonderful day!'"
                ),
            },
            "voice": {
                "type": "string",
                "default": "Orus",
                "description": (
                    f"Voice name. Available: {', '.join(VOICES)}. "
                    "Default: Orus (rich, cinematic male)."
                ),
            },
            "model": {
                "type": "string",
                "default": "gemini-2.5-flash-preview-tts",
                "enum": MODELS,
                "description": (
                    "Gemini TTS model. flash = fast/cheap, pro = highest quality."
                ),
            },
            "audio_format": {
                "type": "string",
                "default": "wav",
                "enum": ["wav", "pcm"],
                "description": "Output format. wav = ready to use, pcm = raw 24kHz s16le.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice", "model"]
    side_effects = ["writes audio file to output_path", "calls Gemini API"]
    user_visible_verification = ["Listen to generated audio for natural speech quality"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        text = inputs.get("text", "")
        model = inputs.get("model", "gemini-2.5-flash-preview-tts")
        # Approximate pricing per character (Gemini TTS pricing is per-token
        # but characters are a reasonable proxy for estimation)
        if "pro" in model:
            rate_per_char = 0.000050  # pro is more expensive
        else:
            rate_per_char = 0.000010  # flash is cheap
        return round(len(text) * rate_per_char, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="No Google API key found. " + self.install_instructions,
            )

        voice = inputs.get("voice", "Orus")
        if voice not in VOICES:
            return ToolResult(
                success=False,
                error=f"Unknown voice '{voice}'. Available: {', '.join(VOICES)}",
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"Gemini TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        import requests

        text = inputs["text"]
        voice = inputs.get("voice", "Orus")
        model = inputs.get("model", "gemini-2.5-flash-preview-tts")
        audio_format = inputs.get("audio_format", "wav")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice,
                        }
                    }
                },
            },
        }

        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            json=payload,
            timeout=120,
        )

        # Issue #3: extract API error body before raising
        if not response.ok:
            try:
                err_msg = response.json().get("error", {}).get("message", response.text[:500])
            except Exception:
                err_msg = response.text[:500]
            raise RuntimeError(f"Gemini API error (HTTP {response.status_code}): {err_msg}")

        data = response.json()

        # Issue #2: guard against missing/blocked candidates
        candidates = data.get("candidates")
        if not candidates:
            error_info = data.get("error", {}).get("message", "No candidates in response")
            raise RuntimeError(f"Gemini API returned no audio: {error_info}")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "")
        if finish_reason == "SAFETY":
            raise RuntimeError("Gemini blocked this request due to safety filters. Rephrase your text.")

        try:
            audio_b64 = candidate["content"]["parts"][0]["inlineData"]["data"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected Gemini response structure: {exc}") from exc

        pcm_bytes = base64.b64decode(audio_b64)

        # Issue #4: reject empty audio
        if not pcm_bytes:
            raise RuntimeError("Gemini returned empty audio data. The text may be too short or unsupported.")

        # Issue #5: audio_format is already constrained by enum, use directly
        output_path = Path(inputs.get("output_path", f"gemini_tts_output.{audio_format}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if audio_format == "wav":
            _write_wav(output_path, pcm_bytes)
        else:
            output_path.write_bytes(pcm_bytes)

        audio_duration = len(pcm_bytes) / (SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice": voice,
                "text_length": len(text),
                "audio_duration_seconds": round(audio_duration, 2),
                "sample_rate": SAMPLE_RATE,
                "output": str(output_path),
                "format": audio_format,
            },
            artifacts=[str(output_path)],
            model=model,
        )


def _write_wav(path: Path, pcm_bytes: bytes) -> None:
    """Wrap raw PCM bytes in a WAV container."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
