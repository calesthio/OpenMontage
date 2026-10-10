"""ElevenLabs text-to-speech provider tool."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from tools.provider_pricing import PriceQuoteRequired

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


class ElevenLabsTTS(BaseTool):
    name = "elevenlabs_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "elevenlabs"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set the ELEVENLABS_API_KEY environment variable:\n"
        "  export ELEVENLABS_API_KEY=your_key_here\n"
        "Get a key at https://elevenlabs.io\n"
        "If fal_elevenlabs_tts is available, use it instead to access ElevenLabs "
        "speech through fal.ai without a separate ElevenLabs key."
    )
    fallback = "openai_tts"
    fallback_tools = ["openai_tts", "piper_tts"]
    agent_skills = ["elevenlabs", "text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "ssml_support",
        "pronunciation_control",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "high-quality narration",
        "voice-sensitive spokesperson videos",
        "multilingual spoken delivery",
    ]
    not_good_for = [
        "fully offline production",
        "privacy-constrained local-only workflows",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "voice_id": {
                "type": "string",
                "description": "ElevenLabs voice ID (default: Rachel)",
            },
            "model_id": {
                "type": "string",
                "default": "eleven_multilingual_v2",
                "enum": [
                    "eleven_v4",
                    "eleven_v4_turbo",
                    "eleven_v3",
                    "eleven_multilingual_v2",
                    "eleven_turbo_v2_5",
                    "eleven_flash_v2_5",
                ],
                "description": "TTS model to use",
            },
            "stability": {
                "type": "number",
                "default": 0.5,
                "minimum": 0,
                "maximum": 1,
            },
            "similarity_boost": {
                "type": "number",
                "default": 0.75,
                "minimum": 0,
                "maximum": 1,
            },
            "style": {
                "type": "number",
                "default": 0.0,
                "minimum": 0,
                "maximum": 1,
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.7,
                "maximum": 1.2,
            },
            "use_speaker_boost": {
                "type": "boolean",
                "default": True,
            },
            "seed": {"type": "integer", "minimum": 0, "maximum": 4294967295},
            "language_code": {"type": "string"},
            "previous_text": {"type": "string"},
            "next_text": {"type": "string"},
            "previous_request_ids": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 3,
            },
            "next_request_ids": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 3,
            },
            "apply_text_normalization": {
                "type": "string",
                "enum": ["auto", "on", "off"],
            },
            "output_path": {"type": "string"},
            "output_format": {
                "type": "string",
                "default": "mp3_44100_128",
                "enum": ["mp3_44100_128", "mp3_44100_192", "pcm_16000", "pcm_24000"],
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = [
        "text",
        "voice_id",
        "model_id",
        "stability",
        "similarity_boost",
        "style",
        "speed",
        "use_speaker_boost",
    ] + [
        "seed",
        "language_code",
        "previous_text",
        "next_text",
        "previous_request_ids",
        "next_request_ids",
        "output_format",
    ]
    side_effects = ["writes audio file to output_path", "calls ElevenLabs API"]
    user_visible_verification = ["Listen to generated audio for natural speech quality"]

    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

    def get_status(self) -> ToolStatus:
        if os.environ.get("ELEVENLABS_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        if inputs.get("model_id", "").startswith("eleven_v4"):
            raise PriceQuoteRequired("Quote Eleven v4 pricing for your account plan")
        return round(len(inputs.get("text", "")) * 0.0003, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="No ElevenLabs API key. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = (
            None
            if inputs.get("model_id", "").startswith("eleven_v4")
            else self.estimate_cost(inputs)
        )
        result.data["cost_status"] = (
            "unquoted" if result.cost_usd is None else "estimated"
        )
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        import requests

        from jsonschema import validate

        validate(inputs, self.input_schema)
        text = inputs["text"]
        limit = (
            10000
            if inputs.get("model_id", "").startswith("eleven_v4")
            else 5000
            if inputs.get("model_id") == "eleven_v3"
            else 40000
        )
        if not text.strip() or len(text) > limit:
            raise ValueError(f"Text must contain 1–{limit} characters for this model")
        voice_id = inputs.get("voice_id", self.DEFAULT_VOICE_ID)
        model_id = inputs.get("model_id", "eleven_multilingual_v2")
        output_format = inputs.get("output_format", "mp3_44100_128")
        voice_settings = {
            "stability": inputs.get("stability", 0.5),
            "similarity_boost": inputs.get("similarity_boost", 0.75),
            "style": inputs.get("style", 0.0),
            "speed": inputs.get("speed", 1.0),
            "use_speaker_boost": inputs.get("use_speaker_boost", True),
        }

        payload = {"text": text, "model_id": model_id, "voice_settings": voice_settings}
        for field in (
            "seed",
            "language_code",
            "previous_text",
            "next_text",
            "previous_request_ids",
            "next_request_ids",
            "apply_text_normalization",
        ):
            if field in inputs:
                payload[field] = inputs[field]
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json=payload,
            params={"output_format": output_format},
            timeout=120,
        )
        response.raise_for_status()

        ext = "mp3" if "mp3" in output_format else "wav"
        output_path = Path(inputs.get("output_path", f"tts_output.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_format.startswith("pcm_"):
            import wave

            with wave.open(str(output_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(int(output_format.split("_")[1]))
                wav.writeframes(response.content)
        else:
            output_path.write_bytes(response.content)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model_id,
                "voice_id": voice_id,
                "voice_settings": voice_settings,
                "text_length": len(text),
                "output": str(output_path),
                "format": output_format,
                "request_id": response.headers.get("request-id"),
            },
            artifacts=[str(output_path)],
            model=model_id,
        )
