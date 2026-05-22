"""OpenAI audio-output TTS provider.

This provider uses audio-capable chat models such as gpt-audio-1.5. It is
separate from openai_tts, which targets the dedicated Speech API.
"""

from __future__ import annotations

import base64
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


class OpenAIAudioTTS(BaseTool):
    name = "openai_audio_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "openai_audio"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["python:requests"]
    install_instructions = (
        "Set the OPENAI_API_KEY environment variable:\n"
        "  export OPENAI_API_KEY=your_key_here\n"
        "This tool calls Chat Completions audio output with an audio-capable model "
        "such as gpt-audio-1.5."
    )
    fallback = "openai_tts"
    fallback_tools = ["openai_tts", "elevenlabs_tts", "piper_tts"]
    agent_skills = ["openai-docs"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "audio_output_chat_completions",
        "instruction_directed_delivery",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "timestamps": False,
        "audio_output_chat_completions": True,
    }
    best_for = [
        "testing OpenAI's newest audio-output models for expressive narration",
        "voiceover auditions that benefit from delivery instructions",
        "spoken responses where natural delivery matters more than word-level timestamps",
    ]
    not_good_for = [
        "word-level timestamp generation",
        "fully offline production",
        "voice clone matching",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Narration text to speak. In strict mode, the model is asked to read it verbatim.",
            },
            "model": {
                "type": "string",
                "default": "gpt-audio-1.5",
                "description": "OpenAI audio-capable chat model.",
            },
            "voice": {
                "type": "string",
                "default": "alloy",
                "description": "OpenAI audio voice name.",
            },
            "format": {
                "type": "string",
                "default": "wav",
                "enum": ["wav", "mp3", "flac", "opus", "pcm16"],
                "description": "Output audio format supported by Chat Completions audio output.",
            },
            "instructions": {
                "type": "string",
                "description": "Optional delivery direction, e.g. tone, pacing, emphasis, emotion, or accent.",
            },
            "strict_script": {
                "type": "boolean",
                "default": True,
                "description": "Ask the model to speak the supplied text verbatim.",
            },
            "temperature": {
                "type": "number",
                "minimum": 0,
                "maximum": 2,
                "default": 0.6,
                "description": "Sampling temperature for the audio-capable chat model.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice", "model", "format", "instructions"]
    side_effects = ["writes audio file to output_path", "calls OpenAI Chat Completions API"]
    user_visible_verification = [
        "Listen to generated audio for naturalness, exact wording, and tone",
        "If subtitles are needed, align separately because this provider does not return word timestamps",
    ]

    _EXT_MAP = {
        "wav": "wav",
        "mp3": "mp3",
        "flac": "flac",
        "opus": "opus",
        "pcm16": "pcm",
    }

    def get_status(self) -> ToolStatus:
        if os.environ.get("OPENAI_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Audio-capable chat model pricing is token based and includes audio
        # output tokens, so a character-only estimate would be misleading.
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return ToolResult(success=False, error="No OpenAI API key. " + self.install_instructions)

        start = time.time()
        try:
            result = self._generate(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"OpenAI audio TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        from tools.analysis.audio_probe import probe_duration

        text = inputs["text"]
        model = inputs.get("model", "gpt-audio-1.5")
        voice = inputs.get("voice", "alloy")
        fmt = inputs.get("format", "wav")
        ext = self._EXT_MAP.get(fmt, fmt)
        output_path = Path(inputs.get("output_path", f"openai_audio_tts.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=self._request_payload(inputs),
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]
        audio = message.get("audio") or {}
        audio_data = audio.get("data")
        if not audio_data:
            raise ValueError("OpenAI response did not include message.audio.data")

        output_path.write_bytes(base64.b64decode(audio_data))
        audio_duration = probe_duration(output_path)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice": voice,
                "format": fmt,
                "text_length": len(text),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
                "transcript": audio.get("transcript") or message.get("content"),
                "selected_provider": self.provider,
                "selected_tool": self.name,
                "timestamps": False,
            },
            artifacts=[str(output_path)],
            model=model,
        )

    def _request_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        model = inputs.get("model", "gpt-audio-1.5")
        voice = inputs.get("voice", "alloy")
        fmt = inputs.get("format", "wav")
        temperature = inputs.get("temperature", 0.6)
        messages = [
            {
                "role": "system",
                "content": self._system_prompt(inputs),
            },
            {
                "role": "user",
                "content": inputs["text"],
            },
        ]
        return {
            "model": model,
            "modalities": ["text", "audio"],
            "audio": {"voice": voice, "format": fmt},
            "messages": messages,
            "temperature": temperature,
        }

    @staticmethod
    def _system_prompt(inputs: dict[str, Any]) -> str:
        parts = [
            "You are recording narration audio for a produced video.",
        ]
        if inputs.get("strict_script", True):
            parts.append(
                "Speak the user's script verbatim. Do not add, remove, summarize, or translate words."
            )
        if inputs.get("instructions"):
            parts.append(f"Delivery direction: {inputs['instructions']}")
        return " ".join(parts)
