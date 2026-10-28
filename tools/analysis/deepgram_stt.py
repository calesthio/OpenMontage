"""Deepgram transcription tool (pre-recorded REST API, Nova-3).

Speech-to-text with word-level timestamps, smart formatting and optional
speaker diarization, served by Deepgram's ``/v1/listen`` endpoint. This is an
optional cloud STT provider; when ``DEEPGRAM_API_KEY`` is configured the agent
may prefer it for cloud transcription, while the local faster-whisper
``transcriber`` tool remains the default offline path.

The local file is uploaded as the raw request body and the JSON result comes
back synchronously — no storage bucket or job polling required. Output is
shaped to match ``transcriber`` exactly (segments + word_timestamps) so it is a
drop-in for ``subtitle_gen`` and every pipeline that consumes a transcript.

Shares the same API key as the ``deepgram_tts`` tool.

Docs: https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded
"""

from __future__ import annotations

import json
import mimetypes
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

_LISTEN_URL = "https://api.deepgram.com/v1/listen"
_DEFAULT_MODEL = "nova-3"


class DeepgramSpeechToText(BaseTool):
    name = "deepgram_stt"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "deepgram"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    # Availability is decided by get_status() (env var check), mirroring the
    # azure_stt provider tool — dependencies stays empty.
    dependencies = []
    install_instructions = (
        "Set your Deepgram API key (same key as deepgram_tts):\n"
        "  export DEEPGRAM_API_KEY=your_deepgram_api_key\n"
        "Create one in the Deepgram console (https://console.deepgram.com) "
        "under 'API Keys'. New accounts include free credit."
    )
    agent_skills = ["deepgram-speech-to-text"]

    capabilities = [
        "transcribe",
        "word_timestamps",
        "diarization",
        "language_detection",
    ]

    best_for = [
        "Cloud transcription with word-level timestamps and no GPU",
        "Fast, accurate Spanish/English transcripts with smart formatting",
        "Speaker diarization without a HuggingFace token",
    ]
    not_good_for = [
        "Fully offline runs (use the whisper `transcriber` fallback)",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string", "description": "Path to audio or video file"},
            "language": {
                "type": "string",
                "description": (
                    "BCP-47 language hint (e.g. 'es', 'es-419', 'en-US') or 'multi' for "
                    "code-switching. Omit for automatic language detection."
                ),
            },
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "description": "Deepgram model, e.g. 'nova-3' (default) or 'nova-2'.",
            },
            "diarize": {"type": "boolean", "default": False},
            "keyterms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Nova-3 keyterm prompting: names/brands to boost recognition.",
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
    idempotency_key_fields = ["input_path", "language", "model", "diarize"]
    side_effects = ["writes transcript JSON to output_dir", "sends audio to Deepgram"]
    fallback = "transcriber"
    fallback_tools = ["transcriber", "azure_stt"]
    user_visible_verification = [
        "Check transcript text against source audio",
        "Verify word timestamps align with speech",
    ]

    # Nova-3 pre-recorded pay-as-you-go (deepgram.com/pricing, Oct 2026):
    # $0.0048/min monolingual, $0.0058/min multilingual.
    COST_PER_MINUTE = 0.0048
    COST_PER_MINUTE_MULTI = 0.0058

    def get_status(self) -> ToolStatus:
        if os.environ.get("DEEPGRAM_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Duration is unknown until the audio is transcribed; return the actual
        # cost by passing duration_seconds, else 0.0 as a pre-call estimate.
        seconds = inputs.get("duration_seconds", 0) or 0
        rate = (
            self.COST_PER_MINUTE_MULTI
            if inputs.get("language") == "multi"
            else self.COST_PER_MINUTE
        )
        return round((seconds / 60.0) * rate, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Pre-recorded transcription is well under real-time; conservative default.
        return 20.0

    @staticmethod
    def _build_params(inputs: dict[str, Any]) -> list[tuple[str, Any]]:
        params: list[tuple[str, Any]] = [
            ("model", inputs.get("model") or _DEFAULT_MODEL),
            ("smart_format", "true"),
            ("punctuate", "true"),
            ("utterances", "true"),
        ]
        language = inputs.get("language")
        if language:
            params.append(("language", language))
        else:
            params.append(("detect_language", "true"))
        if inputs.get("diarize"):
            # `diarize=true` is deprecated; `diarize_model` both enables and selects.
            params.append(("diarize_model", "latest"))
        for term in inputs.get("keyterms") or []:
            params.append(("keyterm", term))
        return params

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input file not found: {input_path}")

        api_key = os.environ.get("DEEPGRAM_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="Deepgram is not configured. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._transcribe(inputs, api_key, input_path)
        except Exception as exc:
            return ToolResult(success=False, error=f"Transcription failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        if result.success:
            result.model = f"deepgram-{inputs.get('model') or _DEFAULT_MODEL}"
            result.cost_usd = self.estimate_cost(
                {
                    "duration_seconds": result.data.get("duration_seconds", 0),
                    "language": inputs.get("language"),
                }
            )
        return result

    def _transcribe(
        self, inputs: dict[str, Any], api_key: str, input_path: Path
    ) -> ToolResult:
        import requests

        output_dir = Path(inputs.get("output_dir", input_path.parent))
        output_dir.mkdir(parents=True, exist_ok=True)

        content_type = mimetypes.guess_type(input_path.name)[0] or "application/octet-stream"
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": content_type,
        }

        try:
            with open(input_path, "rb") as media:
                response = requests.post(
                    _LISTEN_URL,
                    params=self._build_params(inputs),
                    headers=headers,
                    data=media,
                    timeout=600,
                )
        except requests.RequestException as exc:  # network/timeout
            return ToolResult(success=False, error=f"Deepgram request failed: {exc}")

        if response.status_code != 200:
            detail = response.text[:500] if response.text else ""
            return ToolResult(
                success=False,
                error=f"Deepgram returned HTTP {response.status_code}: {detail}",
            )

        try:
            payload = response.json()
        except ValueError:
            return ToolResult(success=False, error="Deepgram returned a non-JSON response.")

        result_data = self._parse_payload(payload, inputs.get("language"))
        result_data["provider"] = "deepgram"
        output_path = output_dir / f"{input_path.stem}_transcript.json"
        output_path.write_text(
            json.dumps(result_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return ToolResult(success=True, data=result_data, artifacts=[str(output_path)])

    @staticmethod
    def _word_entry(w: dict[str, Any]) -> dict[str, Any]:
        entry = {
            # Prefer the smart-formatted form ("Hola," vs "hola") for captions.
            "word": w.get("punctuated_word") or w.get("word", ""),
            "start": round(float(w.get("start", 0.0)), 3),
            "end": round(float(w.get("end", 0.0)), 3),
            "probability": (
                round(float(w["confidence"]), 3) if w.get("confidence") is not None else None
            ),
        }
        if "speaker" in w:
            entry["speaker"] = w["speaker"]
        return entry

    @classmethod
    def _parse_payload(
        cls, payload: dict[str, Any], requested_language: str | None
    ) -> dict[str, Any]:
        """Map the /v1/listen response onto the transcriber output schema."""
        results = payload.get("results") or {}
        channels = results.get("channels") or [{}]
        channel = channels[0] or {}
        alternative = (channel.get("alternatives") or [{}])[0] or {}

        segments: list[dict[str, Any]] = []
        word_timestamps: list[dict[str, Any]] = []

        utterances = results.get("utterances") or []
        if utterances:
            for idx, utt in enumerate(utterances):
                seg_words = [cls._word_entry(w) for w in utt.get("words") or []]
                seg: dict[str, Any] = {
                    "id": idx,
                    "start": round(float(utt.get("start", 0.0)), 3),
                    "end": round(float(utt.get("end", 0.0)), 3),
                    "text": (utt.get("transcript") or "").strip(),
                    "words": seg_words,
                }
                if "speaker" in utt:
                    seg["speaker"] = utt["speaker"]
                segments.append(seg)
                word_timestamps.extend(seg_words)
        else:
            # No utterance segmentation: one segment for the whole alternative.
            seg_words = [cls._word_entry(w) for w in alternative.get("words") or []]
            if seg_words or alternative.get("transcript"):
                segments.append(
                    {
                        "id": 0,
                        "start": seg_words[0]["start"] if seg_words else 0.0,
                        "end": seg_words[-1]["end"] if seg_words else 0.0,
                        "text": (alternative.get("transcript") or "").strip(),
                        "words": seg_words,
                    }
                )
            word_timestamps.extend(seg_words)

        duration = (payload.get("metadata") or {}).get("duration")
        if duration is None and segments:
            duration = max(s["end"] for s in segments)

        language = channel.get("detected_language") or requested_language
        return {
            "segments": segments,
            "word_timestamps": word_timestamps,
            "language": language,
            "duration_seconds": round(float(duration or 0.0), 3),
        }
