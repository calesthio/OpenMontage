"""MiniMax Speech text-to-speech provider tool."""

from __future__ import annotations

import json
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


class MiniMaxTTS(BaseTool):
    name = "minimax_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "minimax"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set MINIMAX_API_KEY to a MiniMax platform API key.\n"
        "Optional: set MINIMAX_TTS_VOICE_ID for the default voice and "
        "MINIMAX_TTS_MODEL for the default speech model."
    )
    fallback = "doubao_tts"
    fallback_tools = ["doubao_tts", "google_tts", "elevenlabs_tts", "openai_tts", "piper_tts"]
    agent_skills = ["minimax-tts", "text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "multilingual",
        "voice_cloning",
        "timestamp_alignment",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "timestamps": True,
        "streaming": False,
        "long_text_async": False,
    }
    best_for = [
        "expressive multilingual narration",
        "short and medium voiceover segments with subtitle metadata",
        "custom or cloned MiniMax voices",
    ]
    not_good_for = [
        "fully offline production",
        "single-call long-form narration above 10000 characters",
        "real-time playback; use the MiniMax WebSocket API for that workflow",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to convert to speech. MiniMax HTTP T2A accepts up to 10000 characters.",
            },
            "voice_id": {
                "type": "string",
                "description": "MiniMax system, designed, or cloned voice ID. Defaults to MINIMAX_TTS_VOICE_ID.",
            },
            "model": {
                "type": "string",
                "default": "speech-2.8-hd",
                "enum": [
                    "speech-2.8-hd",
                    "speech-2.8-turbo",
                    "speech-2.6-hd",
                    "speech-2.6-turbo",
                    "speech-02-hd",
                    "speech-02-turbo",
                    "speech-01-hd",
                    "speech-01-turbo",
                ],
            },
            "language_boost": {
                "type": "string",
                "default": "auto",
                "description": "Language enhancement value such as auto, Chinese, English, Japanese, or Korean.",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.5,
                "maximum": 2.0,
            },
            "vol": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.1,
                "maximum": 10.0,
            },
            "pitch": {
                "type": "integer",
                "default": 0,
                "minimum": -12,
                "maximum": 12,
            },
            "format": {
                "type": "string",
                "default": "mp3",
                "enum": ["mp3", "wav", "flac"],
            },
            "sample_rate": {
                "type": "integer",
                "default": 32000,
                "enum": [8000, 16000, 22050, 24000, 32000, 44100],
            },
            "bitrate": {
                "type": "integer",
                "default": 128000,
            },
            "channel": {
                "type": "integer",
                "default": 1,
                "enum": [1, 2],
            },
            "output_format": {
                "type": "string",
                "default": "hex",
                "enum": ["hex", "url"],
                "description": "MiniMax non-streaming response format. hex embeds audio; url returns a temporary URL.",
            },
            "subtitle_enable": {
                "type": "boolean",
                "default": True,
                "description": "Request subtitle timing metadata from MiniMax when supported.",
            },
            "subtitle_type": {
                "type": "string",
                "default": "sentence",
                "enum": ["sentence", "word"],
            },
            "pronunciation_dict": {
                "type": "object",
                "description": "Optional MiniMax pronunciation dictionary payload.",
            },
            "voice_modify": {
                "type": "object",
                "description": "Optional MiniMax voice effects payload.",
            },
            "output_path": {"type": "string"},
            "metadata_path": {
                "type": "string",
                "description": "Where to save the full MiniMax response JSON. Defaults next to output_path.",
            },
            "api_base": {
                "type": "string",
                "default": "https://api.minimax.io",
                "description": "Override MiniMax API base URL.",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "metadata_path": {"type": "string"},
            "trace_id": {"type": ["string", "null"]},
            "audio_duration_seconds": {"type": ["number", "null"]},
            "extra_info": {"type": ["object", "null"]},
            "subtitle_file": {"type": ["string", "null"]},
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
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["timeout", "rate limit", "too many requests"],
    )
    idempotency_key_fields = ["text", "voice_id", "model", "speed", "format", "sample_rate"]
    side_effects = [
        "writes audio file to output_path",
        "writes MiniMax response metadata JSON next to output_path",
        "calls MiniMax Speech T2A HTTP API",
    ]
    user_visible_verification = [
        "Listen to generated audio for tone, pronunciation, and pacing",
        "Check subtitle metadata before caption alignment",
    ]
    quality_score = 0.87
    latency_p50_seconds = 6.0

    DEFAULT_API_BASE = "https://api.minimax.io"
    T2A_PATH = "/v1/t2a_v2"
    GET_VOICE_PATH = "/v1/get_voice"
    DEFAULT_MODEL = "speech-2.8-hd"
    DEFAULT_VOICE_ENV = "MINIMAX_TTS_VOICE_ID"
    DEFAULT_MODEL_ENV = "MINIMAX_TTS_MODEL"

    def get_status(self) -> ToolStatus:
        if os.environ.get("MINIMAX_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # MiniMax speech billing varies by plan/model. Use a conservative
        # character-based estimate and prefer provider usage metadata when present.
        return round(len(inputs.get("text", "")) * 0.00002, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            return ToolResult(success=False, error="No MiniMax API key. " + self.install_instructions)

        voice_id = inputs.get("voice_id") or os.environ.get(self.DEFAULT_VOICE_ENV)
        if not voice_id:
            return ToolResult(
                success=False,
                error=(
                    "No MiniMax voice_id provided. Pass voice_id or set "
                    f"{self.DEFAULT_VOICE_ENV} in the environment."
                ),
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key=api_key, voice_id=voice_id)
        except Exception as exc:
            return ToolResult(success=False, error=f"MiniMax TTS failed: {self._safe_error(exc)}")

        result.duration_seconds = round(time.time() - start, 2)
        if not result.cost_usd:
            result.cost_usd = self.estimate_cost(inputs)
        return result

    def list_voices(self, voice_type: str = "all", *, api_key: str | None = None) -> dict[str, Any]:
        """Return MiniMax voices available to the current account."""
        import requests

        key = api_key or os.environ.get("MINIMAX_API_KEY")
        if not key:
            raise RuntimeError("No MiniMax API key. " + self.install_instructions)
        if voice_type not in {"system", "voice_cloning", "voice_generation", "all"}:
            raise ValueError("voice_type must be one of: system, voice_cloning, voice_generation, all")

        response = requests.post(
            self._endpoint({}, path=self.GET_VOICE_PATH),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={"voice_type": voice_type},
            timeout=(10, 60),
        )
        payload = self._json_or_raise(response)
        self._raise_for_minimax_error(response.status_code, payload)
        return payload

    def _generate(self, inputs: dict[str, Any], *, api_key: str, voice_id: str) -> ToolResult:
        import requests

        text = inputs["text"]
        if len(text) > 10000:
            raise ValueError("MiniMax HTTP T2A text must be 10000 characters or fewer.")

        model = inputs.get("model") or os.environ.get(self.DEFAULT_MODEL_ENV) or self.DEFAULT_MODEL
        fmt = inputs.get("format", "mp3")
        output_format = inputs.get("output_format", "hex")
        output_path = Path(inputs.get("output_path", f"minimax_tts.{fmt}"))
        metadata_path = Path(
            inputs.get("metadata_path") or output_path.with_suffix(output_path.suffix + ".json")
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.post(
            self._endpoint(inputs),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=self._request_body(inputs, voice_id=voice_id, model=model, output_format=output_format),
            timeout=(10, 120),
        )
        payload = self._json_or_raise(response)
        self._raise_for_minimax_error(response.status_code, payload)

        audio_ref = (payload.get("data") or {}).get("audio")
        if not audio_ref:
            raise RuntimeError("MiniMax task completed but did not return data.audio")

        if output_format == "url":
            audio_response = requests.get(audio_ref, timeout=(10, 120))
            audio_response.raise_for_status()
            output_path.write_bytes(audio_response.content)
        else:
            output_path.write_bytes(bytes.fromhex(audio_ref))

        metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        extra_info = payload.get("extra_info") or {}
        audio_duration = self._duration_from_extra_info(extra_info) or self._audio_duration(output_path)
        cost = self._cost_from_extra_info(extra_info) or self.estimate_cost(inputs)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice_id": voice_id,
                "format": fmt,
                "sample_rate": inputs.get("sample_rate", 32000),
                "speed": inputs.get("speed", 1.0),
                "language_boost": inputs.get("language_boost", "auto"),
                "output_format": output_format,
                "text_length": len(text),
                "trace_id": payload.get("trace_id"),
                "status": (payload.get("data") or {}).get("status"),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
                "metadata_path": str(metadata_path),
                "extra_info": extra_info,
                "subtitle_file": (payload.get("data") or {}).get("subtitle_file"),
            },
            artifacts=[str(output_path), str(metadata_path)],
            cost_usd=cost,
            model=model,
        )

    def _endpoint(self, inputs: dict[str, Any], *, path: str | None = None) -> str:
        api_base = (inputs.get("api_base") or os.environ.get("MINIMAX_API_BASE") or self.DEFAULT_API_BASE).rstrip("/")
        return f"{api_base}{path or self.T2A_PATH}"

    def _request_body(
        self,
        inputs: dict[str, Any],
        *,
        voice_id: str,
        model: str,
        output_format: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "text": inputs["text"],
            "stream": False,
            "language_boost": inputs.get("language_boost", "auto"),
            "output_format": output_format,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": inputs.get("speed", 1.0),
                "vol": inputs.get("vol", 1.0),
                "pitch": inputs.get("pitch", 0),
            },
            "audio_setting": {
                "sample_rate": inputs.get("sample_rate", 32000),
                "bitrate": inputs.get("bitrate", 128000),
                "format": inputs.get("format", "mp3"),
                "channel": inputs.get("channel", 1),
            },
            "subtitle_enable": bool(inputs.get("subtitle_enable", True)),
            "subtitle_type": inputs.get("subtitle_type", "sentence"),
        }
        if inputs.get("pronunciation_dict"):
            body["pronunciation_dict"] = inputs["pronunciation_dict"]
        if inputs.get("voice_modify"):
            body["voice_modify"] = inputs["voice_modify"]
        return body

    @staticmethod
    def _json_or_raise(response: Any) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"Non-JSON response from MiniMax API: HTTP {response.status_code}") from exc

    def _raise_for_minimax_error(self, http_status: int, payload: dict[str, Any]) -> None:
        base_resp = payload.get("base_resp") or {}
        status_code = base_resp.get("status_code")
        data_status = (payload.get("data") or {}).get("status")
        if http_status < 400 and status_code in (0, "0", None) and data_status in (2, "2", None):
            return

        status_msg = base_resp.get("status_msg") or payload.get("message") or "unknown error"
        hint = self._diagnostic_hint(str(status_msg))
        raise RuntimeError(f"HTTP {http_status}, status_code {status_code}: {status_msg}{hint}")

    @staticmethod
    def _diagnostic_hint(message: str) -> str:
        lowered = message.lower()
        if "unauthorized" in lowered or "invalid api key" in lowered or "auth" in lowered:
            return " (check MINIMAX_API_KEY and Bearer authorization)"
        if "voice" in lowered and ("not found" in lowered or "invalid" in lowered or "permission" in lowered):
            return " (check voice_id/MINIMAX_TTS_VOICE_ID and voice authorization)"
        if "insufficient balance" in lowered or "balance" in lowered:
            return " (check MiniMax Account > Billing > Balance and top up before generation)"
        if "rate" in lowered or "quota" in lowered:
            return " (check rate limit, balance, or remaining speech quota)"
        if "text" in lowered and "10000" in lowered:
            return " (split text into shorter segments or use MiniMax async T2A)"
        return ""

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        api_key = os.environ.get("MINIMAX_API_KEY", "")
        message = str(exc)
        if api_key:
            message = message.replace(api_key, "[redacted]")
        return message

    @staticmethod
    def _duration_from_extra_info(extra_info: Any) -> float | None:
        if not isinstance(extra_info, dict):
            return None
        audio_length = extra_info.get("audio_length")
        if isinstance(audio_length, (int, float)) and audio_length > 0:
            # MiniMax returns audio_length in milliseconds.
            return float(audio_length) / 1000.0
        return None

    @staticmethod
    def _audio_duration(path: Path) -> float | None:
        try:
            from tools.analysis.audio_probe import probe_duration

            return probe_duration(path)
        except Exception:
            return None

    @staticmethod
    def _cost_from_extra_info(extra_info: Any) -> float | None:
        if not isinstance(extra_info, dict):
            return None
        usage_characters = extra_info.get("usage_characters")
        if not isinstance(usage_characters, (int, float)):
            return None
        return round(float(usage_characters) * 0.00002, 4)
