"""Sarvam AI text-to-speech provider tool (Bulbul).

Neural TTS for English and 20+ Indic languages, served by Sarvam AI's REST
``/text-to-speech`` endpoint. This is the provider to reach for when narration
must sound natively Indian — Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati,
Kannada, Malayalam, Punjabi, Odia — or when the script is code-mixed
(English words inside an Indic sentence), which the Bulbul models handle
without romanization tricks.

One ``SARVAM_API_KEY`` unlocks the tool. Long scripts are chunked on sentence
boundaries against the model's character ceiling and re-joined losslessly, so
callers can pass a whole narration section without minding the API limit.

Docs: https://docs.sarvam.ai/api-reference/text-to-speech/convert
"""

from __future__ import annotations

import base64
import io
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
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

_API_URL = "https://api.sarvam.ai/text-to-speech"

# Per-request character ceilings enforced by the API, per model.
_MODEL_CHAR_LIMITS = {"bulbul:v3": 2500, "bulbul:v2": 1500}

# Speaker rosters are model-specific — a v2 speaker on v3 is a 400 from the API.
_SPEAKERS_V3 = [
    "shubh", "aditya", "ritu", "priya", "neha", "rahul", "pooja", "rohan",
    "simran", "kavya", "amit", "dev", "ishita", "shreya", "ratan", "varun",
    "manan", "sumit", "roopa", "kabir", "aayan", "ashutosh", "advait", "anand",
    "tanya", "tarun", "sunny", "mani", "gokul", "vijay", "shruti", "suhani",
    "mohit", "kavitha", "rehan", "soham", "rupali",
]
_SPEAKERS_V2 = ["anushka", "manisha", "vidya", "arya", "abhilash", "karun", "hitesh"]

_MODEL_SPEAKERS = {"bulbul:v3": _SPEAKERS_V3, "bulbul:v2": _SPEAKERS_V2}
_MODEL_DEFAULT_SPEAKER = {"bulbul:v3": "shubh", "bulbul:v2": "anushka"}

_LANGUAGES = [
    "en-IN", "hi-IN", "bn-IN", "gu-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN",
    "pa-IN", "ta-IN", "te-IN", "as-IN", "ur-IN", "ne-IN", "kok-IN", "ks-IN",
    "sd-IN", "sa-IN", "sat-IN", "mni-IN", "brx-IN", "mai-IN", "doi-IN",
]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।॥])\s+")


