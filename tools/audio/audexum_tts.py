"""Audexum text-to-speech provider tool (ElevenLabs-compatible endpoint)."""

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


class AudexumTTS(BaseTool):
    name = "audexum_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "audexum"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set the AUDEXUM_API_KEY environment variable:\n"
        "  export AUDEXUM_API_KEY=sk_live_your_key_here\n"
        "Create a key at https://audexum.com (the free tier needs no card)."
    )
    fallback = "openai_tts"
    fallback_tools = ["openai_tts", "piper_tts"]

    capabilities = ["text_to_speech", "voice_selection"]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "low-cost narration at volume",
        "multilingual narration",
    ]
    not_good_for = [
        "voice clone matching",
        "fully offline production",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech (max 5000 characters)"},
            "voice_id": {
                "type": "string",
                "default": "Nova",
                "description": (
                    "Audexum voice: Nova, Atlas, Reid, Sage, Kai, Cole, Ivy, Mira, Elle "
                    "(V3) or M1-M5 / F1-F5 (V1). Full list: GET https://audexum.com/v1/voices"
                ),
            },
            "language_code": {"type": "string", "default": "en"},
            "output_path": {"type": "string"},
            "output_format": {
                "type": "string",
                "default": "mp3_44100_128",
                "enum": ["mp3_44100_128", "wav"],
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["text", "voice_id", "language_code", "output_format"]
    side_effects = ["writes audio file to output_path", "calls Audexum API"]
    user_visible_verification = ["Listen to generated audio for natural speech quality"]

    DEFAULT_VOICE_ID = "Nova"
    MAX_CHARS = 5000
    BASE_URL = "https://audexum.com"

    def get_status(self) -> ToolStatus:
        if os.environ.get("AUDEXUM_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("AUDEXUM_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="No Audexum API key. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        import requests

        text = inputs["text"]
        if not text.strip() or len(text) > self.MAX_CHARS:
            raise ValueError(f"Text must contain 1-{self.MAX_CHARS} characters")
        voice_id = inputs.get("voice_id", self.DEFAULT_VOICE_ID)
        output_format = inputs.get("output_format", "mp3_44100_128")
        base_url = os.environ.get("AUDEXUM_BASE_URL", self.BASE_URL).rstrip("/")

        response = requests.post(
            f"{base_url}/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={"text": text, "language_code": inputs.get("language_code", "en")},
            params={"output_format": output_format},
            timeout=120,
        )
        response.raise_for_status()

        ext = "wav" if output_format.startswith("wav") else "mp3"
        output_path = Path(inputs.get("output_path", f"tts_output.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice_id": voice_id,
                "text_length": len(text),
                "output": str(output_path),
                "format": output_format,
            },
            artifacts=[str(output_path)],
        )
