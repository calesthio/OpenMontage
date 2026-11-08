"""Audexum text-to-speech provider tool.

Uses the documented public API (https://audexum.com/docs):
``POST /api/synthesize`` with ``Authorization: Bearer <key>``; the response
body is the raw audio.
"""

from __future__ import annotations

import math
import os
import re
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
from tools.provider_pricing import PriceQuoteRequired


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

    agent_skills = ["text-to-speech"]
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
                "default": "Atlas",
                "description": (
                    "Audexum voice. V3: Atlas, Reid, Sage, Kai, Cole, Ivy, Mira, Elle, Nova. "
                    "V2: F1-F5, M1-M5. Full list: GET https://audexum.com/api/voices"
                ),
            },
            "engine": {
                "type": "string",
                "enum": ["v1", "v2", "v3"],
                "description": (
                    "Audexum engine (API field `backend`). Defaults to v2 for F1-F5/M1-M5 "
                    "voices and v3 otherwise."
                ),
            },
            "language_code": {
                "type": "string",
                "default": "en",
                "description": "Language, e.g. en or bg. Region suffixes (en-US, pt_BR) are dropped.",
            },
            "output_path": {"type": "string"},
            "output_format": {
                "type": "string",
                "default": "mp3",
                "description": "mp3, wav, ogg or opus. Prefixed forms such as mp3_44100_128 are accepted.",
            },
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "engine": {"type": "string"},
            "format": {"type": "string"},
            "estimated_credits": {"type": "integer"},
            "cost_status": {"type": "string"},
            "audio_duration_seconds": {"type": ["number", "null"]},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["text", "voice_id", "engine", "language_code", "output_format"]
    side_effects = ["writes audio file to output_path", "calls Audexum API"]
    user_visible_verification = ["Listen to generated audio for natural speech quality"]

    DEFAULT_VOICE_ID = "Atlas"
    MAX_CHARS = 5000
    BASE_URL = "https://audexum.com"
    # Credits per character, from https://audexum.com/help/credits/how-credits-work
    CREDITS_PER_CHAR = {"v1": 1.0, "v2": 1.5, "v3": 2.0}
    _V2_VOICE = re.compile(r"^[FM][1-5]$")
    _FORMATS = ("mp3", "wav", "ogg", "opus")

    def get_status(self) -> ToolStatus:
        if os.environ.get("AUDEXUM_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def _engine(self, inputs: dict[str, Any]) -> str:
        engine = str(inputs.get("engine") or "").lower()
        if engine:
            if engine not in self.CREDITS_PER_CHAR:
                raise ValueError(f"engine must be one of {sorted(self.CREDITS_PER_CHAR)}")
            return engine
        voice = inputs.get("voice_id") or self.DEFAULT_VOICE_ID
        return "v2" if self._V2_VOICE.match(voice) else "v3"

    def _format(self, inputs: dict[str, Any]) -> str:
        requested = str(inputs.get("output_format") or "mp3").lower()
        for fmt in self._FORMATS:
            if requested.startswith(fmt):
                return fmt
        raise ValueError(f"Unsupported output_format {requested!r}; use one of {self._FORMATS}")

    def estimate_credits(self, inputs: dict[str, Any]) -> int:
        return math.ceil(len(inputs.get("text", "")) * self.CREDITS_PER_CHAR[self._engine(inputs)])

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            f"Audexum bills {self.estimate_credits(inputs)} credits for this call; credits are "
            "sold through EUR plans and credit packs (https://audexum.com/pricing) and the "
            "tool cannot see which one a key uses"
        )

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
        # Charged in credits sold through plans/packs the tool cannot see: unknown, not free.
        result.cost_usd = None
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        import requests

        text = inputs["text"]
        if not text.strip() or len(text) > self.MAX_CHARS:
            raise ValueError(f"Text must contain 1-{self.MAX_CHARS} characters")
        voice = inputs.get("voice_id") or self.DEFAULT_VOICE_ID
        engine = self._engine(inputs)
        fmt = self._format(inputs)
        lang = re.split(r"[-_]", str(inputs.get("language_code") or "en"))[0].lower() or "en"
        base_url = os.environ.get("AUDEXUM_BASE_URL", self.BASE_URL).rstrip("/")

        response = requests.post(
            f"{base_url}/api/synthesize",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"text": text, "voice": voice, "lang": lang, "format": fmt, "backend": engine},
            timeout=120,
        )
        response.raise_for_status()

        output_path = Path(inputs.get("output_path", f"tts_output.{fmt}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        duration = (getattr(response, "headers", None) or {}).get("X-Audio-Duration-S")
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "voice_id": voice,
                "engine": engine,
                "text_length": len(text),
                "output": str(output_path),
                "format": fmt,
                "estimated_credits": self.estimate_credits(inputs),
                "cost_status": "unquoted",
                "audio_duration_seconds": float(duration) if duration else None,
            },
            artifacts=[str(output_path)],
        )
