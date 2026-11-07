"""Gemini transcription tool (Gemini API, gemini-3.5-transcribe).

Speech-to-text with word-level timestamps, automatic language detection and
optional speaker diarization, served by the Gemini Developer API
(``interactions.create`` with a ``transcription_config``). This is an optional
cloud STT provider; when ``GOOGLE_API_KEY`` / ``GEMINI_API_KEY`` is configured
the agent may use it for cloud transcription, while the local faster-whisper
``transcriber`` tool remains the default offline path.

The audio file is uploaded through the Files API, transcribed in verbatim mode
with word timestamps, and the ``word_info`` annotations are shaped to match
``transcriber`` exactly (segments + word_timestamps) so the output is a drop-in
for ``subtitle_gen`` and every pipeline that consumes a transcript.

The Gemini API free tier (Google AI Studio key without billing) covers this
model at the time of writing; usage may then be used to improve Google's
products — do not send confidential audio on the free tier.

Docs: https://ai.google.dev/gemini-api/docs/transcribe
Model: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-transcribe
"""

from __future__ import annotations

import json
import mimetypes
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

_DEFAULT_MODEL = "gemini-3.5-transcribe"

# Gemini closes segments on pauses longer than this when building utterances
# from the flat word stream.
_SEGMENT_GAP_SECONDS = 0.8


