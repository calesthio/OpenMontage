"""Xiaomi MiMo V2.5 text-to-speech provider tool.

Uses the MiMo API Open Platform (OpenAI-compatible endpoint).
Supports built-in preset voices with optional natural-language style control.

API docs: https://mimo.mi.com/docs/en-US/quick-start/usage-guide/audio/speech-synthesis-v2.5
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


# Built-in voice list from MiMo docs.
BUILTIN_VOICES = {
    "mimo_default": {"name": "MiMo-默认", "language": "zh", "gender": "auto"},
    "冰糖": {"name": "冰糖", "language": "zh", "gender": "female"},
    "茉莉": {"name": "茉莉", "language": "zh", "gender": "female"},
    "苏打": {"name": "苏打", "language": "zh", "gender": "male"},
    "白桦": {"name": "白桦", "language": "zh", "gender": "male"},
    "Mia": {"name": "Mia", "language": "en", "gender": "female"},
    "Chloe": {"name": "Chloe", "language": "en", "gender": "female"},
    "Milo": {"name": "Milo", "language": "en", "gender": "male"},
    "Dean": {"name": "Dean", "language": "en", "gender": "male"},
}

DEFAULT_MODEL = "mimo-v2.5-tts"
ENDPOINT = "https://api.xiaomimimo.com/v1/chat/completions"


class MiMoTTS(BaseTool):
    name = "mimo_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "mimo"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set MIMO_API_KEY in .env (format: sk-xxxxx or tp-xxxxx).\n"
        "Get one at https://platform.xiaomimimo.com/#/console/api-keys\n"
        "API docs: https://mimo.mi.com/docs/en-US/quick-start/usage-guide/audio/speech-synthesis-v2.5"
    )
    fallback = "piper_tts"
    fallback_tools = ["dashscope_tts", "doubao_tts", "openai_tts", "piper_tts"]
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "style_control",
        "multilingual",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "high-quality Chinese TTS with style control",
        "natural language voice style instructions",
        "cost-effective TTS via Xiaomi MiMo platform",
    ]
    not_good_for = [
        "fully offline production",
        "voice clone matching",
        "providers without Xiaomi account",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to synthesize. Max ~600 chars per call.",
            },
            "voice": {
                "type": "string",
                "default": "mimo_default",
                "description": (
                    "Preset voice: mimo_default, 冰糖, 茉莉, 苏打, 白桦, "
                    "Mia, Chloe, Milo, Dean."
                ),
            },
            "model": {
                "type": "string",
                "enum": [DEFAULT_MODEL],
                "default": DEFAULT_MODEL,
                "description": "MiMo preset-voice TTS model.",
            },
            "style_instruction": {
                "type": "string",
                "description": (
                    "Optional delivery/style instruction (user role). "
                    "Examples: 'Gentle, warm bedtime-story tone' or "
                    "'Fast pace, excited sports commentator'."
                ),
            },
            "output_path": {
                "type": "string",
                "description": "Output file path. Defaults to mimo_tts_output.wav.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        retryable_errors=["timeout", "rate_limit", "server_error"],
    )
    idempotency_key_fields = ["text", "voice", "model", "style_instruction"]
    side_effects = [
        "writes audio file to output_path",
        "calls Xiaomi MiMo TTS API",
    ]
    user_visible_verification = [
        "Listen to generated audio for naturalness and style"
    ]

    def get_status(self) -> ToolStatus:
        if os.environ.get("MIMO_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Promotional free period — re-check MiMo console before large batches.
        _ = len(inputs.get("text", ""))
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not os.environ.get("MIMO_API_KEY"):
            return ToolResult(
                success=False,
                error="No MIMO_API_KEY. " + self.install_instructions,
            )

        start = time.time()
        try:
            validation_error = self._validate_inputs(inputs)
            if validation_error:
                return ToolResult(success=False, error=validation_error)
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"MiMo TTS failed: {self._safe_error(exc)}",
            )

        result.duration_seconds = round(time.time() - start, 2)
        if result.success:
            result.cost_usd = self.estimate_cost(inputs)
        return result

    def _validate_inputs(self, inputs: dict[str, Any]) -> str | None:
        model = inputs.get("model", DEFAULT_MODEL)
        if model != DEFAULT_MODEL:
            return f"Unsupported model {model!r}. Use {DEFAULT_MODEL!r}."

        voice = inputs.get("voice", "mimo_default")
        if voice not in BUILTIN_VOICES:
            return (
                f"Unknown preset voice {voice!r}. "
                f"Built-ins: {', '.join(BUILTIN_VOICES)}."
            )
        return None

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        from tools.analysis.audio_probe import probe_duration

        api_key = os.environ["MIMO_API_KEY"]
        model = inputs.get("model", DEFAULT_MODEL)
        voice = inputs.get("voice", "mimo_default")
        text = inputs["text"]
        style_instruction = (inputs.get("style_instruction") or "").strip()
        output_path = Path(inputs.get("output_path", "mimo_tts_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        messages, audio = self._build_request(text, voice, style_instruction)
        payload = {"model": model, "messages": messages, "audio": audio}

        resp = requests.post(
            ENDPOINT,
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )

        if resp.status_code != 200:
            return ToolResult(
                success=False,
                error=f"MiMo API error {resp.status_code}: {resp.text[:300]}",
            )

        try:
            data = resp.json()
        except ValueError:
            return ToolResult(
                success=False,
                error=f"Non-JSON response from MiMo API: HTTP {resp.status_code}",
            )

        choices = data.get("choices", [])
        if not choices:
            return ToolResult(success=False, error="No choices in MiMo response")

        message = choices[0].get("message", {})
        audio_data = message.get("audio") or {}
        if not isinstance(audio_data, dict) or "data" not in audio_data:
            return ToolResult(
                success=False,
                error=f"No audio data in response. Keys: {list(message.keys())}",
            )

        audio_bytes = base64.b64decode(audio_data["data"])
        if not audio_bytes:
            return ToolResult(success=False, error="Decoded audio payload is empty")

        output_path.write_bytes(audio_bytes)
        if output_path.stat().st_size == 0:
            return ToolResult(success=False, error="Audio file write failed")

        audio_duration = probe_duration(output_path)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice": voice,
                "style_instruction": style_instruction or None,
                "text_length": len(text),
                "audio_duration_seconds": (
                    round(audio_duration, 2) if audio_duration else None
                ),
                "output": str(output_path),
                "format": "wav",
                "file_size_bytes": output_path.stat().st_size,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            model=model,
        )

    @staticmethod
    def _build_request(
        text: str,
        voice: str,
        style_instruction: str,
    ) -> tuple[list[dict[str, str]], dict[str, str]]:
        messages: list[dict[str, str]] = []
        if style_instruction:
            messages.append({"role": "user", "content": style_instruction})
        messages.append({"role": "assistant", "content": text})
        audio = {"format": "wav", "voice": voice}
        return messages, audio

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        return str(exc).replace(os.environ.get("MIMO_API_KEY", ""), "[redacted]")
