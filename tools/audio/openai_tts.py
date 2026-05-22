"""OpenAI text-to-speech provider tool."""

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


class OpenAITTS(BaseTool):
    name = "openai_tts"
    version = "0.2.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "openai"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["python:requests"]
    install_instructions = (
        "Set the OPENAI_API_KEY environment variable:\n"
        "  export OPENAI_API_KEY=your_key_here\n"
        "Get a key at https://platform.openai.com/"
    )
    fallback = "piper_tts"
    fallback_tools = ["piper_tts"]
    agent_skills = ["openai-docs"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "instruction_directed_delivery",
        "custom_voice_id",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "timestamps": False,
        "custom_voice_id": True,
    }
    best_for = [
        "dedicated OpenAI Speech API narration",
        "fast voiceover generation with 13 built-in voices",
        "instruction-directed delivery with gpt-4o-mini-tts",
    ]
    not_good_for = [
        "voice clone matching",
        "fully offline production",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "voice": {
                "type": "string",
                "default": "marin",
                "description": "OpenAI built-in voice name. For best quality, try marin or cedar.",
                "enum": [
                    "alloy",
                    "ash",
                    "ballad",
                    "coral",
                    "echo",
                    "fable",
                    "nova",
                    "onyx",
                    "sage",
                    "shimmer",
                    "verse",
                    "marin",
                    "cedar",
                ],
            },
            "voice_id": {
                "type": "string",
                "description": "Optional custom OpenAI voice ID. When provided, it is sent as {'id': voice_id}.",
            },
            "model": {
                "type": "string",
                "default": "gpt-4o-mini-tts",
                "description": "OpenAI speech model",
                "enum": ["gpt-4o-mini-tts", "gpt-4o-mini-tts-2025-12-15", "tts-1", "tts-1-hd"],
            },
            "format": {
                "type": "string",
                "default": "mp3",
                "enum": ["mp3", "opus", "aac", "flac", "wav", "pcm"],
                "description": "Speech API response format.",
            },
            "instructions": {
                "type": "string",
                "maxLength": 4096,
                "description": "Optional delivery instructions. Supported by gpt-4o-mini-tts, not by tts-1 or tts-1-hd.",
            },
            "speed": {
                "type": "number",
                "minimum": 0.25,
                "maximum": 4.0,
                "default": 1.0,
                "description": "Speech speed. 1.0 is default.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice", "voice_id", "model", "format", "instructions", "speed"]
    side_effects = ["writes audio file to output_path", "calls OpenAI API"]
    user_visible_verification = [
        "Listen to generated audio for intelligibility and tone",
        "If subtitles are needed, align separately because this provider does not return word timestamps",
    ]

    def get_status(self) -> ToolStatus:
        if os.environ.get("OPENAI_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return round(len(inputs.get("text", "")) * 0.000015, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not os.environ.get("OPENAI_API_KEY"):
            return ToolResult(success=False, error="No OpenAI API key. " + self.install_instructions)

        start = time.time()
        try:
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"OpenAI TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        from tools.analysis.audio_probe import probe_duration

        text = inputs["text"]
        model = inputs.get("model", "gpt-4o-mini-tts")
        voice = self._voice_payload(inputs)
        fmt = inputs.get("format", "mp3")
        output_path = Path(inputs.get("output_path", f"openai_tts.{fmt}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        kwargs: dict[str, Any] = {
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": fmt,
        }
        if inputs.get("instructions") and self._supports_instructions(model):
            kwargs["instructions"] = inputs["instructions"]
        if inputs.get("speed") and inputs["speed"] != 1.0:
            kwargs["speed"] = inputs["speed"]

        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                "Content-Type": "application/json",
            },
            json=kwargs,
            timeout=180,
        )
        response.raise_for_status()
        output_path.write_bytes(response.content)

        audio_duration = probe_duration(output_path)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice": self._voice_label(voice),
                "format": fmt,
                "text_length": len(text),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
                "instructions_applied": bool(inputs.get("instructions") and self._supports_instructions(model)),
                "timestamps": False,
            },
            artifacts=[str(output_path)],
            model=model,
        )

    @staticmethod
    def _supports_instructions(model: str) -> bool:
        return model.startswith("gpt-4o-mini-tts")

    @staticmethod
    def _voice_payload(inputs: dict[str, Any]) -> str | dict[str, str]:
        voice_id = inputs.get("voice_id")
        if voice_id:
            return {"id": voice_id}
        return inputs.get("voice", "marin")

    @staticmethod
    def _voice_label(voice: str | dict[str, str]) -> str:
        if isinstance(voice, dict):
            return voice.get("id", "")
        return voice
