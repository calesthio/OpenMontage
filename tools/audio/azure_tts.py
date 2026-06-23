"""Azure AI Speech text-to-speech provider tool."""

from __future__ import annotations

import importlib
import json
import os
import time
import xml.sax.saxutils
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

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


class AzureTTS(BaseTool):
    name = "azure_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "azure"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION for Azure AI Speech.\n"
        "Optional: set AZURE_SPEECH_ENDPOINT for a custom endpoint, or "
        "AZURE_SPEECH_AUTH_TOKEN for token-based auth.\n"
        "For word-boundary timing metadata, install the optional SDK:\n"
        "  pip install azure-cognitiveservices-speech"
    )
    fallback = "doubao_tts"
    fallback_tools = ["doubao_tts", "google_tts", "elevenlabs_tts", "openai_tts", "piper_tts"]
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "ssml_support",
        "multilingual",
        "expressive_style_control",
        "custom_voice_endpoint",
        "voice_catalog",
        "word_boundary_timestamps",
    ]
    supports = {
        "voice_cloning": False,
        "custom_voice": True,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "ssml": True,
        "style": True,
        "prosody": True,
        "word_boundary_events": True,
        "sdk_optional": True,
    }
    best_for = [
        "production Mandarin narration with enterprise-grade availability",
        "SSML-directed pacing, pitch, volume, style, and role",
        "voice catalog discovery before TTS Segment Lab auditions",
        "word-boundary timing metadata for subtitles and visual cue alignment when the optional SDK is installed",
    ]
    not_good_for = [
        "fully offline production",
        "word-level timestamps without the optional Azure Speech SDK",
        "voice cloning through this generic REST provider",
    ]

    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "default": "synthesize",
                "enum": ["synthesize", "list_voices", "preflight"],
                "description": "Use list_voices to fetch the Azure voice catalog, or preflight to inspect credentials and optional SDK availability.",
            },
            "text": {"type": "string", "description": "Text to convert to speech"},
            "backend": {
                "type": "string",
                "default": "auto",
                "enum": ["auto", "rest", "sdk"],
                "description": "auto/rest uses lightweight REST by default. sdk uses the optional Azure Speech SDK for word-boundary metadata.",
            },
            "enable_word_boundaries": {
                "type": "boolean",
                "default": False,
                "description": "Use Azure Speech SDK to capture word-boundary timing metadata for subtitles and visual cue alignment. Requires azure-cognitiveservices-speech.",
            },
            "require_word_boundaries": {
                "type": "boolean",
                "default": False,
                "description": "Fail instead of falling back to REST when word-boundary metadata was requested but the optional SDK is unavailable.",
            },
            "ssml": {
                "type": "string",
                "description": "Raw SSML. When provided, OpenMontage sends it directly and ignores text/prosody/style fields.",
            },
            "voice": {
                "type": "string",
                "default": "zh-CN-YunxiNeural",
                "description": "Azure voice name, for example zh-CN-XiaoxiaoNeural, zh-CN-YunxiNeural, en-US-JennyNeural.",
            },
            "language_code": {
                "type": "string",
                "default": "zh-CN",
                "description": "SSML xml:lang and optional voice catalog locale filter.",
            },
            "style": {
                "type": "string",
                "description": "Optional mstts:express-as style, for example chat, cheerful, customerservice, newscast, sad.",
            },
            "style_degree": {
                "type": "number",
                "minimum": 0.01,
                "maximum": 2.0,
                "description": "Optional mstts:express-as styledegree. Azure commonly supports 0.01 to 2.",
            },
            "role": {
                "type": "string",
                "description": "Optional mstts:express-as role, for example YoungAdultMale or SeniorFemale.",
            },
            "rate": {
                "type": "string",
                "description": "Optional SSML prosody rate, for example +8%, -10%, fast, medium, slow.",
            },
            "pitch": {
                "type": "string",
                "description": "Optional SSML prosody pitch, for example +2st, -5%, high, medium, low.",
            },
            "volume": {
                "type": "string",
                "description": "Optional SSML prosody volume, for example +2dB, soft, medium, loud.",
            },
            "sentence_silence_ms": {
                "type": "integer",
                "minimum": 0,
                "description": "Optional sentence boundary silence using mstts:silence, in milliseconds.",
            },
            "audio_format": {
                "type": "string",
                "default": "audio-24khz-160kbitrate-mono-mp3",
                "description": "Azure X-Microsoft-OutputFormat value. Custom values are passed through.",
            },
            "region": {
                "type": "string",
                "description": "Azure Speech region. Defaults to AZURE_SPEECH_REGION or SPEECH_REGION.",
            },
            "endpoint": {
                "type": "string",
                "description": "Optional Azure Speech endpoint override. Defaults to AZURE_SPEECH_ENDPOINT.",
            },
            "deployment_id": {
                "type": "string",
                "description": "Optional custom voice deployment id. Appended as deploymentId query parameter.",
            },
            "output_path": {"type": "string"},
            "metadata_path": {
                "type": "string",
                "description": "Where to save provider metadata. Defaults next to output_path.",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "metadata_path": {"type": "string"},
            "voice": {"type": "string"},
            "language_code": {"type": "string"},
            "format": {"type": "string"},
            "voices": {"type": "array"},
            "words": {"type": "array"},
            "boundaries": {"type": "array"},
        },
    }
    artifact_schema = {"type": "array", "items": {"type": "string"}}

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout", "429", "503"])
    idempotency_key_fields = [
        "text", "ssml", "voice", "language_code", "style", "rate", "audio_format",
        "backend", "enable_word_boundaries",
    ]
    side_effects = [
        "writes audio file to output_path",
        "writes Azure request metadata JSON next to output_path",
        "calls Azure AI Speech REST API",
        "optionally calls Azure Speech SDK when word-boundary timing is requested",
    ]
    user_visible_verification = [
        "Listen to generated audio for naturalness, pronunciation, and pacing",
        "Use operation=list_voices before choosing a production voice",
    ]
    quality_score = 0.86
    latency_p50_seconds = 3.0

    DEFAULT_REGION_ENV = "AZURE_SPEECH_REGION"
    DEFAULT_KEY_ENV = "AZURE_SPEECH_KEY"
    DEFAULT_TOKEN_ENV = "AZURE_SPEECH_AUTH_TOKEN"
    DEFAULT_VOICE = "zh-CN-YunxiNeural"
    DEFAULT_LANGUAGE = "zh-CN"
    DEFAULT_FORMAT = "audio-24khz-160kbitrate-mono-mp3"

    _EXT_MAP = {
        "mp3": "mp3",
        "riff": "wav",
        "wav": "wav",
        "raw": "pcm",
        "ogg": "ogg",
        "opus": "opus",
        "webm": "webm",
    }

    def get_status(self) -> ToolStatus:
        if (self._get_key() or self._get_auth_token()) and (self._get_region({}) or self._get_endpoint({})):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Azure Speech bills neural TTS by characters. Keep this conservative;
        # provider account billing remains the source of truth.
        text = inputs.get("text") or inputs.get("ssml") or ""
        return round(len(text) * 0.000016, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not (self._get_key() or self._get_auth_token()):
            return ToolResult(success=False, error="No Azure Speech key/token. " + self.install_instructions)
        if not (self._get_region(inputs) or self._get_endpoint(inputs)):
            return ToolResult(success=False, error="No Azure Speech region or endpoint. " + self.install_instructions)

        start = time.time()
        try:
            operation = inputs.get("operation", "synthesize")
            if operation == "list_voices":
                result = self._list_voices(inputs)
            elif operation == "preflight":
                result = self._preflight(inputs)
            elif self._should_use_sdk(inputs):
                result = self._synthesize_with_sdk(inputs)
            else:
                result = self._synthesize(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"Azure TTS failed: {self._safe_error(exc)}")

        result.duration_seconds = round(time.time() - start, 2)
        if not result.cost_usd:
            result.cost_usd = self.estimate_cost(inputs)
        return result

    def _synthesize_with_sdk(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            speechsdk = importlib.import_module("azure.cognitiveservices.speech")
        except ImportError:
            if self._can_fallback_to_rest(inputs):
                result = self._synthesize(inputs)
                self._mark_word_boundary_fallback(
                    result,
                    "Azure word-boundary timing requires the optional Speech SDK: "
                    "pip install azure-cognitiveservices-speech",
                )
                return result
            return ToolResult(
                success=False,
                error=(
                    "Azure word-boundary timing requires the optional Speech SDK: "
                    "pip install azure-cognitiveservices-speech"
                ),
            )

        text = inputs.get("text")
        ssml = inputs.get("ssml")
        if not text and not ssml:
            return ToolResult(success=False, error="Azure TTS SDK synthesize requires text or ssml.")

        audio_format = inputs.get("audio_format", self.DEFAULT_FORMAT)
        output_path = Path(inputs.get("output_path", f"azure_tts.{self._extension_for_format(audio_format)}"))
        metadata_path = Path(inputs.get("metadata_path") or output_path.with_suffix(output_path.suffix + ".json"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        speech_config = self._sdk_speech_config(speechsdk, inputs)
        speech_config.speech_synthesis_voice_name = inputs.get("voice", self.DEFAULT_VOICE)
        speech_config.set_speech_synthesis_output_format(self._sdk_output_format(speechsdk, audio_format))

        audio_config = speechsdk.audio.AudioOutputConfig(filename=str(output_path))
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )

        boundaries: list[dict[str, Any]] = []

        def on_word_boundary(evt: Any) -> None:
            boundaries.append(self._word_boundary_payload(evt))

        synthesizer.synthesis_word_boundary.connect(on_word_boundary)

        ssml_body = ssml or self._build_ssml(inputs)
        result = synthesizer.speak_ssml_async(ssml_body).get()
        reason = getattr(result, "reason", None)
        if reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            details = getattr(result, "cancellation_details", None) or speechsdk.CancellationDetails(result)
            return ToolResult(success=False, error=f"Azure Speech SDK synthesis failed: {details}")

        words = [item for item in boundaries if item.get("boundary_type") == "Word"]
        metadata = {
            "provider": self.provider,
            "operation": "synthesize",
            "backend": "sdk",
            "voice": inputs.get("voice", self.DEFAULT_VOICE),
            "language_code": inputs.get("language_code", self.DEFAULT_LANGUAGE),
            "format": audio_format,
            "output": str(output_path),
            "ssml_generated": not bool(ssml),
            "region": self._get_region(inputs),
            "endpoint": self._safe_endpoint(inputs),
            "deployment_id": inputs.get("deployment_id"),
            "text_length": len(text or ssml_body),
            "word_boundary_count": len(words),
            "boundaries": boundaries,
            "words": words,
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={**metadata, "metadata_path": str(metadata_path)},
            artifacts=[str(output_path), str(metadata_path)],
            model=f"azure-tts-sdk/{inputs.get('voice', self.DEFAULT_VOICE)}",
        )

    def _synthesize(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        text = inputs.get("text")
        ssml = inputs.get("ssml")
        if not text and not ssml:
            return ToolResult(success=False, error="Azure TTS synthesize requires text or ssml.")

        audio_format = inputs.get("audio_format", self.DEFAULT_FORMAT)
        output_path = Path(inputs.get("output_path", f"azure_tts.{self._extension_for_format(audio_format)}"))
        metadata_path = Path(inputs.get("metadata_path") or output_path.with_suffix(output_path.suffix + ".json"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        ssml_body = ssml or self._build_ssml(inputs)
        response = requests.post(
            self._synthesize_url(inputs),
            headers=self._synthesize_headers(audio_format),
            data=ssml_body.encode("utf-8"),
            timeout=(10, 120),
        )
        response.raise_for_status()
        output_path.write_bytes(response.content)

        metadata = {
            "provider": self.provider,
            "operation": "synthesize",
            "backend": "rest",
            "voice": inputs.get("voice", self.DEFAULT_VOICE),
            "language_code": inputs.get("language_code", self.DEFAULT_LANGUAGE),
            "format": audio_format,
            "output": str(output_path),
            "ssml_generated": not bool(ssml),
            "region": self._get_region(inputs),
            "endpoint": self._safe_endpoint(inputs),
            "deployment_id": inputs.get("deployment_id"),
            "text_length": len(text or ssml_body),
            "request_id": response.headers.get("X-RequestId") or response.headers.get("x-requestid"),
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={**metadata, "metadata_path": str(metadata_path)},
            artifacts=[str(output_path), str(metadata_path)],
            model=f"azure-tts/{inputs.get('voice', self.DEFAULT_VOICE)}",
        )

    def _list_voices(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        response = requests.get(
            self._voices_url(inputs),
            headers=self._auth_headers(),
            timeout=(10, 60),
        )
        response.raise_for_status()
        voices = response.json()
        locale = inputs.get("language_code")
        if locale:
            voices = [voice for voice in voices if voice.get("Locale") == locale]
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "operation": "list_voices",
                "backend": "rest",
                "language_code": locale,
                "voices": voices,
                "voice_count": len(voices),
            },
            model="azure-tts/voices-list",
        )

    def _preflight(self, inputs: dict[str, Any]) -> ToolResult:
        region = self._get_region(inputs)
        endpoint = self._get_endpoint(inputs)
        has_key = bool(self._get_key())
        has_token = bool(self._get_auth_token())
        sdk_available = self._sdk_available()
        wants_word_boundaries = bool(inputs.get("enable_word_boundaries"))
        can_synthesize = bool((has_key or has_token) and (region or endpoint))
        warnings = []
        if wants_word_boundaries and not sdk_available:
            if self._can_fallback_to_rest(inputs):
                warnings.append(
                    "Azure Speech SDK is unavailable; synthesis can fall back to REST without word-boundary metadata."
                )
            else:
                warnings.append(
                    "Azure Speech SDK is unavailable and word-boundary metadata is required."
                )
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "operation": "preflight",
                "status": "available" if can_synthesize else "unavailable",
                "has_key": has_key,
                "has_auth_token": has_token,
                "region": region,
                "endpoint": self._safe_endpoint(inputs),
                "sdk_available": sdk_available,
                "word_boundaries_requested": wants_word_boundaries,
                "rest_fallback_available": self._can_fallback_to_rest(inputs),
                "warnings": warnings,
            },
            model="azure-tts/preflight",
        )

    @staticmethod
    def _should_use_sdk(inputs: dict[str, Any]) -> bool:
        return inputs.get("backend") == "sdk" or bool(inputs.get("enable_word_boundaries"))

    @staticmethod
    def _can_fallback_to_rest(inputs: dict[str, Any]) -> bool:
        return inputs.get("backend") != "sdk" and not bool(inputs.get("require_word_boundaries"))

    @staticmethod
    def _sdk_available() -> bool:
        try:
            return importlib.util.find_spec("azure.cognitiveservices.speech") is not None
        except (ImportError, ValueError):
            return False

    @staticmethod
    def _mark_word_boundary_fallback(result: ToolResult, reason: str) -> None:
        if result.data is None:
            result.data = {}
        warnings = list(result.data.get("warnings") or [])
        warnings.append(reason)
        result.data["warnings"] = warnings
        result.data["word_boundaries_requested"] = True
        result.data["word_boundary_fallback"] = "rest_without_word_boundaries"
        result.data["boundaries"] = []
        result.data["words"] = []

    def _sdk_speech_config(self, speechsdk: Any, inputs: dict[str, Any]) -> Any:
        endpoint = self._get_endpoint(inputs)
        key = self._get_key()
        token = self._get_auth_token()
        region = self._get_region(inputs)

        if endpoint:
            speech_config = speechsdk.SpeechConfig(endpoint=endpoint, subscription=key)
        else:
            speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        if token:
            speech_config.authorization_token = token
        return speech_config

    @staticmethod
    def _sdk_output_format(speechsdk: Any, audio_format: str) -> Any:
        normalized = audio_format.replace("-", "_").replace(".", "_")
        candidates = {
            "audio_16khz_32kbitrate_mono_mp3": "Audio16Khz32KBitRateMonoMp3",
            "audio_16khz_64kbitrate_mono_mp3": "Audio16Khz64KBitRateMonoMp3",
            "audio_16khz_128kbitrate_mono_mp3": "Audio16Khz128KBitRateMonoMp3",
            "audio_24khz_48kbitrate_mono_mp3": "Audio24Khz48KBitRateMonoMp3",
            "audio_24khz_96kbitrate_mono_mp3": "Audio24Khz96KBitRateMonoMp3",
            "audio_24khz_160kbitrate_mono_mp3": "Audio24Khz160KBitRateMonoMp3",
            "riff_16khz_16bit_mono_pcm": "Riff16Khz16BitMonoPcm",
            "riff_24khz_16bit_mono_pcm": "Riff24Khz16BitMonoPcm",
            "riff_48khz_16bit_mono_pcm": "Riff48Khz16BitMonoPcm",
            "ogg_24khz_16bit_mono_opus": "Ogg24Khz16BitMonoOpus",
            "webm_24khz_16bit_mono_opus": "Webm24Khz16BitMonoOpus",
        }
        enum_name = candidates.get(normalized.lower(), "Audio24Khz160KBitRateMonoMp3")
        return getattr(speechsdk.SpeechSynthesisOutputFormat, enum_name)

    @staticmethod
    def _word_boundary_payload(evt: Any) -> dict[str, Any]:
        boundary_type = getattr(evt, "boundary_type", "")
        if hasattr(boundary_type, "name"):
            boundary_type = boundary_type.name
        audio_offset_ticks = AzureTTS._ticks(getattr(evt, "audio_offset", 0))
        duration_ticks = AzureTTS._ticks(getattr(evt, "duration", 0))
        return {
            "boundary_type": str(boundary_type),
            "text": getattr(evt, "text", ""),
            "audio_offset_ticks": audio_offset_ticks,
            "audio_offset_seconds": audio_offset_ticks / 10_000_000,
            "duration_ticks": duration_ticks,
            "duration_seconds": duration_ticks / 10_000_000,
            "text_offset": getattr(evt, "text_offset", None),
            "word_length": getattr(evt, "word_length", None),
        }

    @staticmethod
    def _ticks(value: Any) -> int:
        if hasattr(value, "total_seconds"):
            return int(value.total_seconds() * 10_000_000)
        return int(value or 0)

    def _build_ssml(self, inputs: dict[str, Any]) -> str:
        text = xml.sax.saxutils.escape(inputs["text"])
        language = xml.sax.saxutils.escape(inputs.get("language_code", self.DEFAULT_LANGUAGE))
        voice = xml.sax.saxutils.escape(inputs.get("voice", self.DEFAULT_VOICE))
        content = text

        silence = self._silence_tag(inputs)
        if self._has_prosody(inputs):
            attrs = self._attrs({
                "rate": inputs.get("rate"),
                "pitch": inputs.get("pitch"),
                "volume": inputs.get("volume"),
            })
            content = f"<prosody{attrs}>{content}</prosody>"

        if self._has_express_as(inputs):
            attrs = self._attrs({
                "style": inputs.get("style"),
                "styledegree": inputs.get("style_degree"),
                "role": inputs.get("role"),
            })
            content = f"<mstts:express-as{attrs}>{content}</mstts:express-as>"

        return (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{language}">'
            f'<voice name="{voice}">{silence}{content}</voice>'
            f"</speak>"
        )

    @staticmethod
    def _attrs(values: dict[str, Any]) -> str:
        attrs = []
        for key, value in values.items():
            if value is None or value == "":
                continue
            escaped = xml.sax.saxutils.escape(str(value), {'"': "&quot;"})
            attrs.append(f'{key}="{escaped}"')
        return (" " + " ".join(attrs)) if attrs else ""

    @staticmethod
    def _has_prosody(inputs: dict[str, Any]) -> bool:
        return any(inputs.get(key) for key in ("rate", "pitch", "volume"))

    @staticmethod
    def _has_express_as(inputs: dict[str, Any]) -> bool:
        return any(inputs.get(key) for key in ("style", "style_degree", "role"))

    @staticmethod
    def _silence_tag(inputs: dict[str, Any]) -> str:
        value = inputs.get("sentence_silence_ms")
        if value is None:
            return ""
        return f'<mstts:silence type="Sentenceboundary" value="{int(value)}ms"/>'

    def _synthesize_headers(self, audio_format: str) -> dict[str, str]:
        headers = {
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": audio_format,
            "User-Agent": "OpenMontage",
        }
        headers.update(self._auth_headers())
        return headers

    def _auth_headers(self) -> dict[str, str]:
        token = self._get_auth_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {"Ocp-Apim-Subscription-Key": self._get_key() or ""}

    def _synthesize_url(self, inputs: dict[str, Any]) -> str:
        url = self._synthesis_endpoint(inputs)
        deployment_id = inputs.get("deployment_id")
        if deployment_id:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode({'deploymentId': deployment_id})}"
        return url

    def _voices_url(self, inputs: dict[str, Any]) -> str:
        endpoint = self._get_endpoint(inputs)
        if endpoint:
            endpoint = endpoint.rstrip("/")
            if endpoint.endswith("/cognitiveservices/voices/list"):
                return endpoint
            if endpoint.endswith("/cognitiveservices/v1"):
                return endpoint.rsplit("/cognitiveservices/v1", 1)[0] + "/cognitiveservices/voices/list"
            return endpoint + "/cognitiveservices/voices/list"
        return self._endpoint_base(inputs, service="tts") + "/cognitiveservices/voices/list"

    def _synthesis_endpoint(self, inputs: dict[str, Any]) -> str:
        endpoint = self._get_endpoint(inputs)
        if endpoint:
            endpoint = endpoint.rstrip("/")
            if endpoint.endswith("/cognitiveservices/v1"):
                return endpoint
            return endpoint + "/cognitiveservices/v1"
        return self._endpoint_base(inputs, service="tts") + "/cognitiveservices/v1"

    def _endpoint_base(self, inputs: dict[str, Any], *, service: str) -> str:
        endpoint = self._get_endpoint(inputs)
        if endpoint:
            return endpoint.rstrip("/")
        region = self._get_region(inputs)
        if service == "tts":
            return f"https://{region}.tts.speech.microsoft.com"
        return f"https://{region}.api.cognitive.microsoft.com"

    @staticmethod
    def _get_key() -> str | None:
        return os.environ.get("AZURE_SPEECH_KEY") or os.environ.get("SPEECH_KEY")

    @staticmethod
    def _get_auth_token() -> str | None:
        return os.environ.get("AZURE_SPEECH_AUTH_TOKEN") or os.environ.get("SPEECH_AUTH_TOKEN")

    @staticmethod
    def _get_region(inputs: dict[str, Any]) -> str | None:
        return inputs.get("region") or os.environ.get("AZURE_SPEECH_REGION") or os.environ.get("SPEECH_REGION")

    @staticmethod
    def _get_endpoint(inputs: dict[str, Any]) -> str | None:
        return inputs.get("endpoint") or os.environ.get("AZURE_SPEECH_ENDPOINT") or os.environ.get("SPEECH_ENDPOINT")

    def _safe_endpoint(self, inputs: dict[str, Any]) -> str | None:
        endpoint = self._get_endpoint(inputs)
        if endpoint:
            return endpoint.rstrip("/")
        region = self._get_region(inputs)
        return f"https://{region}.tts.speech.microsoft.com" if region else None

    @classmethod
    def _extension_for_format(cls, audio_format: str) -> str:
        lowered = audio_format.lower()
        for needle, ext in cls._EXT_MAP.items():
            if needle in lowered:
                return ext
        return "audio"

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = str(exc)
        for env_name in ("AZURE_SPEECH_KEY", "SPEECH_KEY", "AZURE_SPEECH_AUTH_TOKEN", "SPEECH_AUTH_TOKEN"):
            value = os.environ.get(env_name)
            if value:
                message = message.replace(value, "[redacted]")
        return message