def _seconds(value: Any) -> float:
    """Parse a protobuf Duration string ("1.250s") or a number into seconds."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.endswith("s"):
        text = text[:-1]
    return float(text)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class GeminiSpeechToText(BaseTool):
    name = "gemini_stt"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "google"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    # Availability is decided by get_status() (credential check), mirroring the
    # other Google tools — dependencies stays empty.
    dependencies = []
    install_instructions = (
        "Set a Gemini API key (Google AI Studio):\n"
        "  export GOOGLE_API_KEY=your_gemini_api_key   # or GEMINI_API_KEY\n"
        "Create one at https://aistudio.google.com/apikey. The free tier covers "
        "gemini-3.5-transcribe; free-tier content may be used to improve Google's products."
    )
    agent_skills = ["gemini-speech-to-text"]

    capabilities = [
        "transcribe",
        "word_timestamps",
        "diarization",
        "language_detection",
    ]

    best_for = [
        "Cloud transcription with word-level timestamps on a free Gemini API key",
        "Automatic language detection across 85+ languages (code-switching)",
        "Speaker diarization (up to 8 speakers) without a HuggingFace token",
    ]
    not_good_for = [
        "Fully offline runs (use the whisper `transcriber` fallback)",
        "Confidential audio on the free tier (content may be used by Google)",
        "Files longer than 30 minutes with word timestamps (split them first)",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string", "description": "Path to audio or video file"},
            "language": {
                "type": "string",
                "description": (
                    "BCP-47 language hint (e.g. 'es-AR', 'es-419', 'en-US'). "
                    "Omit for automatic language detection."
                ),
            },
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "description": "Gemini transcription model (default gemini-3.5-transcribe).",
            },
            "diarize": {"type": "boolean", "default": False},
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
    side_effects = [
        "writes transcript JSON to output_dir",
        "uploads audio to the Gemini Files API",
    ]
    fallback = "transcriber"
    fallback_tools = ["transcriber", "azure_stt"]
    user_visible_verification = [
        "Check transcript text against source audio",
        "Verify word timestamps align with speech",
    ]

    # gemini-3.5-transcribe paid tier (ai.google.dev pricing, Oct 2026):
    # ~$0.003/min audio input + ~$0.002/min text output. Free tier: $0.
    COST_PER_MINUTE = 0.005

    def get_status(self) -> ToolStatus:
        from tools.google_credentials import has_google_credentials

        return ToolStatus.AVAILABLE if has_google_credentials() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Upper bound on the paid tier; the free tier bills nothing.
        seconds = inputs.get("duration_seconds", 0) or 0
        return round((seconds / 60.0) * self.COST_PER_MINUTE, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0

    @staticmethod
    def build_request(inputs: dict[str, Any], file_uri: str, mime_type: str) -> dict[str, Any]:
        mode: dict[str, Any] = {"type": "verbatim", "timestamp_granularities": ["word"]}
        if inputs.get("diarize"):
            mode["diarization_mode"] = "speaker"
        transcription_config: dict[str, Any] = {"mode": mode}
        language = inputs.get("language")
        transcription_config["language_codes"] = [language] if language else []
        return {
            "model": inputs.get("model") or _DEFAULT_MODEL,
            "input": [{"type": "audio", "uri": file_uri, "mime_type": mime_type}],
            "generation_config": {"transcription_config": transcription_config},
        }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input file not found: {input_path}")
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="Gemini is not configured. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._transcribe(inputs, input_path)
        except Exception as exc:
            return ToolResult(success=False, error=f"Transcription failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        if result.success:
            result.model = inputs.get("model") or _DEFAULT_MODEL
            result.cost_usd = self.estimate_cost(
                {"duration_seconds": result.data.get("duration_seconds", 0)}
            )
        return result

    def _transcribe(self, inputs: dict[str, Any], input_path: Path) -> ToolResult:
        from tools.google_credentials import get_genai_client

        output_dir = Path(inputs.get("output_dir", input_path.parent))
        output_dir.mkdir(parents=True, exist_ok=True)
        mime_type = mimetypes.guess_type(input_path.name)[0] or "audio/mpeg"

        # gemini-3.5-transcribe returns an empty transcript for video containers:
        # send only the audio track (16 kHz mono WAV).
        upload_path = input_path
        tmp_dir = None
        if mime_type.startswith("video/"):
            import shutil
            import subprocess
            import tempfile

            if not shutil.which("ffmpeg"):
                return ToolResult(success=False, error="ffmpeg is required to extract audio from video input")
            tmp_dir = tempfile.TemporaryDirectory(prefix="gemini_stt_")
            upload_path = Path(tmp_dir.name) / f"{input_path.stem}.wav"
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-i", str(input_path), "-vn", "-ac", "1", "-ar", "16000", str(upload_path)],
                check=True,
            )
            mime_type = "audio/wav"

        # Keep a live reference to the client for the whole exchange: the SDK
        # closes a temporary client before a chained request is sent.
        client = get_genai_client()
        try:
            uploaded = client.files.upload(file=str(upload_path), config={"mime_type": mime_type})
            request = self.build_request(
                inputs, _get(uploaded, "uri"), _get(uploaded, "mime_type") or mime_type
            )
            interaction = client.interactions.create(**request)
        finally:
            if tmp_dir is not None:
                tmp_dir.cleanup()

        result_data = self._parse_interaction(interaction, inputs.get("language"))
        if not result_data["segments"]:
            return ToolResult(success=False, error="Gemini returned an empty transcript")
        result_data["provider"] = "google"
        output_path = output_dir / f"{input_path.stem}_transcript.json"
        output_path.write_text(
            json.dumps(result_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return ToolResult(success=True, data=result_data, artifacts=[str(output_path)])

    @staticmethod
    def _word_annotations(interaction: Any) -> list[Any]:
        words: list[Any] = []
        for step in _get(interaction, "steps") or []:
            for content in _get(step, "content") or []:
                for ann in _get(content, "annotations") or []:
                    if _get(ann, "type") == "word_info":
                        words.append(ann)
        return words

    @staticmethod
    def _text(interaction: Any) -> str:
        text = _get(interaction, "output_text")
        if text:
            return str(text).strip()
        parts = []
        for step in _get(interaction, "steps") or []:
            for content in _get(step, "content") or []:
                if _get(content, "type") == "text" and _get(content, "text"):
                    parts.append(str(_get(content, "text")))
        return " ".join(parts).strip()

    @classmethod
    def _parse_interaction(cls, interaction: Any, requested_language: str | None) -> dict[str, Any]:
        """Map Gemini word_info annotations onto the transcriber output schema."""
        word_timestamps: list[dict[str, Any]] = []
        for ann in cls._word_annotations(interaction):
            entry: dict[str, Any] = {
                "word": str(_get(ann, "text", "")).strip(),
                "start": round(_seconds(_get(ann, "start_offset")), 3),
                "end": round(_seconds(_get(ann, "end_offset")), 3),
                # Gemini does not report per-word confidence.
                "probability": None,
            }
            speaker = _get(ann, "speaker")
            if speaker:
                entry["speaker"] = speaker
            if entry["word"]:
                word_timestamps.append(entry)

        # Build segments: split on sentence ends, speaker changes or long pauses.
        segments: list[dict[str, Any]] = []
        current: list[dict[str, Any]] = []

        def flush() -> None:
            if not current:
                return
            seg: dict[str, Any] = {
                "id": len(segments),
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "text": " ".join(w["word"] for w in current),
                "words": list(current),
            }
            if current[0].get("speaker"):
                seg["speaker"] = current[0]["speaker"]
            segments.append(seg)
            current.clear()

        for w in word_timestamps:
            if current and (
                w["start"] - current[-1]["end"] > _SEGMENT_GAP_SECONDS
                or w.get("speaker") != current[-1].get("speaker")
            ):
                flush()
            current.append(w)
            if w["word"].endswith((".", "?", "!")):
                flush()
        flush()

        if not segments:
            text = cls._text(interaction)
            if text:
                segments.append({"id": 0, "start": 0.0, "end": 0.0, "text": text, "words": []})

        duration = max((s["end"] for s in segments), default=0.0)
        return {
            "segments": segments,
            "word_timestamps": word_timestamps,
            "language": requested_language,
            "duration_seconds": round(float(duration), 3),
        }
