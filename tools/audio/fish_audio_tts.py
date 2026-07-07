"""fish.audio text-to-speech provider tool.

fish.audio offers high-quality S1/S2-generation models and reference_id voice
cloning (reusing voice models created in the fish.audio playground). Strong
for expressive, multilingual narration with inline emotion tags on S2 models.
Billed per UTF-8 byte of input text.
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


class FishAudioTTS(BaseTool):
    name = "fish_audio_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "fish_audio"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set FISH_AUDIO_API_KEY to an API key from https://fish.audio/go-api/api-keys/\n"
        "Create voice models in the fish.audio playground and pass their id as\n"
        "reference_id to reuse a cloned voice."
    )
    fallback = "elevenlabs_tts"
    fallback_tools = ["elevenlabs_tts", "google_tts", "openai_tts", "piper_tts"]
    agent_skills = ["fish-audio-tts", "text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "voice_cloning",
        "multilingual",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "ssml": False,
    }
    best_for = [
        "high-quality voice-clone narration via reference_id",
        "expressive S2-model read-throughs with inline emotion tags",
        "multilingual narration",
    ]
    not_good_for = [
        "fully offline production",
        "SSML markup control",
        "deterministic reproducible output",
    ]

    _VALID_MODELS = ("s1", "s2-pro", "s2.1-pro", "s2.1-pro-free")

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "model": {
                "type": "string",
                "enum": list(_VALID_MODELS),
                "description": (
                    "Backend TTS model (sent as the 'model' HTTP header). Required — no "
                    "default. s2.1-pro = latest flagship (emotion tags, 80+ languages), "
                    "s2.1-pro-free = free tier for drafts, s2-pro = first S2 generation, "
                    "s1 = previous flagship kept for compatibility."
                ),
            },
            "reference_id": {
                "type": "string",
                "description": "fish.audio voice model id (from the playground) to clone/reuse.",
            },
            "voice_id": {
                "type": "string",
                "description": "Alias for reference_id (selector compatibility). Used only when reference_id is absent.",
            },
            "format": {
                "type": "string",
                "default": "mp3",
                "enum": ["mp3", "wav", "pcm", "opus"],
                "description": "Audio output format.",
            },
            "mp3_bitrate": {
                "type": "integer",
                "default": 128,
                "enum": [64, 128, 192],
                "description": "MP3 bitrate (kbps). Only applies when format=mp3.",
            },
            "chunk_length": {
                "type": "integer",
                "default": 300,
                "minimum": 100,
                "maximum": 300,
                "description": "Text chunk length for streaming synthesis.",
            },
            "normalize": {
                "type": "boolean",
                "default": True,
                "description": "Normalize numbers/dates for stable pronunciation.",
            },
            "latency": {
                "type": "string",
                "default": "normal",
                "enum": ["low", "balanced", "normal"],
                "description": (
                    "Latency mode. 'normal' = best quality, 'balanced' trades a little "
                    "quality for speed, 'low' = fastest."
                ),
            },
            "temperature": {
                "type": "number",
                "default": 0.7,
                "description": "Sampling temperature. Higher = more expressive, less stable.",
            },
            "top_p": {
                "type": "number",
                "default": 0.7,
                "description": "Nucleus sampling threshold.",
            },
            "repetition_penalty": {
                "type": "number",
                "default": 1.2,
                "description": "Penalty against repeated phrasing.",
            },
            "sample_rate": {
                "type": "integer",
                "description": "Output sample rate in Hz (optional; API default when omitted).",
            },
            "prosody": {
                "type": "object",
                "description": "Optional prosody controls, e.g. {\"speed\": 1.0, \"volume\": 0}.",
            },
            "output_path": {"type": "string"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "provider": {"type": "string"},
            "model": {"type": "string"},
            "reference_id": {"type": ["string", "null"]},
            "format": {"type": "string"},
            "text_length": {"type": "integer"},
        },
    }
    artifact_schema = {
        "type": "array",
        "items": {"type": "string"},
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, backoff_seconds=2.0, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["text", "model", "reference_id", "format"]
    side_effects = [
        "writes audio file to output_path",
        "calls the fish.audio TTS API",
    ]
    user_visible_verification = [
        "Listen to generated audio for natural speech quality and voice-clone fidelity",
    ]
    quality_score = 0.9
    latency_p50_seconds = 6.0

    API_URL = "https://api.fish.audio/v1/tts"

    # Approximate fish.audio pricing per UTF-8 byte of input text. fish bills by
    # bytes, not characters — matters for CJK/emoji where one char is 3-4 bytes.
    # Kept here (not pricing.yaml, which is fal-only) to mirror google_tts /
    # doubao_tts. Verify against https://fish.audio pricing when refreshing.
    _FALLBACK_RATES = {
        "s1": 0.000015,            # ~$15 / 1M bytes
        "s2-pro": 0.000015,        # ~$15 / 1M bytes
        "s2.1-pro": 0.000015,      # ~$15 / 1M bytes
        "s2.1-pro-free": 0.0,      # free tier
    }
    _DEFAULT_RATE = 0.000015

    _EXT_MAP = {"mp3": "mp3", "wav": "wav", "pcm": "pcm", "opus": "opus"}

    def _get_api_key(self) -> str | None:
        return os.environ.get("FISH_AUDIO_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        byte_count = len(str(inputs.get("text", "")).encode("utf-8"))
        model = inputs.get("model", "")
        rate = self._FALLBACK_RATES.get(model, self._DEFAULT_RATE)
        return round(byte_count * rate, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="No fish.audio API key. " + self.install_instructions,
            )

        model = inputs.get("model")
        if not model:
            return ToolResult(
                success=False,
                error=(
                    "fish_audio_tts requires an explicit 'model'. "
                    f"Valid values: {', '.join(self._VALID_MODELS)}."
                ),
            )
        if model not in self._VALID_MODELS:
            return ToolResult(
                success=False,
                error=(
                    f"Unknown fish.audio model '{model}'. "
                    f"Valid values: {', '.join(self._VALID_MODELS)}."
                ),
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key=api_key, model=model)
        except Exception as exc:
            return ToolResult(
                success=False, error=f"fish.audio TTS failed: {self._safe_error(exc, api_key)}"
            )

        result.duration_seconds = round(time.time() - start, 2)
        if not result.cost_usd:
            result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], *, api_key: str, model: str) -> ToolResult:
        import requests

        text = inputs["text"]
        fmt = inputs.get("format", "mp3")
        reference_id = inputs.get("reference_id") or inputs.get("voice_id")

        body: dict[str, Any] = {
            "text": text,
            "format": fmt,
            "normalize": bool(inputs.get("normalize", True)),
            "latency": inputs.get("latency", "normal"),
            "chunk_length": int(inputs.get("chunk_length", 300)),
        }
        if fmt == "mp3":
            body["mp3_bitrate"] = int(inputs.get("mp3_bitrate", 128))
        if reference_id:
            body["reference_id"] = reference_id
        if inputs.get("temperature") is not None:
            body["temperature"] = float(inputs["temperature"])
        if inputs.get("top_p") is not None:
            body["top_p"] = float(inputs["top_p"])
        if inputs.get("repetition_penalty") is not None:
            body["repetition_penalty"] = float(inputs["repetition_penalty"])
        if inputs.get("sample_rate") is not None:
            body["sample_rate"] = int(inputs["sample_rate"])
        if isinstance(inputs.get("prosody"), dict):
            body["prosody"] = inputs["prosody"]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "model": model,
        }

        response = requests.post(self.API_URL, headers=headers, json=body, timeout=120)
        response.raise_for_status()
        audio_content = response.content

        ext = self._EXT_MAP.get(fmt, "mp3")
        output_path = Path(inputs.get("output_path", f"fish_audio_tts.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_content)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "reference_id": reference_id,
                "format": fmt,
                "text_length": len(text),
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            model=f"fish-audio/{model}",
        )

    @staticmethod
    def _safe_error(exc: Exception, api_key: str | None) -> str:
        message = str(exc)
        if api_key:
            message = message.replace(api_key, "***")
        return message
