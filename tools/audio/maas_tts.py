"""DolphinLitePark MaaS platform TTS tool.

POST /v1/audio/speech  — OpenAI-compatible TTS endpoint.
Gateway handles all provider differences; client always sends the same shape.

Models available (2026-06-28):
  leapfast/indextts       — Self-hosted IndexTTS on H100, Chinese+English, free
  cosyvoice-v3.5-flash — DashScope CosyVoice, Chinese multi-speaker, free
  qwen3-tts-flash     — DashScope Qwen3 TTS, ¥1.60/M tokens

Voice map for leapfast/indextts (OpenAI names work too):
  alloy   → zh_female_intellectual   (知性女声)
  echo    → zh_male_broadcaster      (播音男声)
  fable   → zh_female_youthful       (青春女声)
  onyx    → zh_male_deep             (浑厚男声)
  nova    → zh_female_warm           (温暖女声)
  shimmer → zh_female_soothing       (舒缓女声)
  Or pass an IndexTTS native voice name directly.
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


class MaasTTS(BaseTool):
    name = "maas_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "maas"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MAAS_API_KEY"]
    install_instructions = (
        "Set MAAS_API_KEY to your DolphinLitePark API key (sk-dlp-...).\n"
        "Optionally set MAAS_API_BASE to override the gateway URL\n"
        "(default: https://api.aiapbot.com)."
    )
    agent_skills = ["text-to-speech"]

    capabilities = ["text_to_speech", "voice_selection", "multilingual"]
    supports = {
        "text_to_speech": True,
        "multilingual": True,
        "chinese": True,
        "english": True,
        "voice_cloning": False,
        "offline": False,
        "streaming": False,
    }
    best_for = [
        "Chinese narration — IndexTTS H100 is optimized for Mandarin",
        "internal MaaS quota — no external TTS billing",
        "fast synthesis: leapfast/indextts and cosyvoice-v3.5-flash are free-tier",
    ]
    not_good_for = [
        "voice cloning",
        "offline / air-gapped environments",
    ]
    fallback_tools = ["elevenlabs_tts", "openai_tts", "piper_tts"]

    # TTS models on MaaS (sourced 2026-06-28)
    MODELS = {
        "leapfast/indextts":        {"lang": "zh+en", "price": "free",           "format": "wav"},
        "cosyvoice-v3.5-flash": {"lang": "zh",    "price": "free",           "format": "mp3"},
        "qwen3-tts-flash":      {"lang": "zh+en", "price": "¥1.60/M tokens", "format": "mp3"},
    }
    DEFAULT_MODEL = "leapfast/indextts"

    # OpenAI voice → IndexTTS native voice index
    VOICE_MAP = {
        "alloy":   "zh_female_intellectual",
        "echo":    "zh_male_broadcaster",
        "fable":   "zh_female_youthful",
        "onyx":    "zh_male_deep",
        "nova":    "zh_female_warm",
        "shimmer": "zh_female_soothing",
    }
    DEFAULT_VOICE = "alloy"

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to synthesize"},
            "model": {
                "type": "string",
                "description": (
                    "TTS model. Options: leapfast/indextts (default, free, zh+en), "
                    "cosyvoice-v3.5-flash (free, zh), qwen3-tts-flash (¥1.60/M tok, zh+en)"
                ),
                "default": "leapfast/indextts",
            },
            "voice": {
                "type": "string",
                "description": (
                    "Voice name. OpenAI names (alloy/echo/fable/onyx/nova/shimmer) are "
                    "auto-mapped to IndexTTS voices. Or pass a native voice index directly."
                ),
                "default": "alloy",
            },
            "format": {
                "type": "string",
                "enum": ["mp3", "wav"],
                "default": "mp3",
                "description": "Output audio format (leapfast/indextts defaults to wav)",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "description": "Speech rate (1.0 = normal)",
            },
            "output_path": {"type": "string", "description": "Local path to save audio file"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=20, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "rate_limit"])
    idempotency_key_fields = ["text", "model", "voice", "format"]
    side_effects = ["writes audio file to output_path", "calls MaaS gateway API"]
    user_visible_verification = ["Listen to generated audio for clarity and tone"]

    def _api_key(self) -> str | None:
        return os.environ.get("MAAS_API_KEY")

    def _base_url(self) -> str:
        return os.environ.get("MAAS_API_BASE", "https://api.aiapbot.com").rstrip("/")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # leapfast/indextts and cosyvoice are free; qwen3-tts-flash is token-priced in CNY
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        chars = len(inputs.get("text", ""))
        return max(5.0, chars / 20)  # rough: ~20 chars/s synthesis speed

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="MAAS_API_KEY not set. " + self.install_instructions,
            )

        model = inputs.get("model", self.DEFAULT_MODEL)
        voice = inputs.get("voice", self.DEFAULT_VOICE)
        fmt = inputs.get("format", "mp3")
        text = inputs["text"]

        # leapfast/indextts native format is WAV; honour caller's preference otherwise
        if model == "leapfast/indextts" and fmt == "mp3":
            fmt = "wav"

        payload: dict[str, Any] = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": fmt,
        }
        if inputs.get("speed") and inputs["speed"] != 1.0:
            payload["speed"] = inputs["speed"]

        ext = fmt
        output_path = Path(inputs.get("output_path", f"maas_tts_{int(time.time())}.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        start = time.time()
        try:
            resp = requests.post(
                f"{self._base_url()}/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                stream=True,
                timeout=120,
            )
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            return ToolResult(success=False, error=f"MaaS TTS failed: {e}")

        # Probe duration if possible
        audio_duration = None
        try:
            from tools.analysis.audio_probe import probe_duration
            audio_duration = probe_duration(output_path)
        except Exception:
            pass

        return ToolResult(
            success=True,
            data={
                "provider": "maas",
                "model": model,
                "voice": voice,
                "format": fmt,
                "text_length": len(text),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
                "output_path": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),   # 0.0 for free MaaS TTS models
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
