"""Doubao Speech text-to-speech provider tool."""

from __future__ import annotations

import json
import os
import time
import uuid
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


class DoubaoTTS(BaseTool):
    name = "doubao_tts"
    version = "0.2.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "doubao"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set DOUBAO_SPEECH_API_KEY to a Volcengine Doubao Speech API Key.\n"
        "Optional: set DOUBAO_SPEECH_VOICE_TYPE to the default speaker voice.\n"
        "Use the new console API key flow; do not pass app id/access token as the API key."
    )
    fallback = "google_tts"
    fallback_tools = ["google_tts", "elevenlabs_tts", "openai_tts", "piper_tts"]
    agent_skills = ["doubao-tts", "text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "multilingual",
        "timestamp_alignment",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "timestamps": True,
        "long_text_async": True,
    }
    best_for = [
        "natural Mandarin narration",
        "Chinese explainer voiceovers with character-level timestamps",
        "long-form narration that needs subtitle alignment",
    ]
    not_good_for = [
        "fully offline production",
        "voice clone matching",
        "real-time interactive speech playback",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "voice_id": {
                "type": "string",
                "description": "Doubao speaker/voice_type. Defaults to DOUBAO_SPEECH_VOICE_TYPE.",
            },
            "resource_id": {
                "type": "string",
                "default": "seed-tts-2.0",
                "description": "Volcengine resource id. Use seed-tts-2.0 for Doubao Speech 2.0 voices.",
            },
            "model": {
                "type": "string",
                "description": "Optional req_params.model for compatible voices, e.g. seed-tts-2.0-expressive or seed-tts-2.0-standard.",
            },
            "format": {
                "type": "string",
                "default": "mp3",
                "enum": ["mp3", "ogg_opus", "pcm", "wav"],
            },
            "sample_rate": {
                "type": "integer",
                "default": 24000,
                "enum": [8000, 16000, 22050, 24000, 32000, 44100, 48000],
            },
            "bit_rate": {
                "type": "integer",
                "description": "Optional MP3 bit rate, when supported by the endpoint.",
            },
            "speech_rate": {
                "type": "integer",
                "default": 0,
                "minimum": -50,
                "maximum": 100,
                "description": "Doubao speech rate. 0=normal, 100=2x, -50=0.5x.",
            },
            "emotion": {
                "type": "string",
                "description": "Optional Doubao emotion value, e.g. neutral, news, storytelling. Supported values depend on voice.",
            },
            "emotion_scale": {
                "type": "number",
                "minimum": 1,
                "maximum": 5,
                "description": "Emotion intensity when emotion is set. 1 is least expressive, 5 is strongest.",
            },
            "loudness_rate": {
                "type": "integer",
                "minimum": -50,
                "maximum": 100,
                "description": "Doubao loudness rate. 0=normal, 100=2x, -50=0.5x.",
            },
            "explicit_language": {
                "type": "string",
                "description": "Optional additions.explicit_language, e.g. zh-cn, en, crosslingual. Leave unset unless needed.",
            },
            "context_texts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional context strings to guide style or dialogue context when supported.",
            },
            "silence_duration": {
                "type": "integer",
                "minimum": 0,
                "maximum": 30000,
                "description": "Optional trailing silence in milliseconds.",
            },
            "enable_language_detector": {
                "type": "boolean",
                "description": "Optional automatic language detection.",
            },
            "disable_emoji_filter": {
                "type": "boolean",
                "description": "Optional emoji filter control.",
            },
            "mute_cut_threshold": {
                "type": "integer",
                "description": "Optional mute cutting threshold; sent with mute_cut_remain_ms as string additions.",
            },
            "mute_cut_remain_ms": {
                "type": "integer",
                "description": "Optional silence length to keep after mute cutting; sent as a string addition.",
            },
            "max_length_to_filter_parenthesis": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Optional parenthesis filtering threshold.",
            },
            "unsupported_char_ratio_thresh": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Optional unsupported-character ratio threshold.",
            },
            "post_process_pitch": {
                "type": "integer",
                "minimum": -12,
                "maximum": 12,
                "description": "Optional post-process pitch shift in semitones.",
            },
            "extra_audio_params": {
                "type": "object",
                "description": "Advanced raw req_params.audio_params overrides for newly documented Doubao fields.",
            },
            "extra_additions": {
                "type": "object",
                "description": "Advanced raw req_params.additions overrides for newly documented Doubao fields.",
            },
            "enable_timestamp": {
                "type": "boolean",
                "default": True,
                "description": "Return sentence/word timing metadata when supported by the selected endpoint.",
            },
            "disable_markdown_filter": {
                "type": "boolean",
                "default": False,
                "description": "Pass through Doubao markdown filtering behavior. Defaults to API-safe false.",
            },
            "return_usage": {
                "type": "boolean",
                "default": True,
                "description": "Request usage token data from Volcengine when available.",
            },
            "output_path": {"type": "string"},
            "metadata_path": {
                "type": "string",
                "description": "Where to save the full query JSON. Defaults next to output_path.",
            },
            "poll_interval_seconds": {
                "type": "number",
                "default": 2.0,
                "minimum": 0.5,
            },
            "timeout_seconds": {
                "type": "integer",
                "default": 300,
                "minimum": 30,
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "metadata_path": {"type": "string"},
            "task_id": {"type": "string"},
            "audio_duration_seconds": {"type": ["number", "null"]},
            "sentences": {"type": "array"},
            "usage": {"type": ["object", "null"]},
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
        retryable_errors=["timeout", "rate_limit", "quota exceeded for types: concurrency"],
    )
    idempotency_key_fields = ["text", "voice_id", "resource_id", "speech_rate", "sample_rate"]
    side_effects = [
        "writes audio file to output_path",
        "writes Doubao query metadata JSON next to output_path",
        "calls Volcengine Doubao Speech API",
    ]
    user_visible_verification = [
        "Listen to generated audio for Mandarin naturalness and pacing",
        "Check timestamp JSON before building subtitles",
    ]
    quality_score = 0.88
    latency_p50_seconds = 8.0

    SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/tts/submit"
    QUERY_URL = "https://openspeech.bytedance.com/api/v3/tts/query"
    DEFAULT_RESOURCE_ID = "seed-tts-2.0"
    DEFAULT_VOICE_ENV = "DOUBAO_SPEECH_VOICE_TYPE"

    def get_status(self) -> ToolStatus:
        if os.environ.get("DOUBAO_SPEECH_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Volcengine bills Doubao Speech 2.0 by characters. Keep this conservative
        # and prefer provider-returned usage when available.
        return round(len(inputs.get("text", "")) * 0.000015, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("DOUBAO_SPEECH_API_KEY")
        if not api_key:
            return ToolResult(success=False, error="No Doubao Speech API key. " + self.install_instructions)

        voice_id = inputs.get("voice_id") or os.environ.get(self.DEFAULT_VOICE_ENV)
        if not voice_id:
            return ToolResult(
                success=False,
                error=(
                    "No Doubao voice_id provided. Pass voice_id or set "
                    f"{self.DEFAULT_VOICE_ENV} in the environment."
                ),
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key=api_key, voice_id=voice_id)
        except Exception as exc:
            return ToolResult(success=False, error=f"Doubao TTS failed: {self._safe_error(exc)}")

        result.duration_seconds = round(time.time() - start, 2)
        if not result.cost_usd:
            result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], *, api_key: str, voice_id: str) -> ToolResult:
        import requests

        text = inputs["text"]
        fmt = inputs.get("format", "mp3")
        resource_id = inputs.get("resource_id", self.DEFAULT_RESOURCE_ID)
        output_path = Path(inputs.get("output_path", f"doubao_tts.{self._extension_for_format(fmt)}"))
        metadata_path = Path(
            inputs.get("metadata_path") or output_path.with_suffix(output_path.suffix + ".json")
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        req_id = str(uuid.uuid4())
        headers = self._headers(
            api_key=api_key,
            resource_id=resource_id,
            request_id=req_id,
            return_usage=bool(inputs.get("return_usage", True)),
        )
        body = self._submit_body(inputs, voice_id=voice_id, request_id=req_id)

        submit_response = requests.post(self.SUBMIT_URL, headers=headers, json=body, timeout=(10, 60))
        submit_data = self._json_or_raise(submit_response)
        self._raise_for_doubao_error(submit_response.status_code, submit_data)

        task_id = submit_data.get("data", {}).get("task_id")
        if not task_id:
            raise RuntimeError("Doubao submit succeeded but did not return data.task_id")

        query_data = self._poll_query(
            requests_module=requests,
            api_key=api_key,
            resource_id=resource_id,
            task_id=task_id,
            return_usage=bool(inputs.get("return_usage", True)),
            poll_interval=float(inputs.get("poll_interval_seconds", 2.0)),
            timeout_seconds=int(inputs.get("timeout_seconds", 300)),
        )
        data = query_data.get("data", {})
        audio_url = data.get("audio_url")
        if not audio_url:
            raise RuntimeError("Doubao task completed but did not return data.audio_url")

        audio_response = requests.get(audio_url, timeout=(10, 120))
        audio_response.raise_for_status()
        output_path.write_bytes(audio_response.content)
        metadata_path.write_text(json.dumps(query_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        audio_duration = self._audio_duration(output_path)
        usage = data.get("usage")
        cost = self._cost_from_usage(usage) or self.estimate_cost(inputs)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": resource_id,
                "resource_id": resource_id,
                "request_model": inputs.get("model"),
                "voice_id": voice_id,
                "format": fmt,
                "sample_rate": inputs.get("sample_rate", 24000),
                "bit_rate": inputs.get("bit_rate"),
                "speech_rate": inputs.get("speech_rate", 0),
                "emotion": inputs.get("emotion"),
                "emotion_scale": inputs.get("emotion_scale"),
                "loudness_rate": inputs.get("loudness_rate"),
                "post_process_pitch": inputs.get("post_process_pitch"),
                "text_length": len(text),
                "task_id": task_id,
                "task_status": data.get("task_status"),
                "req_text_length": data.get("req_text_length"),
                "synthesize_text_length": data.get("synthesize_text_length"),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
                "metadata_path": str(metadata_path),
                "sentences": data.get("sentences", []),
                "usage": usage,
                "url_expire_time": data.get("url_expire_time"),
            },
            artifacts=[str(output_path), str(metadata_path)],
            cost_usd=cost,
            model=resource_id,
        )

    def _headers(
        self,
        *,
        api_key: str,
        resource_id: str,
        request_id: str,
        return_usage: bool,
    ) -> dict[str, str]:
        headers = {
            "X-Api-Key": api_key,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": request_id,
            "Content-Type": "application/json",
        }
        if return_usage:
            headers["X-Control-Require-Usage-Tokens-Return"] = "true"
        return headers

    def _submit_body(self, inputs: dict[str, Any], *, voice_id: str, request_id: str) -> dict[str, Any]:
        audio_params = {
            "format": inputs.get("format", "mp3"),
            "sample_rate": inputs.get("sample_rate", 24000),
            "speech_rate": inputs.get("speech_rate", 0),
            "enable_timestamp": bool(inputs.get("enable_timestamp", True)),
        }
        for key in ("bit_rate", "emotion", "emotion_scale", "loudness_rate"):
            if inputs.get(key) is not None:
                audio_params[key] = inputs[key]
        extra_audio_params = inputs.get("extra_audio_params")
        if isinstance(extra_audio_params, dict):
            audio_params.update({key: value for key, value in extra_audio_params.items() if value is not None})

        additions = {
            "disable_markdown_filter": bool(inputs.get("disable_markdown_filter", False)),
        }
        for key in (
            "explicit_language",
            "context_texts",
            "silence_duration",
            "enable_language_detector",
            "disable_emoji_filter",
            "max_length_to_filter_parenthesis",
            "unsupported_char_ratio_thresh",
        ):
            if inputs.get(key) is not None:
                additions[key] = inputs[key]
        if inputs.get("mute_cut_threshold") is not None:
            additions["mute_cut_threshold"] = str(inputs["mute_cut_threshold"])
        if inputs.get("mute_cut_remain_ms") is not None:
            additions["mute_cut_remain_ms"] = str(inputs["mute_cut_remain_ms"])
        if inputs.get("post_process_pitch") is not None:
            additions["post_process"] = {"pitch": inputs["post_process_pitch"]}
        extra_additions = inputs.get("extra_additions")
        if isinstance(extra_additions, dict):
            additions.update({key: value for key, value in extra_additions.items() if value is not None})

        req_params = {
            "text": inputs["text"],
            "speaker": voice_id,
            "audio_params": audio_params,
            "additions": json.dumps(additions, ensure_ascii=False),
        }
        if inputs.get("model") is not None:
            req_params["model"] = inputs["model"]
        return {
            "user": {"uid": inputs.get("user_id", "openmontage")},
            "unique_id": request_id,
            "req_params": req_params,
        }

    def _poll_query(
        self,
        *,
        requests_module: Any,
        api_key: str,
        resource_id: str,
        task_id: str,
        return_usage: bool,
        poll_interval: float,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            time.sleep(poll_interval)
            headers = self._headers(
                api_key=api_key,
                resource_id=resource_id,
                request_id=str(uuid.uuid4()),
                return_usage=return_usage,
            )
            response = requests_module.post(self.QUERY_URL, headers=headers, json={"task_id": task_id}, timeout=(10, 60))
            query_data = self._json_or_raise(response)
            self._raise_for_doubao_error(response.status_code, query_data)
            status = query_data.get("data", {}).get("task_status")
            if status == 2:
                return query_data
            if status == 3:
                raise RuntimeError(f"Doubao task failed: {query_data.get('message', 'unknown error')}")
        raise TimeoutError(f"Doubao task did not finish within {timeout_seconds} seconds")

    @staticmethod
    def _json_or_raise(response: Any) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"Non-JSON response from Doubao API: HTTP {response.status_code}") from exc

    def _raise_for_doubao_error(self, http_status: int, payload: dict[str, Any]) -> None:
        code = payload.get("code")
        if http_status < 400 and code == 20000000:
            return
        message = payload.get("message", "unknown error")
        hint = self._diagnostic_hint(message)
        raise RuntimeError(f"HTTP {http_status}, code {code}: {message}{hint}")

    @staticmethod
    def _diagnostic_hint(message: str) -> str:
        lowered = message.lower()
        if "load grant" in lowered or "requested grant not found" in lowered:
            return " (check DOUBAO_SPEECH_API_KEY and use the new-console X-Api-Key flow)"
        if "speaker permission denied" in lowered or "access denied" in lowered:
            return " (check voice_id/DOUBAO_SPEECH_VOICE_TYPE and voice authorization)"
        if "quota exceeded" in lowered:
            return " (check quota, concurrency, or remaining character package)"
        if "unsupported additions explicit language" in lowered:
            return " (do not pass additions.explicit_language for this endpoint)"
        return ""

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        # Avoid ever echoing request headers or secrets in user-visible errors.
        return str(exc).replace(os.environ.get("DOUBAO_SPEECH_API_KEY", ""), "[redacted]")

    @staticmethod
    def _extension_for_format(fmt: str) -> str:
        if fmt == "ogg_opus":
            return "ogg"
        if fmt == "pcm":
            return "pcm"
        return "mp3"

    @staticmethod
    def _audio_duration(path: Path) -> float | None:
        try:
            from tools.analysis.audio_probe import probe_duration

            return probe_duration(path)
        except Exception:
            return None

    @staticmethod
    def _cost_from_usage(usage: Any) -> float | None:
        if not isinstance(usage, dict):
            return None
        text_words = usage.get("text_words")
        if not isinstance(text_words, (int, float)):
            return None
        return round(float(text_words) * 0.000015, 4)
