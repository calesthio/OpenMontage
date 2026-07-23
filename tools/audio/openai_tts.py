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
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "openai"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
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
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "general narration fallback",
        "API-based production when ElevenLabs is unavailable",
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
                "default": "alloy",
                "description": "OpenAI voice name",
            },
            "model": {
                "type": "string",
                "default": "gpt-4o-mini-tts",
                "description": "OpenAI speech model",
            },
            "format": {
                "type": "string",
                "default": "mp3",
                "enum": ["mp3", "wav", "pcm"],
                "description": "Backward-compatible alias for response_format.",
            },
            "response_format": {
                "type": "string",
                "default": "mp3",
                "enum": ["mp3", "opus", "aac", "flac", "wav", "pcm"],
                "description": "OpenAI speech response_format.",
            },
            "instructions": {
                "type": "string",
                "description": "Optional delivery instructions. Supported by gpt-4o-mini-tts.",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.25,
                "maximum": 4.0,
                "description": "OpenAI speech speed multiplier.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice", "model", "format", "response_format", "instructions", "speed"]
    side_effects = ["writes audio file to output_path", "calls OpenAI API"]
    user_visible_verification = ["Listen to generated audio for intelligibility and tone"]

    def get_status(self) -> ToolStatus:
        if os.environ.get("OPENAI_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return round(len(inputs.get("text", "")) * 0.000015, 4)

    @staticmethod
    def _supports_instructions(model: str) -> bool:
        return model.startswith("gpt-4o-mini-tts")

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
        from openai import OpenAI

        from tools.analysis.audio_probe import probe_duration

        text = inputs["text"]
        model = inputs.get("model", "gpt-4o-mini-tts")
        voice = inputs.get("voice", "alloy")
        fmt = inputs.get("response_format") or inputs.get("format", "mp3")
        if inputs.get("instructions") and not self._supports_instructions(model):
            return ToolResult(
                success=False,
                error=(
                    "OpenAI TTS instructions are only supported by "
                    "gpt-4o-mini-tts. Use that model or omit instructions."
                ),
            )

        client = OpenAI()
        output_path = Path(inputs.get("output_path", f"openai_tts.{fmt}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        kwargs: dict[str, Any] = {
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": fmt,
        }
        if inputs.get("instructions"):
            kwargs["instructions"] = inputs["instructions"]
        if inputs.get("speed") and inputs["speed"] != 1.0:
            kwargs["speed"] = inputs["speed"]

        with client.audio.speech.with_streaming_response.create(**kwargs) as response:
            response.stream_to_file(output_path)

        audio_duration = probe_duration(output_path)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice": voice,
                "format": fmt,
                "response_format": fmt,
                "instructions": inputs.get("instructions"),
                "speed": inputs.get("speed", 1.0),
                "text_length": len(text),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            model=model,
        )
