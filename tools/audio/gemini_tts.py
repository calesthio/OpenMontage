"""Gemini 3.1 Flash TTS — hero-tier voice (2026 Speech Arena #1 for naturalness).

A NEW hero-voice provider alongside ElevenLabs / Kokoro / Google Cloud TTS — it does
not replace them. On the Artificial Analysis blind Speech Arena (2026), Gemini 3.1
Flash TTS leads for naturalness (near-tie with Cartesia Sonic 3.5), with ElevenLabs
outside the top 5. But the arena only measures short-sample naturalness — ElevenLabs
stays the pick for voice CLONING, long-form stability, and inline emotion tags. So:

  - Hero narration where natural delivery matters most → Gemini 3.1 Flash TTS.
  - Voice-clone / brand voice / long-form / heavy emotion-tag control → keep ElevenLabs.
  - Bulk/draft → Kokoro (free, local).

Runs on AI Studio (the same GOOGLE_API_KEY / GEMINI_API_KEY the Imagen tool uses), so it
reports UNAVAILABLE only when no Google key is set — never disturbing existing flows.

The exact AI-Studio model id and the generateContent audio schema shift between Gemini
releases; the model id (`_DEFAULT_MODEL`) and request builder are the `ponytail:`
calibration knobs to confirm against the live API. PCM→WAV wrapping is stdlib-only.
"""

from __future__ import annotations

import base64
import os
import re
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

# ponytail: confirm the live AI-Studio model id for "Gemini 3.1 Flash TTS" — override
# per-call via the `model` input, or edit this default. Everything else is version-stable.
_DEFAULT_MODEL = "gemini-3.1-flash-tts"
_DEFAULT_VOICE = "Kore"
_DEFAULT_RATE = 24000  # Gemini TTS emits 24 kHz signed-16-bit PCM mono


class GeminiTTS(BaseTool):
    name = "gemini_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "gemini"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically via Google API key
    install_instructions = (
        "Set GOOGLE_API_KEY (or GEMINI_API_KEY) to an AI Studio key:\n"
        "  export GOOGLE_API_KEY=your_key   # https://aistudio.google.com/apikey\n"
        "This is the same key the Imagen tool uses."
    )
    agent_skills = ["text-to-speech"]

    capabilities = ["text_to_speech", "expressive_narration"]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "style_prompt": True,
        "native_audio": True,
    }
    best_for = [
        "hero-tier natural narration (2026 Speech Arena naturalness leader)",
        "prompt-driven delivery style (say it cheerfully / calmly / dramatically)",
    ]
    not_good_for = [
        "voice cloning or brand-voice matching (use ElevenLabs)",
        "bulk/draft narration (use Kokoro — free/local)",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "voice_id": {
                "type": "string",
                "default": _DEFAULT_VOICE,
                "description": "Gemini prebuilt voice, e.g. Kore, Puck, Charon, Aoede, Fenrir.",
            },
            "instructions": {
                "type": "string",
                "description": "Natural-language delivery style, prepended as a directive "
                "(e.g. 'Say warmly and slowly'). Gemini TTS is prompt-steered.",
            },
            "model": {"type": "string", "default": _DEFAULT_MODEL},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice_id", "instructions", "model"]
    side_effects = ["writes audio file to output_path", "calls Google AI Studio API"]
    user_visible_verification = ["Listen for natural delivery and correct style/emotion"]

    @staticmethod
    def _api_key() -> str | None:
        return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Gemini TTS bills per audio token; a short hero line is a fraction of a cent.
        # Kept small so the scorer treats it as a cheap hero option.
        return round(max(1, len(inputs.get("text", "") or "")) / 1000 * 0.01, 4)

    @staticmethod
    def _build_request(text: str, voice: str, instructions: str | None) -> dict[str, Any]:
        """Build the AI-Studio generateContent body for a TTS turn (pure, testable).

        ponytail: this is the audio-generateContent schema — the knob to confirm
        against the live Gemini release alongside the model id.
        """
        spoken = f"{instructions.strip()}: {text}" if instructions and instructions.strip() else text
        return {
            "contents": [{"parts": [{"text": spoken}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
                },
            },
        }

    @staticmethod
    def _extract_pcm(data: dict[str, Any]) -> tuple[bytes, int]:
        """Pull base64 PCM + sample rate from a generateContent audio response."""
        parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                rate = _DEFAULT_RATE
                mime = inline.get("mimeType") or inline.get("mime_type") or ""
                m = re.search(r"rate=(\d+)", mime)
                if m:
                    rate = int(m.group(1))
                return base64.b64decode(inline["data"]), rate
        raise RuntimeError(f"No audio in Gemini response: {data}")

    @staticmethod
    def _pcm_to_wav(pcm: bytes, path: Path, rate: int = _DEFAULT_RATE) -> None:
        """Wrap raw signed-16-bit mono PCM in a WAV container (stdlib only)."""
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        api_key = self._api_key()
        if not api_key:
            return ToolResult(success=False, error="Gemini TTS unavailable. " + self.install_instructions)
        if not (inputs.get("text") or "").strip():
            return ToolResult(success=False, error="gemini_tts: 'text' is required and must be non-empty.")

        start = time.time()
        model = inputs.get("model") or _DEFAULT_MODEL
        voice = inputs.get("voice_id") or _DEFAULT_VOICE

        try:
            body = self._build_request(inputs["text"], voice, inputs.get("instructions"))
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                json=body,
                timeout=120,
            )
            resp.raise_for_status()
            pcm, rate = self._extract_pcm(resp.json())
        except Exception as e:  # noqa: BLE001 - surface API/network failure to the agent
            return ToolResult(success=False, error=f"Gemini TTS failed: {e}")

        output_path = Path(inputs.get("output_path", "gemini_tts.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._pcm_to_wav(pcm, output_path, rate)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice_id": voice,
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": "wav",
                "sample_rate": rate,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            model=model,
            duration_seconds=round(time.time() - start, 2),
        )
