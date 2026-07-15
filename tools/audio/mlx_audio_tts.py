"""In-process MLX-Audio text-to-speech provider for Apple Silicon."""

from __future__ import annotations

import gc
import os
import platform
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

from tools.base_tool import (
    BaseTool,
    DependencyError,
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


_MODEL_LOCK = threading.RLock()
_CACHED_MODEL_ID: str | None = None
_CACHED_MODEL: Any = None

DEFAULT_MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-6bit"
DEFAULT_VOICE_ID = "Ryan"
ENABLED_ENV = "MLX_AUDIO_ENABLED"
MODEL_ENV = "MLX_AUDIO_MODEL_ID"
VOICE_ENV = "MLX_AUDIO_VOICE_ID"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_LEGACY_INPUTS = {"model", "voice"}

_RESERVED_GENERATION_OPTIONS = {
    "instruct",
    "lang_code",
    "ref_audio",
    "ref_text",
    "speed",
    "stream",
    "text",
    "voice",
}


def _load_runtime() -> tuple[Callable[..., Any], Callable[..., Any], Any]:
    """Import MLX-Audio only when execution has passed availability checks."""
    import mlx.core as mx
    from mlx_audio.audio_io import write as audio_write
    from mlx_audio.tts.utils import load_model

    return load_model, audio_write, mx


def _audio_size(audio: Any) -> int:
    """Return an array-like audio object's sample count without copying it."""
    size = getattr(audio, "size", None)
    if callable(size):
        size = size()
    if isinstance(size, int):
        return size

    shape = getattr(audio, "shape", None)
    if not shape:
        return 0

    total = 1
    for dimension in shape:
        total *= int(dimension)
    return total


def _release_cached_model(mx: Any) -> None:
    """Release the active model and return its MLX allocations to the cache."""
    global _CACHED_MODEL, _CACHED_MODEL_ID

    old_model = _CACHED_MODEL
    _CACHED_MODEL = None
    _CACHED_MODEL_ID = None
    del old_model
    gc.collect()
    mx.clear_cache()


def _get_cached_model(model_id: str, load_model: Callable[..., Any], mx: Any) -> Any:
    """Load at most one model and reuse it while the requested ID is unchanged."""
    global _CACHED_MODEL, _CACHED_MODEL_ID

    if _CACHED_MODEL is not None and _CACHED_MODEL_ID != model_id:
        _release_cached_model(mx)

    if _CACHED_MODEL is None:
        model = load_model(model_id)
        _CACHED_MODEL = model
        _CACHED_MODEL_ID = model_id

    return _CACHED_MODEL


class MLXAudioTTS(BaseTool):
    """Generate one verified WAV with a configurable MLX-Audio model."""

    name = "mlx_audio_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "mlx_audio"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = ["python:mlx_audio", "binary:ffprobe"]
    install_instructions = (
        "Set MLX_AUDIO_ENABLED=true. MLX-Audio requires macOS on Apple Silicon "
        "and ffprobe from FFmpeg (`brew install ffmpeg`). Install the TTS-only "
        "Python dependency with "
        "`make install-mlx-audio`, or run `python -m pip install "
        "'mlx-audio[tts]>=0.4.5,<0.5'`."
    )
    agent_skills = ["mlx-audio"]

    capabilities = [
        "text_to_speech",
        "explicit_model_selection",
        "voice_selection",
        "local_generation",
        "wav_output",
    ]
    supports = {
        "apple_silicon": True,
        "local_generation": True,
        "output_formats": ["wav"],
        "hugging_face_model_ids": True,
        "local_model_paths": True,
        "voice_selection": "model_dependent",
        "multilingual": "model_dependent",
        "speed_control": "model_dependent",
        "voice_cloning": "model_dependent",
        "instructions": "model_dependent",
        "streaming": False,
        "default_model": DEFAULT_MODEL_ID,
        "default_voice": DEFAULT_VOICE_ID,
    }
    best_for = [
        "private on-device TTS on Apple Silicon",
        "configurable MLX-Audio model and voice selection",
        "local WAV narration with no per-generation fee",
    ]
    not_good_for = [
        "non-Apple-Silicon systems",
        "streaming playback",
        "workflows that require one voice or model to work across every model family",
    ]

    input_schema = {
        "type": "object",
        "required": ["text", "output_path"],
        "properties": {
            "text": {
                "type": "string",
                "minLength": 1,
                "description": "Text to synthesize.",
            },
            "model_id": {
                "type": "string",
                "minLength": 1,
                "default": DEFAULT_MODEL_ID,
                "description": (
                    "Hugging Face model ID or local MLX-Audio model path. "
                    "Overrides MLX_AUDIO_MODEL_ID and the built-in default."
                ),
            },
            "output_path": {
                "type": "string",
                "minLength": 1,
                "pattern": "\\.[wW][aA][vV]$",
                "description": "Required WAV destination.",
            },
            "voice_id": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "Model-specific voice, mapped to model.generate(voice=...). "
                    "Overrides MLX_AUDIO_VOICE_ID. Ryan is used when the built-in "
                    "default model is active and no voice is configured."
                ),
            },
            "language": {
                "type": "string",
                "minLength": 1,
                "description": "Model-specific language code, mapped to lang_code.",
            },
            "instructions": {
                "type": "string",
                "minLength": 1,
                "description": "Model-specific delivery or voice-design instruction.",
            },
            "speed": {
                "type": "number",
                "exclusiveMinimum": 0,
                "description": "Model-specific speed multiplier.",
            },
            "reference_audio_path": {
                "type": "string",
                "minLength": 1,
                "description": "Existing reference audio path for models that support cloning.",
            },
            "reference_text": {
                "type": "string",
                "minLength": 1,
                "description": "Transcript corresponding to reference_audio_path.",
            },
            "generation_options": {
                "type": "object",
                "description": "Additional model-specific model.generate keyword arguments.",
            },
        },
    }

    output_schema = {
        "type": "object",
        "required": [
            "provider",
            "model",
            "voice_id",
            "language",
            "speed",
            "instructions",
            "text_length",
            "format",
            "sample_rate",
            "audio_duration_seconds",
            "output",
            "output_path",
        ],
        "properties": {
            "provider": {"const": "mlx_audio"},
            "model": {"type": "string"},
            "voice_id": {"type": ["string", "null"]},
            "language": {"type": ["string", "null"]},
            "speed": {"type": ["number", "null"]},
            "instructions": {"type": ["string", "null"]},
            "text_length": {"type": "integer", "minimum": 1},
            "format": {"const": "wav"},
            "sample_rate": {"type": "integer", "minimum": 1},
            "audio_duration_seconds": {"type": "number", "exclusiveMinimum": 0},
            "output": {"type": "string"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=4096,
        vram_mb=4096,
        disk_mb=4096,
        network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = [
        "text",
        "model_id",
        "voice_id",
        "language",
        "instructions",
        "speed",
        "reference_audio_path",
        "reference_text",
        "generation_options",
    ]
    side_effects = [
        "writes a WAV file to output_path",
        "may download Hugging Face model weights on first use of a model_id",
        "loads one MLX-Audio model into unified memory and releases it when model_id changes",
    ]
    fallback = None
    fallback_tools: list[str] = []
    user_visible_verification = [
        "Listen to the WAV for pronunciation, voice, language, pacing, and instruction adherence",
        "Confirm the selected model supports every optional control that was requested",
    ]

    def get_status(self) -> ToolStatus:
        """Report availability only when explicitly enabled on supported hardware."""
        if os.environ.get(ENABLED_ENV, "").strip().lower() not in _TRUE_VALUES:
            return ToolStatus.UNAVAILABLE

        machine = platform.machine().lower()
        if platform.system() != "Darwin" or machine != "arm64":
            return ToolStatus.UNAVAILABLE

        try:
            self.check_dependencies()
        except DependencyError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Return a conservative warm-cache estimate for local generation.

        Actual latency varies substantially by model and Apple Silicon tier.
        First-time model downloads are intentionally excluded.
        """
        return 30.0

    def idempotency_key(self, inputs: dict[str, Any]) -> str:
        """Include resolved configuration defaults in the generation identity."""
        effective_inputs = dict(inputs)
        model_id = self._resolve_model_id(inputs)
        effective_inputs["model_id"] = model_id
        voice_id = self._resolve_voice_id(inputs, model_id)
        if voice_id is not None:
            effective_inputs["voice_id"] = voice_id
        return super().idempotency_key(effective_inputs)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        validation_error = self._validate_inputs(inputs)
        if validation_error:
            return ToolResult(success=False, error=validation_error)

        model_id = self._resolve_model_id(inputs)
        voice_id = self._resolve_voice_id(inputs, model_id)
        effective_inputs = dict(inputs)
        effective_inputs["model_id"] = model_id
        if voice_id is not None:
            effective_inputs["voice_id"] = voice_id
        output_path = Path(inputs["output_path"].strip()).expanduser()

        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="MLX-Audio TTS is unavailable. " + self.install_instructions,
            )

        try:
            with _MODEL_LOCK:
                result = self._generate(effective_inputs, model_id, output_path)
        except Exception as exc:
            result = ToolResult(
                success=False,
                error=f"MLX-Audio TTS failed for model {model_id!r}: {exc}",
            )

        result.duration_seconds = round(time.monotonic() - started, 3)
        result.cost_usd = 0.0
        if result.success:
            result.model = model_id
        return result

    @staticmethod
    def _validate_inputs(inputs: dict[str, Any]) -> str | None:
        legacy = set(inputs).intersection(_LEGACY_INPUTS)
        if legacy:
            fields = ", ".join(sorted(legacy))
            return (
                f"Unsupported legacy MLX-Audio TTS input field(s): {fields}. "
                "Use model_id and voice_id."
            )

        for field in ("text", "output_path"):
            value = inputs.get(field)
            if not isinstance(value, str) or not value.strip():
                return f"Missing or empty required input: {field}"

        if "model_id" in inputs:
            model_id = inputs["model_id"]
            if not isinstance(model_id, str) or not model_id.strip():
                return "MLX-Audio TTS input model_id must be a non-empty string"

        if Path(inputs["output_path"].strip()).suffix.lower() != ".wav":
            return "MLX-Audio TTS output_path must end with .wav"

        for field in ("voice_id", "language", "instructions", "reference_text"):
            if field in inputs:
                value = inputs[field]
                if not isinstance(value, str) or not value.strip():
                    return f"MLX-Audio TTS input {field} must be a non-empty string"

        if "speed" in inputs:
            speed = inputs["speed"]
            if isinstance(speed, bool) or not isinstance(speed, (int, float)) or speed <= 0:
                return "MLX-Audio TTS input speed must be a number greater than zero"

        reference_audio = inputs.get("reference_audio_path")
        if reference_audio is not None:
            if not isinstance(reference_audio, str) or not reference_audio.strip():
                return "MLX-Audio TTS input reference_audio_path must be a non-empty string"
            if not Path(reference_audio).expanduser().is_file():
                return f"Reference audio file not found: {reference_audio}"

        generation_options = inputs.get("generation_options", {})
        if not isinstance(generation_options, dict):
            return "MLX-Audio TTS input generation_options must be an object"
        if any(not isinstance(key, str) for key in generation_options):
            return "MLX-Audio TTS generation_options keys must be strings"

        conflicts = _RESERVED_GENERATION_OPTIONS.intersection(generation_options)
        if conflicts:
            fields = ", ".join(sorted(conflicts))
            return (
                "MLX-Audio TTS generation_options cannot override canonical "
                f"parameter(s): {fields}"
            )

        return None

    @staticmethod
    def _resolve_model_id(inputs: dict[str, Any]) -> str:
        requested = inputs.get("model_id")
        if isinstance(requested, str) and requested.strip():
            return requested.strip()

        configured = os.environ.get(MODEL_ENV, "").strip()
        return configured or DEFAULT_MODEL_ID

    @staticmethod
    def _resolve_voice_id(inputs: dict[str, Any], model_id: str) -> str | None:
        requested = inputs.get("voice_id")
        if isinstance(requested, str) and requested.strip():
            return requested.strip()

        configured = os.environ.get(VOICE_ENV, "").strip()
        if configured:
            return configured
        if model_id == DEFAULT_MODEL_ID:
            return DEFAULT_VOICE_ID
        return None

    @staticmethod
    def _generation_kwargs(inputs: dict[str, Any]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "text": inputs["text"],
            "stream": False,
        }
        mappings = {
            "voice_id": "voice",
            "language": "lang_code",
            "instructions": "instruct",
            "speed": "speed",
            "reference_audio_path": "ref_audio",
            "reference_text": "ref_text",
        }
        for input_name, generate_name in mappings.items():
            if input_name in inputs:
                value = inputs[input_name]
                if input_name == "reference_audio_path":
                    value = str(Path(value).expanduser())
                kwargs[generate_name] = value

        kwargs.update(inputs.get("generation_options", {}))
        return kwargs

    def _generate(
        self,
        inputs: dict[str, Any],
        model_id: str,
        output_path: Path,
    ) -> ToolResult:
        load_model, audio_write, mx = _load_runtime()
        model = _get_cached_model(model_id, load_model, mx)
        generated = model.generate(**self._generation_kwargs(inputs))

        audio_chunks: list[Any] = []
        sample_rate: int | None = None
        for segment in generated:
            audio = getattr(segment, "audio", None)
            if audio is None or _audio_size(audio) <= 0:
                raise ValueError("MLX-Audio model returned an empty audio segment")

            segment_rate = getattr(segment, "sample_rate", None)
            if not isinstance(segment_rate, (int, float)) or int(segment_rate) <= 0:
                raise ValueError("MLX-Audio model returned no valid sample rate")
            segment_rate = int(segment_rate)
            if sample_rate is not None and segment_rate != sample_rate:
                raise ValueError("MLX-Audio model returned segments with different sample rates")

            sample_rate = segment_rate
            audio_chunks.append(audio)

        if not audio_chunks or sample_rate is None:
            raise ValueError("MLX-Audio model generated no audio")

        combined_audio = (
            mx.concatenate(audio_chunks, axis=0)
            if len(audio_chunks) > 1
            else audio_chunks[0]
        )
        if _audio_size(combined_audio) <= 0:
            raise ValueError("MLX-Audio model generated no audio samples")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{output_path.stem}-",
                suffix=".wav",
                dir=output_path.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)

            audio_write(str(temporary_path), combined_audio, sample_rate, format="wav")
            if not temporary_path.is_file() or temporary_path.stat().st_size <= 44:
                raise ValueError("MLX-Audio produced an empty WAV file")

            from tools.analysis.audio_probe import AudioProbe

            probe = AudioProbe().execute({"input_path": str(temporary_path)})
            if not probe.success:
                raise ValueError(f"Generated WAV validation failed: {probe.error}")

            audio_info = probe.data.get("audio")
            duration = probe.data.get("duration_seconds")
            if not isinstance(audio_info, dict):
                raise ValueError("Generated WAV validation found no audio stream")
            if not isinstance(duration, (int, float)) or duration <= 0:
                raise ValueError("Generated WAV validation found no audio duration")

            probed_rate = audio_info.get("sample_rate")
            if not isinstance(probed_rate, int) or probed_rate <= 0:
                raise ValueError("Generated WAV validation found no sample rate")
            if probed_rate != sample_rate:
                raise ValueError(
                    "Generated WAV sample rate mismatch: "
                    f"model returned {sample_rate} Hz, probe found {probed_rate} Hz"
                )

            os.replace(temporary_path, output_path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        output = str(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model_id,
                "voice_id": inputs.get("voice_id"),
                "language": inputs.get("language"),
                "speed": inputs.get("speed"),
                "instructions": inputs.get("instructions"),
                "text_length": len(inputs["text"]),
                "format": "wav",
                "sample_rate": probed_rate,
                "audio_duration_seconds": duration,
                "output": output,
                "output_path": output,
            },
            artifacts=[output],
            cost_usd=0.0,
            model=model_id,
        )
