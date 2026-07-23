"""Azure AI Speech transcription tool (Fast Transcription REST API).

Speech-to-text with word-level timestamps and optional speaker diarization,
served by Azure AI Speech. This is an optional cloud STT provider; when
`AZURE_SPEECH_KEY` is configured the agent may prefer it for cloud
transcription, while the local faster-whisper `transcriber` tool remains the
default offline path.

Uses the **Fast Transcription** REST endpoint, which accepts a local audio
file directly (multipart upload) and returns a synchronous JSON result — no
Azure Blob storage, SAS URLs, or async job polling required. Output is shaped
to match `transcriber` exactly (segments + word_timestamps) so it is a
drop-in for `subtitle_gen` and every pipeline that consumes a transcript.

Docs: https://learn.microsoft.com/azure/ai-services/speech-service/fast-transcription-create
"""

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
    ResumeSupport,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# Fast Transcription API version (GA).
_API_VERSION = "2024-11-15"

# Candidate locales used for automatic language identification when the caller
# does not pin a language. Azure Fast Transcription accepts several locales and
# picks the best match per phrase.
_DEFAULT_CANDIDATE_LOCALES = [
    "en-US",
    "es-ES",
    "fr-FR",
    "de-DE",
    "it-IT",
    "pt-BR",
    "hi-IN",
    "ja-JP",
    "zh-CN",
]

# Minimal ISO 639-1 -> default BCP-47 locale map so callers can keep passing the
# short codes the whisper transcriber accepts (e.g. "en", "es").
_ISO_TO_LOCALE = {
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "de": "de-DE",
    "it": "it-IT",
    "pt": "pt-BR",
    "hi": "hi-IN",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "zh": "zh-CN",
    "ar": "ar-EG",
    "ru": "ru-RU",
    "nl": "nl-NL",
    "tr": "tr-TR",
    "pl": "pl-PL",
    "id": "id-ID",
}


