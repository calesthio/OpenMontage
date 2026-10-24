"""Deepgram Aura text-to-speech provider tool.

Neural TTS served by Deepgram's REST ``/v1/speak`` endpoint (Aura-2 voices).
This is an optional cloud TTS provider; when ``DEEPGRAM_API_KEY`` is configured
the agent may prefer it for natural narration, while the local ``piper_tts``
tool remains the default offline path.

Shares the same API key as the ``deepgram_stt`` transcription tool (one key
unlocks both directions). The endpoint is synchronous: a JSON body with the
text goes in, audio bytes come back — no job polling.

Notable for OpenMontage: Aura-2 ships regional Spanish voices (Argentine,
Mexican, Colombian, Peninsular, Latin American) in addition to English,
German, French, Dutch, Italian and Japanese.

Docs: https://developers.deepgram.com/reference/text-to-speech/speak-request
Voices: https://developers.deepgram.com/docs/tts-models
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

_SPEAK_URL = "https://api.deepgram.com/v1/speak"


class DeepgramTTS(BaseTool):
    name = "deepgram_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "deepgram"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    # Aura can insert non-deterministic natural pauses and breaths.
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    # Availability is decided by get_status() (env var check), mirroring the
    # azure_tts and elevenlabs_tts provider tools — dependencies stays empty.
    dependencies = []
    install_instructions = (
        "Set your Deepgram API key (same key as deepgram_stt):\n"
        "  export DEEPGRAM_API_KEY=your_deepgram_api_key\n"
        "Create one in the Deepgram console (https://console.deepgram.com) "
        "under 'API Keys'. New accounts include free credit."
    )
    fallback = "piper_tts"
    fallback_tools = ["azure_tts", "elevenlabs_tts", "piper_tts"]
    agent_skills = ["deepgram-text-to-speech", "text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "speed_control",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "natural cloud narration with regional Spanish accents (es-AR, es-MX, es-CO, es-ES, es-419)",
        "warm conversational delivery for explainers and social clips",
        "cloud TTS that shares one key with deepgram_stt",
    ]
    not_good_for = [
        "fully offline production (use piper_tts)",
        "voice cloning (use elevenlabs_tts)",
        "fine-grained SSML prosody/pitch control (use azure_tts)",
    ]

    # A small curated shortlist of Aura-2 voices. Any valid Aura model name
    # (e.g. 'aura-2-thalia-en') may be passed via `voice`.
    RECOMMENDED_VOICES = {
        "thalia": "aura-2-thalia-en",  # en-US, clear, confident female
        "apollo": "aura-2-apollo-en",  # en-US, comfortable, casual male
        "antonia": "aura-2-antonia-es",  # es-AR, approachable, natural female
        "estrella": "aura-2-estrella-es",  # es-MX, mature, calm female
        "selena": "aura-2-selena-es",  # es-419, calm, friendly female
        "aquila": "aura-2-aquila-es",  # es-419, expressive male
        "sirio": "aura-2-sirio-es",  # es-MX, calm, empathetic male
        "diana": "aura-2-diana-es",  # es-ES, storytelling female
        "nestor": "aura-2-nestor-es",  # es-ES, calm, professional male
    }
    DEFAULT_VOICE = "aura-2-thalia-en"

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "voice": {
                "type": "string",
                "description": (
                    "Aura model name (e.g. 'aura-2-antonia-es') or a shortlist alias: "
                    "thalia, apollo, antonia, estrella, selena, aquila, sirio, diana, "
                    "nestor. Default: aura-2-thalia-en."
                ),
            },
            "voice_id": {
                "type": "string",
                "description": "Alias for `voice` (selector-level control).",
            },
            "speed": {
                "type": "number",
                "minimum": 0.7,
                "maximum": 1.5,
                "description": (
                    "Speaking-rate multiplier (0.7-1.5, default 1.0). Deepgram notes "
                    "it is not yet supported in every language."
                ),
            },
            "speaking_rate": {
                "type": "number",
                "description": "Alias for `speed` (selector-level control).",
            },
            "output_path": {"type": "string"},
            "output_format": {
                "type": "string",
                "description": (
                    "'mp3' (default) or 'wav' (48kHz 16-bit PCM). Selector-style "
                    "values such as 'mp3_44100_128' are normalized by prefix."
                ),
                "default": "mp3",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "voice": {"type": "string"},
            "output": {"type": "string"},
            "format": {"type": "string"},
            "text_length": {"type": "integer"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        retryable_errors=["ConnectionError", "Timeout", "429", "503"],
    )
    idempotency_key_fields = ["text", "voice", "speed", "output_format"]
    side_effects = ["writes audio file to output_path", "sends text to Deepgram"]
    user_visible_verification = ["Listen to generated audio for natural speech quality and accent"]

    # Aura-2 pay-as-you-go: $0.030 per 1k characters (deepgram.com/pricing, Oct 2026).
    COST_PER_CHAR = 0.030 / 1_000

    def get_status(self) -> ToolStatus:
        if os.environ.get("DEEPGRAM_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return round(len(inputs.get("text", "")) * self.COST_PER_CHAR, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Well under real-time for typical narration segments.
        return 10.0

    def _resolve_voice(self, inputs: dict[str, Any]) -> str:
        voice = (inputs.get("voice") or inputs.get("voice_id") or "").strip()
        if not voice:
            return self.DEFAULT_VOICE
        return self.RECOMMENDED_VOICES.get(voice.lower(), voice)

    @staticmethod
    def _resolve_speed(inputs: dict[str, Any]) -> float | None:
        speed = inputs.get("speed", inputs.get("speaking_rate"))
        if speed is None:
            return None
        return max(0.7, min(1.5, float(speed)))

    @staticmethod
    def _resolve_container(inputs: dict[str, Any]) -> str:
        fmt = str(inputs.get("output_format", "mp3")).lower()
        return "wav" if fmt.startswith(("wav", "riff", "pcm", "linear16")) else "mp3"

    def _build_params(self, inputs: dict[str, Any]) -> dict[str, Any]:
        params: dict[str, Any] = {"model": self._resolve_voice(inputs)}
        if self._resolve_container(inputs) == "wav":
            params.update({"encoding": "linear16", "container": "wav", "sample_rate": 48000})
        else:
            params["encoding"] = "mp3"
        speed = self._resolve_speed(inputs)
        if speed is not None and speed != 1.0:
            params["speed"] = speed
        return params

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("DEEPGRAM_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="Deepgram is not configured. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._synthesize(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        if result.success:
            result.cost_usd = self.estimate_cost(inputs)
        return result

    def _synthesize(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        import requests

        params = self._build_params(inputs)
        ext = "wav" if params["encoding"] == "linear16" else "mp3"
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "OpenMontage-deepgram-tts",
        }

        try:
            response = requests.post(
                _SPEAK_URL,
                params=params,
                headers=headers,
                json={"text": inputs["text"]},
                timeout=120,
            )
        except requests.RequestException as exc:
            return ToolResult(success=False, error=f"Deepgram TTS request failed: {exc}")

        if response.status_code != 200:
            detail = response.text[:500] if response.text else ""
            return ToolResult(
                success=False,
                error=f"Deepgram TTS returned HTTP {response.status_code}: {detail}",
            )

        output_path = Path(inputs.get("output_path", f"tts_output.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice": params["model"],
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": ext,
            },
            artifacts=[str(output_path)],
            model=f"deepgram-aura:{params['model']}",
        )
