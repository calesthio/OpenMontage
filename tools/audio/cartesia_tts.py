"""Cartesia Sonic — hero-tier voice (2026 Speech Arena #2, near-tie with Gemini).

A NEW hero-voice provider alongside Gemini / ElevenLabs / Kokoro — it does not replace
them. On the Artificial Analysis blind Speech Arena, Cartesia Sonic 3.5 (~1209) sits in
the top cluster (a near-tie with #1 Gemini 3.1 Flash TTS) and is the latency leader
(~82ms end-to-end). Value here: a top-naturalness voice with NO Google/OpenAI
dependency, and the fastest option if you ever add real-time.

Reports UNAVAILABLE until CARTESIA_API_KEY is set, so it never disturbs existing flows;
it auto-joins the tts menu via tts_selector.

The Cartesia API versions by date header, and the exact model id evolves (sonic-2 today,
sonic-3.5 as it GAs) — those are the `ponytail:` calibration knobs. Sonic returns a WAV
container directly, so no PCM wrapping is needed.
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

# ponytail: confirm against your Cartesia account — the API version header and the
# model id are the knobs. sonic-2 is the stable id; pass model="sonic-3.5" (the arena
# entry) once it's GA on your plan.
_API_URL = "https://api.cartesia.ai/tts/bytes"
_API_VERSION = "2025-04-16"
_DEFAULT_MODEL = "sonic-2"
_SAMPLE_RATE = 44100


class CartesiaTTS(BaseTool):
    name = "cartesia_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "cartesia"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically via CARTESIA_API_KEY
    install_instructions = (
        "Set CARTESIA_API_KEY to your Cartesia API key:\n"
        "  export CARTESIA_API_KEY=your_key   # https://play.cartesia.ai/keys\n"
        "Pick a voice id from your Cartesia voice library and pass it as voice_id."
    )
    agent_skills = ["text-to-speech"]

    capabilities = ["text_to_speech", "low_latency_speech"]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "hero-tier natural narration without a Google/OpenAI dependency",
        "lowest-latency speech (Sonic SSM, ~82ms) if real-time is ever needed",
    ]
    not_good_for = [
        "bulk/draft narration (use Kokoro — free/local)",
        "inline emotion-tag scripting (ElevenLabs v3 is stronger there)",
    ]

    input_schema = {
        "type": "object",
        "required": ["text", "voice_id"],
        "properties": {
            "text": {"type": "string"},
            "voice_id": {
                "type": "string",
                "description": "Cartesia voice id (from your voice library). Required.",
            },
            "model": {"type": "string", "default": _DEFAULT_MODEL},
            "language": {"type": "string", "default": "en"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice_id", "model", "language"]
    side_effects = ["writes audio file to output_path", "calls Cartesia API"]
    user_visible_verification = ["Listen for natural delivery and correct voice identity"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if os.environ.get("CARTESIA_API_KEY") else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Cartesia bills per character; a hero line is a fraction of a cent.
        return round(max(1, len(inputs.get("text", "") or "")) * 0.00003, 4)

    @staticmethod
    def _build_request(text: str, voice_id: str, model: str, language: str) -> dict[str, Any]:
        """Build the Cartesia /tts/bytes body (pure, testable)."""
        return {
            "model_id": model,
            "transcript": text,
            "voice": {"mode": "id", "id": voice_id},
            "language": language,
            "output_format": {
                "container": "wav",
                "encoding": "pcm_s16le",
                "sample_rate": _SAMPLE_RATE,
            },
        }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        api_key = os.environ.get("CARTESIA_API_KEY")
        if not api_key:
            return ToolResult(success=False, error="Cartesia TTS unavailable. " + self.install_instructions)
        if not (inputs.get("text") or "").strip():
            return ToolResult(success=False, error="cartesia_tts: 'text' is required and must be non-empty.")
        voice_id = inputs.get("voice_id")
        if not voice_id:
            return ToolResult(
                success=False,
                error="cartesia_tts: 'voice_id' is required — pick one from your Cartesia voice library.",
            )

        start = time.time()
        model = inputs.get("model") or _DEFAULT_MODEL
        body = self._build_request(inputs["text"], voice_id, model, inputs.get("language", "en"))

        try:
            resp = requests.post(
                _API_URL,
                headers={
                    "X-API-Key": api_key,
                    "Cartesia-Version": _API_VERSION,
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=120,
            )
            resp.raise_for_status()
            audio = resp.content
        except Exception as e:  # noqa: BLE001 - surface API/network failure to the agent
            return ToolResult(success=False, error=f"Cartesia TTS failed: {e}")

        output_path = Path(inputs.get("output_path", "cartesia_tts.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice_id": voice_id,
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": "wav",
                "sample_rate": _SAMPLE_RATE,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            model=model,
            duration_seconds=round(time.time() - start, 2),
        )