class AzureSpeechToText(BaseTool):
    name = "azure_stt"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "azure"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    # Availability is decided by get_status() (env var check), mirroring the
    # ElevenLabs provider tool — dependencies stays empty.
    dependencies = []
    install_instructions = (
        "Set your Azure AI Speech credentials:\n"
        "  export AZURE_SPEECH_KEY=your_speech_resource_key\n"
        "  export AZURE_SPEECH_REGION=eastus   # your Speech resource region\n"
        "Create a Speech resource in the Azure portal "
        "(https://portal.azure.com) — the key and region are on its "
        "'Keys and Endpoint' page. Optionally set AZURE_SPEECH_ENDPOINT to a "
        "full custom endpoint URL instead of the region."
    )
    agent_skills = ["azure-speech-to-text"]

    capabilities = [
        "transcribe",
        "word_timestamps",
        "diarization",
        "language_detection",
    ]

    best_for = [
        "Cloud transcription with word-level timestamps and no GPU",
        "Multi-language auto-detection across a candidate locale set",
        "Speaker diarization without a HuggingFace token",
    ]
    not_good_for = [
        "Fully offline runs (use the whisper `transcriber` fallback)",
        "Single files longer than ~2 hours (use Azure Batch transcription)",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string", "description": "Path to audio or video file"},
            "language": {
                "type": "string",
                "description": (
                    "ISO 639-1 code (e.g. 'en') or BCP-47 locale (e.g. 'en-US'). "
                    "Omit for automatic language identification across common locales."
                ),
            },
            "candidate_locales": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "BCP-47 locales to consider for language ID when `language` is "
                    "not set. Defaults to a common-language shortlist."
                ),
            },
            "diarize": {"type": "boolean", "default": False},
            "max_speakers": {"type": "integer", "default": 4},
            "profanity_filter": {
                "type": "string",
                "enum": ["None", "Masked", "Removed", "Tags"],
                "default": "Masked",
            },
            "output_dir": {"type": "string", "description": "Directory for output files"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "segments": {"type": "array"},
            "word_timestamps": {"type": "array"},
            "language": {"type": "string"},
            "duration_seconds": {"type": "number"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=256,
        vram_mb=0,
        disk_mb=50,
        network_required=True,
    )

    retry_policy = RetryPolicy(
        max_retries=2,
        retryable_errors=["ConnectionError", "Timeout", "429", "503"],
    )
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["input_path", "language", "diarize"]
    side_effects = ["writes transcript JSON to output_dir", "sends audio to Azure AI Speech"]
    fallback = "transcriber"
    fallback_tools = ["transcriber"]
    user_visible_verification = [
        "Check transcript text against source audio",
        "Verify word timestamps align with speech",
    ]

    def get_status(self) -> ToolStatus:
        if os.environ.get("AZURE_SPEECH_KEY") and (
            os.environ.get("AZURE_SPEECH_REGION") or os.environ.get("AZURE_SPEECH_ENDPOINT")
        ):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    # Azure AI Speech Fast Transcription bills per audio-hour (Standard tier is
    # roughly $1.00/audio-hour at time of writing).
    COST_PER_AUDIO_HOUR = 1.0

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Duration is unknown until the audio is transcribed; return the actual
        # cost by passing duration_seconds, else 0.0 as a pre-call estimate.
        seconds = inputs.get("duration_seconds", 0) or 0
        return round((seconds / 3600.0) * self.COST_PER_AUDIO_HOUR, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Fast Transcription is well under real-time; conservative default.
        return 20.0

    def _endpoint(self) -> str:
        endpoint = os.environ.get("AZURE_SPEECH_ENDPOINT")
        if endpoint:
            return endpoint.rstrip("/")
        region = os.environ.get("AZURE_SPEECH_REGION", "").strip()
        return f"https://{region}.api.cognitive.microsoft.com"

    @staticmethod
    def _resolve_locales(inputs: dict[str, Any]) -> list[str]:
        language = inputs.get("language")
        if language:
            if "-" in language:  # already a BCP-47 locale
                return [language]
            return [_ISO_TO_LOCALE.get(language.lower(), f"{language.lower()}-US")]
        candidates = inputs.get("candidate_locales")
        return list(candidates) if candidates else list(_DEFAULT_CANDIDATE_LOCALES)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input file not found: {input_path}")

        api_key = os.environ.get("AZURE_SPEECH_KEY")
        if not api_key or not (
            os.environ.get("AZURE_SPEECH_REGION") or os.environ.get("AZURE_SPEECH_ENDPOINT")
        ):
            return ToolResult(
                success=False,
                error="Azure Speech is not configured. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._transcribe(inputs, api_key, input_path)
        except Exception as exc:
            return ToolResult(success=False, error=f"Transcription failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.model = "azure-fast-transcription"
        result.cost_usd = self.estimate_cost(
            {"duration_seconds": result.data.get("duration_seconds", 0)}
        )
        return result

    def _transcribe(
        self, inputs: dict[str, Any], api_key: str, input_path: Path
    ) -> ToolResult:
        import requests

        output_dir = Path(inputs.get("output_dir", input_path.parent))
        diarize = inputs.get("diarize", False)
        output_dir.mkdir(parents=True, exist_ok=True)

        locales = self._resolve_locales(inputs)
        definition: dict[str, Any] = {
            "locales": locales,
            "profanityFilterMode": inputs.get("profanity_filter", "Masked"),
        }
        if diarize:
            definition["diarization"] = {
                "maxSpeakers": inputs.get("max_speakers", 4),
                "enabled": True,
            }

        url = f"{self._endpoint()}/speechtotext/transcriptions:transcribe?api-version={_API_VERSION}"
        headers = {"Ocp-Apim-Subscription-Key": api_key}

        try:
            with open(input_path, "rb") as audio_file:
                response = requests.post(
                    url,
                    headers=headers,
                    files={
                        "audio": (input_path.name, audio_file, "application/octet-stream"),
                        "definition": (None, json.dumps(definition), "application/json"),
                    },
                    timeout=600,
                )
        except requests.RequestException as exc:  # network/timeout
            return ToolResult(success=False, error=f"Azure Speech request failed: {exc}")

        if response.status_code != 200:
            detail = response.text[:500] if response.text else ""
            return ToolResult(
                success=False,
                error=f"Azure Speech returned HTTP {response.status_code}: {detail}",
            )

        try:
            payload = response.json()
        except ValueError:
            return ToolResult(
                success=False,
                error="Azure Speech returned a non-JSON response.",
            )

        result_data = self._parse_payload(payload, locales)
        result_data["provider"] = "azure"
        output_path = output_dir / f"{input_path.stem}_transcript.json"
        output_path.write_text(json.dumps(result_data, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data=result_data,
            artifacts=[str(output_path)],
        )

    @staticmethod
    def _parse_payload(payload: dict[str, Any], requested_locales: list[str]) -> dict[str, Any]:
        """Map the Fast Transcription response onto the transcriber output schema."""
        segments: list[dict[str, Any]] = []
        word_timestamps: list[dict[str, Any]] = []
        detected_locale: str | None = None

        for idx, phrase in enumerate(payload.get("phrases", [])):
            offset_ms = phrase.get("offsetMilliseconds", 0)
            dur_ms = phrase.get("durationMilliseconds", 0)
            confidence = phrase.get("confidence")
            if detected_locale is None and phrase.get("locale"):
                detected_locale = phrase["locale"]

            seg: dict[str, Any] = {
                "id": idx,
                "start": round(offset_ms / 1000.0, 3),
                "end": round((offset_ms + dur_ms) / 1000.0, 3),
                "text": (phrase.get("text") or "").strip(),
            }
            if "speaker" in phrase:
                seg["speaker"] = phrase["speaker"]

            words = phrase.get("words") or []
            if words:
                seg_words = []
                for w in words:
                    w_offset = w.get("offsetMilliseconds", 0)
                    w_dur = w.get("durationMilliseconds", 0)
                    word_entry = {
                        "word": w.get("text", ""),
                        "start": round(w_offset / 1000.0, 3),
                        "end": round((w_offset + w_dur) / 1000.0, 3),
                        # Fast Transcription has no per-word confidence; carry the
                        # phrase confidence so downstream schemas stay populated.
                        "probability": round(confidence, 3) if confidence is not None else None,
                    }
                    seg_words.append(word_entry)
                    word_timestamps.append(word_entry)
                seg["words"] = seg_words

            segments.append(seg)

        duration_ms = payload.get("durationMilliseconds")
        if duration_ms is None and segments:
            duration_ms = max(int(s["end"] * 1000) for s in segments)

        return {
            "segments": segments,
            "word_timestamps": word_timestamps,
            "language": detected_locale or (requested_locales[0] if requested_locales else None),
            "duration_seconds": round((duration_ms or 0) / 1000.0, 3),
        }