class SarvamTTS(BaseTool):
    name = "sarvam_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "sarvam"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    # Bulbul v3 samples with a temperature, so repeat calls vary slightly.
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    # Availability is an env-var check in get_status(), like the other
    # API-key provider tools — dependencies stays empty.
    dependencies = []
    install_instructions = (
        "Set your Sarvam AI API key:\n"
        "  export SARVAM_API_KEY=your_sarvam_subscription_key\n"
        "Create a key in the Sarvam dashboard (https://dashboard.sarvam.ai/) — "
        "new accounts include free credits. Optionally set SARVAM_API_BASE_URL "
        "to override the default https://api.sarvam.ai host."
    )
    fallback = "piper_tts"
    fallback_tools = ["elevenlabs_tts", "google_tts", "azure_tts", "piper_tts"]
    agent_skills = ["sarvam-tts", "text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "indic_languages",
        "code_mixed_text",
        "pace_control",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "ssml_support": False,
        "long_text_chunking": True,
    }
    best_for = [
        "Hindi and Indic-language narration that sounds natively Indian",
        "Indian-English (en-IN) brand narration without an American accent",
        "code-mixed Hinglish scripts that mix English terms into Indic sentences",
        "multi-language variants of one video for Indian audiences",
    ]
    not_good_for = [
        "voice cloning (use elevenlabs_tts)",
        "non-Indian accents or European/East Asian languages (use google_tts or elevenlabs_tts)",
        "fully offline production (use piper_tts)",
        "SSML markup — Bulbul takes plain text with pace/pitch parameters instead",
    ]

    DEFAULT_MODEL = "bulbul:v3"
    DEFAULT_LANGUAGE = "en-IN"

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "Text to speak. Longer than the model's per-request limit "
                    "(2500 chars for bulbul:v3, 1500 for bulbul:v2) is chunked on "
                    "sentence boundaries and re-joined into one audio file. "
                    "Write numbers over 4 digits with commas ('10,000') so they "
                    "are read as whole numbers."
                ),
            },
            "model": {
                "type": "string",
                "enum": ["bulbul:v3", "bulbul:v2"],
                "default": "bulbul:v3",
                "description": (
                    "bulbul:v3 — 30+ speakers, temperature control, best quality. "
                    "bulbul:v2 — legacy, adds pitch and loudness controls."
                ),
            },
            "target_language_code": {
                "type": "string",
                "enum": _LANGUAGES,
                "default": "en-IN",
                "description": "BCP-47 language of the output speech.",
            },
            "speaker": {
                "type": "string",
                "description": (
                    "Speaker voice, lowercase. Must match the model: v3 speakers "
                    "include shubh, ritu, priya, rahul, kavya, arjun-style names; "
                    "v2 speakers are anushka, manisha, vidya, arya (female) and "
                    "abhilash, karun, hitesh (male). Defaults to the model's own default."
                ),
            },
            "pace": {
                "type": "number",
                "default": 1.0,
                "description": "Speech speed. bulbul:v3 accepts 0.5-2.0, bulbul:v2 accepts 0.3-3.0.",
            },
            "temperature": {
                "type": "number",
                "minimum": 0.01,
                "maximum": 2.0,
                "description": (
                    "Expressiveness vs stability, bulbul:v3 only. Default 0.6; "
                    "lower is steadier, higher is more expressive but can add artifacts."
                ),
            },
            "pitch": {
                "type": "number",
                "minimum": -0.75,
                "maximum": 0.75,
                "description": "Pitch shift, bulbul:v2 only. Ignored on bulbul:v3.",
            },
            "loudness": {
                "type": "number",
                "minimum": 0.1,
                "maximum": 3.0,
                "description": "Output loudness, bulbul:v2 only. Ignored on bulbul:v3.",
            },
            "speech_sample_rate": {
                "type": "integer",
                "enum": [8000, 16000, 22050, 24000, 32000, 44100, 48000],
                "default": 24000,
                "description": "Output sample rate. 32000+ is bulbul:v3 REST only.",
            },
            "enable_preprocessing": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Normalize English words and numerals in mixed-language text. "
                    "bulbul:v2 only — v3 preprocesses automatically."
                ),
            },
            "dict_id": {
                "type": "string",
                "description": "Pronunciation dictionary ID to apply, bulbul:v3 only.",
            },
            "output_path": {"type": "string"},
            "output_format": {
                "type": "string",
                "enum": ["wav", "mp3"],
                "default": "wav",
                "description": (
                    "Container. wav is the API's native output; mp3 for a "
                    "chunked script is transcoded locally with ffmpeg."
                ),
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "model": {"type": "string"},
            "speaker": {"type": "string"},
            "language": {"type": "string"},
            "output": {"type": "string"},
            "format": {"type": "string"},
            "text_length": {"type": "integer"},
            "chunks": {"type": "integer"},
            "request_ids": {"type": "array", "items": {"type": "string"}},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        retryable_errors=["ConnectionError", "Timeout", "429", "503"],
    )
    idempotency_key_fields = [
        "text", "model", "speaker", "target_language_code", "pace", "output_format",
    ]
    side_effects = ["writes audio file to output_path", "sends text to the Sarvam AI API"]
    user_visible_verification = [
        "Listen for natural pronunciation of Indic words and any English terms in the script",
        "Check that numbers, acronyms, and brand names are read the way you intend",
    ]

    # Bulbul is billed in rupees: ₹30 per 10,000 characters.
    INR_PER_CHAR = 30.0 / 10_000
    # Conversion is only for the shared cost_usd reporting surface; override
    # with SARVAM_INR_PER_USD when the rate has moved materially.
    DEFAULT_INR_PER_USD = 88.0

    # HTTP statuses worth a retry — rate limit and transient server errors.
    _RETRY_STATUSES = {429, 500, 502, 503, 504}

    def get_status(self) -> ToolStatus:
        if os.environ.get("SARVAM_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def _inr_per_usd(self) -> float:
        try:
            rate = float(os.environ.get("SARVAM_INR_PER_USD", ""))
            return rate if rate > 0 else self.DEFAULT_INR_PER_USD
        except ValueError:
            return self.DEFAULT_INR_PER_USD

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        chars = len(inputs.get("text", ""))
        return round(chars * self.INR_PER_CHAR / self._inr_per_usd(), 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        model = self._resolve_model(inputs)
        chunks = max(1, -(-len(inputs.get("text", "")) // _MODEL_CHAR_LIMITS[model]))
        return 8.0 * chunks

    # ---- request shaping ----

    def _base_url(self) -> str:
        host = os.environ.get("SARVAM_API_BASE_URL")
        if host:
            return f"{host.rstrip('/')}/text-to-speech"
        return _API_URL

    def _resolve_model(self, inputs: dict[str, Any]) -> str:
        model = str(inputs.get("model") or self.DEFAULT_MODEL).strip().lower()
        return model if model in _MODEL_CHAR_LIMITS else self.DEFAULT_MODEL

    def _resolve_speaker(self, inputs: dict[str, Any], model: str) -> str:
        speaker = str(inputs.get("speaker") or "").strip().lower()
        if not speaker:
            return _MODEL_DEFAULT_SPEAKER[model]
        if speaker not in _MODEL_SPEAKERS[model]:
            raise ValueError(
                f"Speaker '{speaker}' is not available on {model}. "
                f"Valid speakers: {', '.join(_MODEL_SPEAKERS[model])}"
            )
        return speaker

    @staticmethod
    def chunk_text(text: str, limit: int) -> list[str]:
        """Split text into API-sized chunks, preferring sentence boundaries."""
        text = text.strip()
        if len(text) <= limit:
            return [text] if text else []

        chunks: list[str] = []
        current = ""
        for sentence in _SENTENCE_SPLIT.split(text):
            sentence = sentence.strip()
            if not sentence:
                continue
            # A single sentence over the limit gets split on word boundaries.
            pieces = [sentence]
            if len(sentence) > limit:
                pieces, buf = [], ""
                for word in sentence.split():
                    candidate = f"{buf} {word}".strip()
                    if len(candidate) > limit and buf:
                        pieces.append(buf)
                        buf = word
                    else:
                        buf = candidate
                if buf:
                    pieces.append(buf)

            for piece in pieces:
                candidate = f"{current} {piece}".strip()
                if len(candidate) > limit and current:
                    chunks.append(current)
                    current = piece
                else:
                    current = candidate
        if current:
            chunks.append(current)
        return chunks

    def _build_payload(
        self, inputs: dict[str, Any], text: str, model: str, speaker: str, codec: str
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": text,
            "model": model,
            "speaker": speaker,
            "target_language_code": str(
                inputs.get("target_language_code") or self.DEFAULT_LANGUAGE
            ),
            "output_audio_codec": codec,
            "speech_sample_rate": int(inputs.get("speech_sample_rate", 24000)),
        }
        if inputs.get("pace") is not None:
            payload["pace"] = float(inputs["pace"])

        if model == "bulbul:v3":
            # pitch, loudness and enable_preprocessing are v2-only; sending them
            # to v3 is rejected, so they are dropped rather than passed through.
            if inputs.get("temperature") is not None:
                payload["temperature"] = float(inputs["temperature"])
            if inputs.get("dict_id"):
                payload["dict_id"] = str(inputs["dict_id"])
        else:
            if inputs.get("pitch") is not None:
                payload["pitch"] = float(inputs["pitch"])
            if inputs.get("loudness") is not None:
                payload["loudness"] = float(inputs["loudness"])
            payload["enable_preprocessing"] = bool(inputs.get("enable_preprocessing", False))
        return payload

    # ---- audio assembly ----

    @staticmethod
    def merge_wavs(clips: list[bytes]) -> bytes:
        """Concatenate WAV payloads into one file (frames appended in order)."""
        if len(clips) == 1:
            return clips[0]

        out = io.BytesIO()
        writer = None
        try:
            for clip in clips:
                with wave.open(io.BytesIO(clip), "rb") as reader:
                    if writer is None:
                        writer = wave.open(out, "wb")
                        writer.setparams(reader.getparams())
                    writer.writeframes(reader.readframes(reader.getnframes()))
        finally:
            if writer is not None:
                writer.close()
        return out.getvalue()

    @staticmethod
    def _transcode_to_mp3(wav_bytes: bytes, output_path: Path) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError(
                "ffmpeg is required to write mp3 for a multi-chunk script. "
                "Install ffmpeg, or request output_format='wav'."
            )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        try:
            subprocess.run(
                [ffmpeg, "-y", "-i", tmp_path, "-codec:a", "libmp3lame",
                 "-b:a", "192k", str(output_path)],
                check=True, capture_output=True,
            )
        finally:
            os.unlink(tmp_path)

    # ---- execution ----

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("SARVAM_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="Sarvam AI is not configured. " + self.install_instructions,
            )

        text = str(inputs.get("text") or "").strip()
        if not text:
            return ToolResult(success=False, error="No text provided for synthesis.")

        model = self._resolve_model(inputs)
        try:
            speaker = self._resolve_speaker(inputs, model)
        except ValueError as exc:
            return ToolResult(success=False, error=str(exc))

        start = time.time()
        try:
            result = self._synthesize(inputs, api_key, text, model, speaker)
        except Exception as exc:
            return ToolResult(success=False, error=f"TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        if result.success:
            result.cost_usd = self.estimate_cost({"text": text})
        return result

    def _synthesize(
        self, inputs: dict[str, Any], api_key: str, text: str, model: str, speaker: str
    ) -> ToolResult:
        container = str(inputs.get("output_format", "wav")).lower()
        if container not in ("wav", "mp3"):
            container = "wav"

        chunks = self.chunk_text(text, _MODEL_CHAR_LIMITS[model])
        # A single chunk can be delivered in the requested codec directly;
        # multi-chunk scripts are fetched as WAV so they can be joined losslessly.
        api_codec = container if len(chunks) == 1 else "wav"

        audio_parts: list[bytes] = []
        request_ids: list[str] = []
        for chunk in chunks:
            payload = self._build_payload(inputs, chunk, model, speaker, api_codec)
            ok, data = self._post(payload, api_key)
            if not ok:
                return ToolResult(success=False, error=data)
            audios = data.get("audios") or []
            if not audios:
                return ToolResult(
                    success=False, error="Sarvam TTS returned no audio for a text chunk."
                )
            audio_parts.append(base64.b64decode(audios[0]))
            if data.get("request_id"):
                request_ids.append(str(data["request_id"]))

        output_path = Path(inputs.get("output_path", f"tts_output.{container}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if len(audio_parts) == 1:
            output_path.write_bytes(audio_parts[0])
        else:
            merged = self.merge_wavs(audio_parts)
            if container == "mp3":
                self._transcode_to_mp3(merged, output_path)
            else:
                output_path.write_bytes(merged)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "speaker": speaker,
                "language": str(
                    inputs.get("target_language_code") or self.DEFAULT_LANGUAGE
                ),
                "text_length": len(text),
                "chunks": len(chunks),
                "request_ids": request_ids,
                "output": str(output_path),
                "format": container,
            },
            artifacts=[str(output_path)],
            model=f"{model}:{speaker}",
        )

    def _post(self, payload: dict[str, Any], api_key: str) -> tuple[bool, Any]:
        """POST one chunk, retrying transient failures. Returns (ok, data|error)."""
        import requests

        headers = {
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "OpenMontage-sarvam-tts",
        }
        attempts = self.retry_policy.max_retries + 1
        last_error = "Sarvam TTS request failed."

        for attempt in range(attempts):
            try:
                response = requests.post(
                    self._base_url(), headers=headers, json=payload, timeout=180
                )
            except requests.RequestException as exc:
                last_error = f"Sarvam TTS request failed: {exc}"
            else:
                if response.status_code == 200:
                    return True, response.json()
                detail = (response.text or "")[:500]
                last_error = f"Sarvam TTS returned HTTP {response.status_code}: {detail}"
                if response.status_code not in self._RETRY_STATUSES:
                    return False, last_error

            if attempt < attempts - 1:
                time.sleep(2 ** attempt)

        return False, last_error
