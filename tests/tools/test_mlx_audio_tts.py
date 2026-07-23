"""Focused tests for the in-process MLX-Audio TTS provider."""

from __future__ import annotations

import importlib
import sys
import time
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

import tools.audio.mlx_audio_tts as mlx_provider
from tools.analysis.audio_probe import AudioProbe
from tools.audio.mlx_audio_tts import MLXAudioTTS
from tools.audio.tts_selector import TTSSelector
from tools.base_tool import DependencyError, ToolResult, ToolStatus
from tools.tool_registry import ToolRegistry


@pytest.fixture(autouse=True)
def reset_model_cache(monkeypatch):
    monkeypatch.setattr(mlx_provider, "_CACHED_MODEL", None)
    monkeypatch.setattr(mlx_provider, "_CACHED_MODEL_ID", None)
    monkeypatch.delenv(mlx_provider.ENABLED_ENV, raising=False)
    monkeypatch.delenv(mlx_provider.MODEL_ENV, raising=False)
    monkeypatch.delenv(mlx_provider.VOICE_ENV, raising=False)


def _write_wav(path: str, audio, sample_rate: int, *, format: str) -> None:
    assert format == "wav"
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())


def _probe_result(sample_rate: int = 24000, duration: float = 0.5) -> ToolResult:
    return ToolResult(
        success=True,
        data={
            "duration_seconds": duration,
            "format_name": "wav",
            "audio": {"codec": "pcm_s16le", "sample_rate": sample_rate},
        },
    )


def _install_mock_runtime(
    monkeypatch,
    models: list[object],
    *,
    probe_result: ToolResult | None = None,
):
    load_model = MagicMock(side_effect=models)
    mx = SimpleNamespace(
        concatenate=MagicMock(side_effect=lambda chunks, axis=0: np.concatenate(chunks, axis=axis)),
        clear_cache=MagicMock(),
    )
    writer = MagicMock(side_effect=_write_wav)

    monkeypatch.setattr(MLXAudioTTS, "get_status", lambda self: ToolStatus.AVAILABLE)
    monkeypatch.setattr(
        mlx_provider,
        "_load_runtime",
        lambda: (load_model, writer, mx),
    )
    probe = MagicMock(return_value=probe_result or _probe_result())
    monkeypatch.setattr(AudioProbe, "execute", probe)
    return load_model, writer, mx, probe


def _model(*chunks: np.ndarray, sample_rate: int = 24000):
    model = MagicMock()
    model.sample_rate = sample_rate
    model.generate.return_value = [
        SimpleNamespace(audio=chunk, sample_rate=sample_rate) for chunk in chunks
    ]
    return model


def test_contract_declares_canonical_local_provider():
    tool = MLXAudioTTS()
    info = tool.get_info()

    assert info["name"] == "mlx_audio_tts"
    assert info["provider"] == "mlx_audio"
    assert info["capability"] == "tts"
    assert info["runtime"] == "local_gpu"
    assert info["dependencies"] == ["python:mlx_audio", "binary:ffprobe"]
    assert "ffprobe" in info["install_instructions"]
    assert tool.input_schema["required"] == ["text", "output_path"]
    assert (
        tool.input_schema["properties"]["model_id"]["default"]
        == mlx_provider.DEFAULT_MODEL_ID
    )
    assert set(tool.input_schema["properties"]) == {
        "text",
        "model_id",
        "output_path",
        "voice_id",
        "language",
        "instructions",
        "speed",
        "reference_audio_path",
        "reference_text",
        "generation_options",
    }
    assert tool.retry_policy.max_retries == 0
    assert tool.fallback is None
    assert tool.fallback_tools == []
    assert tool.resource_profile.network_required is False
    assert tool.estimate_cost({"text": "hello"}) == 0.0
    assert tool.estimate_runtime({"text": "hello"}) == 30.0
    assert tool.quality_score is None
    assert tool.latency_p50_seconds is None
    assert "first use" in " ".join(tool.side_effects)
    assert tool.supports["voice_selection"] == "model_dependent"
    assert tool.supports["multilingual"] == "model_dependent"
    assert tool.supports["voice_cloning"] == "model_dependent"


def test_wav_schema_pattern_is_ecma_compatible_and_case_insensitive(tmp_path):
    pattern = MLXAudioTTS.input_schema["properties"]["output_path"]["pattern"]
    assert pattern == r"\.[wW][aA][vV]$"

    validator = Draft202012Validator(MLXAudioTTS.input_schema)
    validator.validate(
        {
            "text": "hello",
            "output_path": str(tmp_path / "speech.WAV"),
        }
    )
    with pytest.raises(ValidationError):
        validator.validate(
            {
                "text": "hello",
                "output_path": str(tmp_path / "speech.mp3"),
            }
        )


def test_module_import_does_not_import_mlx_audio(monkeypatch):
    imported: list[str] = []
    original_import = __import__

    def guarded_import(name, *args, **kwargs):
        if name == "mlx_audio" or name.startswith("mlx_audio.") or name == "mlx.core":
            imported.append(name)
            raise AssertionError(f"eager MLX import: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)
    importlib.reload(sys.modules["tools.audio.mlx_audio_tts"])
    assert imported == []


def test_status_requires_macos_on_apple_silicon(monkeypatch):
    tool = MLXAudioTTS()
    check_dependencies = MagicMock()
    monkeypatch.setenv(mlx_provider.ENABLED_ENV, "true")
    monkeypatch.setattr(tool, "check_dependencies", check_dependencies)
    monkeypatch.setattr(mlx_provider.platform, "system", lambda: "Linux")
    monkeypatch.setattr(mlx_provider.platform, "machine", lambda: "x86_64")

    assert tool.get_status() == ToolStatus.UNAVAILABLE
    check_dependencies.assert_not_called()


def test_status_is_available_when_platform_and_dependency_match(monkeypatch):
    tool = MLXAudioTTS()
    monkeypatch.setenv(mlx_provider.ENABLED_ENV, "true")
    monkeypatch.setattr(mlx_provider.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mlx_provider.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(tool, "check_dependencies", MagicMock())

    assert tool.get_status() == ToolStatus.AVAILABLE


def test_status_rejects_noncanonical_darwin_architecture(monkeypatch):
    tool = MLXAudioTTS()
    check_dependencies = MagicMock()
    monkeypatch.setenv(mlx_provider.ENABLED_ENV, "true")
    monkeypatch.setattr(mlx_provider.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mlx_provider.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(tool, "check_dependencies", check_dependencies)

    assert tool.get_status() == ToolStatus.UNAVAILABLE
    check_dependencies.assert_not_called()


def test_status_is_unavailable_when_dependency_is_missing(monkeypatch):
    tool = MLXAudioTTS()
    monkeypatch.setenv(mlx_provider.ENABLED_ENV, "true")
    monkeypatch.setattr(mlx_provider.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mlx_provider.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(
        tool,
        "check_dependencies",
        MagicMock(side_effect=DependencyError("missing")),
    )

    assert tool.get_status() == ToolStatus.UNAVAILABLE


@pytest.mark.parametrize("value", [None, "", "0", "false", "no"])
def test_status_requires_explicit_enablement(monkeypatch, value):
    tool = MLXAudioTTS()
    check_dependencies = MagicMock()
    monkeypatch.setattr(tool, "check_dependencies", check_dependencies)
    monkeypatch.setattr(mlx_provider.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mlx_provider.platform, "machine", lambda: "arm64")
    if value is None:
        monkeypatch.delenv(mlx_provider.ENABLED_ENV, raising=False)
    else:
        monkeypatch.setenv(mlx_provider.ENABLED_ENV, value)

    assert tool.get_status() == ToolStatus.UNAVAILABLE
    check_dependencies.assert_not_called()


@pytest.mark.parametrize("missing", ["text", "output_path"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_required_inputs_must_be_present_and_nonempty(tmp_path, missing, value):
    inputs = {
        "text": "hello",
        "model_id": "org/model",
        "output_path": str(tmp_path / "speech.wav"),
    }
    if value is None:
        inputs.pop(missing)
    else:
        inputs[missing] = value

    result = MLXAudioTTS().execute(inputs)

    assert result.success is False
    assert missing in result.error
    assert not (tmp_path / "speech.wav").exists()


@pytest.mark.parametrize("value", [None, "", "   "])
def test_explicit_model_id_must_be_nonempty(tmp_path, value):
    inputs = {
        "text": "hello",
        "model_id": value,
        "output_path": str(tmp_path / "speech.wav"),
    }

    result = MLXAudioTTS().execute(inputs)

    assert result.success is False
    assert "model_id" in result.error


def test_output_path_is_required_to_be_wav(tmp_path):
    result = MLXAudioTTS().execute(
        {
            "text": "hello",
            "model_id": "org/model",
            "output_path": str(tmp_path / "speech.mp3"),
        }
    )

    assert result.success is False
    assert ".wav" in result.error
    assert not (tmp_path / "speech.mp3").exists()


@pytest.mark.parametrize(
    "reserved",
    ["text", "voice", "lang_code", "instruct", "speed", "ref_audio", "ref_text", "stream"],
)
def test_generation_options_cannot_override_canonical_arguments(tmp_path, reserved):
    result = MLXAudioTTS().execute(
        {
            "text": "hello",
            "model_id": "org/model",
            "output_path": str(tmp_path / "speech.wav"),
            "generation_options": {reserved: "override"},
        }
    )

    assert result.success is False
    assert reserved in result.error


def test_legacy_provider_arguments_are_rejected(tmp_path):
    result = MLXAudioTTS().execute(
        {
            "text": "hello",
            "model_id": "org/model",
            "output_path": str(tmp_path / "speech.wav"),
            "model": "legacy/model",
            "voice": "legacy-voice",
        }
    )

    assert result.success is False
    assert "model" in result.error
    assert "voice" in result.error


def test_selector_metadata_is_ignored_by_provider_execution(tmp_path, monkeypatch):
    model = _model(np.ones(1000, dtype=np.float32))
    _install_mock_runtime(monkeypatch, [model])
    result = MLXAudioTTS().execute(
        {
            "text": "hello",
            "model_id": "org/model",
            "output_path": str(tmp_path / "speech.wav"),
            "preferred_provider": "mlx_audio",
        }
    )

    assert result.success is True
    model.generate.assert_called_once_with(text="hello", stream=False)


def test_missing_reference_audio_fails_before_runtime_loading(tmp_path, monkeypatch):
    load_runtime = MagicMock()
    monkeypatch.setattr(mlx_provider, "_load_runtime", load_runtime)

    result = MLXAudioTTS().execute(
        {
            "text": "hello",
            "model_id": "org/model",
            "output_path": str(tmp_path / "speech.wav"),
            "reference_audio_path": str(tmp_path / "missing.wav"),
        }
    )

    assert result.success is False
    assert "Reference audio file not found" in result.error
    load_runtime.assert_not_called()


def test_missing_dependency_returns_failure_without_importing_runtime(tmp_path, monkeypatch):
    load_runtime = MagicMock()
    monkeypatch.setattr(MLXAudioTTS, "get_status", lambda self: ToolStatus.UNAVAILABLE)
    monkeypatch.setattr(mlx_provider, "_load_runtime", load_runtime)

    result = MLXAudioTTS().execute(
        {
            "text": "hello",
            "model_id": "org/model",
            "output_path": str(tmp_path / "speech.wav"),
        }
    )

    assert result.success is False
    assert "unavailable" in result.error.lower()
    assert "install-mlx-audio" in result.error
    load_runtime.assert_not_called()


def test_direct_python_api_maps_canonical_fields_and_joins_segments(tmp_path, monkeypatch):
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"reference")
    first = np.full(6000, 0.1, dtype=np.float32)
    second = np.full(6000, -0.1, dtype=np.float32)
    model = _model(first, second)
    load_model, writer, mx, probe = _install_mock_runtime(monkeypatch, [model])
    output = tmp_path / "nested" / "speech.wav"

    result = MLXAudioTTS().execute(
        {
            "text": "Hello from MLX-Audio",
            "model_id": "mlx-community/example-6bit",
            "output_path": str(output),
            "voice_id": "speaker-one",
            "language": "English",
            "instructions": "Warm and concise",
            "speed": 1.1,
            "reference_audio_path": str(reference),
            "reference_text": "Reference transcript",
            "generation_options": {"temperature": 0.7, "top_p": 0.9},
        }
    )

    assert result.success is True
    load_model.assert_called_once_with("mlx-community/example-6bit")
    model.generate.assert_called_once_with(
        text="Hello from MLX-Audio",
        voice="speaker-one",
        lang_code="English",
        instruct="Warm and concise",
        speed=1.1,
        ref_audio=str(reference),
        ref_text="Reference transcript",
        stream=False,
        temperature=0.7,
        top_p=0.9,
    )
    mx.concatenate.assert_called_once()
    written_audio = writer.call_args.args[1]
    np.testing.assert_array_equal(written_audio, np.concatenate([first, second]))
    assert writer.call_args.args[2] == 24000
    assert writer.call_args.kwargs == {"format": "wav"}
    probe.assert_called_once()
    assert probe.call_args.args[0]["input_path"].endswith(".wav")

    assert output.is_file()
    with wave.open(str(output), "rb") as wav_file:
        assert wav_file.getnframes() == 12000
        assert wav_file.getframerate() == 24000

    assert result.data == {
        "provider": "mlx_audio",
        "model": "mlx-community/example-6bit",
        "voice_id": "speaker-one",
        "language": "English",
        "speed": 1.1,
        "instructions": "Warm and concise",
        "text_length": len("Hello from MLX-Audio"),
        "format": "wav",
        "sample_rate": 24000,
        "audio_duration_seconds": 0.5,
        "output": str(output),
        "output_path": str(output),
    }
    assert result.artifacts == [str(output)]
    assert result.model == "mlx-community/example-6bit"
    assert result.cost_usd == 0.0
    assert result.duration_seconds != result.data["audio_duration_seconds"]


def test_environment_model_and_voice_are_used_when_request_omits_them(
    tmp_path,
    monkeypatch,
):
    model = _model(np.ones(1000, dtype=np.float32))
    load_model, _, _, _ = _install_mock_runtime(monkeypatch, [model])
    monkeypatch.setenv(mlx_provider.MODEL_ENV, "org/configured-model")
    monkeypatch.setenv(mlx_provider.VOICE_ENV, "configured-voice")

    result = MLXAudioTTS().execute(
        {
            "text": "configured narration",
            "output_path": str(tmp_path / "configured.wav"),
        }
    )

    assert result.success is True
    load_model.assert_called_once_with("org/configured-model")
    model.generate.assert_called_once_with(
        text="configured narration",
        voice="configured-voice",
        stream=False,
    )
    assert result.data["model"] == "org/configured-model"
    assert result.data["voice_id"] == "configured-voice"


def test_request_model_and_voice_override_environment_configuration(
    tmp_path,
    monkeypatch,
):
    model = _model(np.ones(1000, dtype=np.float32))
    load_model, _, _, _ = _install_mock_runtime(monkeypatch, [model])
    monkeypatch.setenv(mlx_provider.MODEL_ENV, "org/configured-model")
    monkeypatch.setenv(mlx_provider.VOICE_ENV, "configured-voice")

    result = MLXAudioTTS().execute(
        {
            "text": "request narration",
            "model_id": "org/request-model",
            "voice_id": "request-voice",
            "output_path": str(tmp_path / "request.wav"),
        }
    )

    assert result.success is True
    load_model.assert_called_once_with("org/request-model")
    model.generate.assert_called_once_with(
        text="request narration",
        voice="request-voice",
        stream=False,
    )


def test_environment_model_and_voice_change_idempotency_key(monkeypatch):
    tool = MLXAudioTTS()
    inputs = {"text": "same narration"}
    default_key = tool.idempotency_key(inputs)

    monkeypatch.setenv(mlx_provider.MODEL_ENV, "org/configured-model")
    monkeypatch.setenv(mlx_provider.VOICE_ENV, "configured-voice")

    assert tool.idempotency_key(inputs) != default_key


def test_same_model_is_reused_and_switch_clears_mlx_cache(tmp_path, monkeypatch):
    model_a = _model(np.ones(1000, dtype=np.float32))
    model_b = _model(np.ones(1000, dtype=np.float32) * 0.5)
    load_model, _, mx, _ = _install_mock_runtime(monkeypatch, [model_a, model_b])
    tool = MLXAudioTTS()

    for index, model_id in enumerate(["org/model-a", "org/model-a", "org/model-b"]):
        result = tool.execute(
            {
                "text": f"utterance {index}",
                "model_id": model_id,
                "output_path": str(tmp_path / f"speech-{index}.wav"),
            }
        )
        assert result.success is True

    assert load_model.call_args_list == [call("org/model-a"), call("org/model-b")]
    assert model_a.generate.call_count == 2
    assert model_b.generate.call_count == 1
    mx.clear_cache.assert_called_once_with()
    assert mlx_provider._CACHED_MODEL is model_b
    assert mlx_provider._CACHED_MODEL_ID == "org/model-b"


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (RuntimeError("download failed"), "download failed"),
        (RuntimeError("inference failed"), "inference failed"),
    ],
)
def test_model_loading_and_inference_failures_are_not_replaced(
    tmp_path,
    monkeypatch,
    failure,
    expected,
):
    if expected == "download failed":
        load_model = MagicMock(side_effect=failure)
        model = None
    else:
        model = MagicMock()
        model.generate.side_effect = failure
        load_model = MagicMock(return_value=model)

    mx = SimpleNamespace(concatenate=MagicMock(), clear_cache=MagicMock())
    monkeypatch.setattr(MLXAudioTTS, "get_status", lambda self: ToolStatus.AVAILABLE)
    monkeypatch.setattr(mlx_provider, "_load_runtime", lambda: (load_model, _write_wav, mx))

    output = tmp_path / "speech.wav"
    result = MLXAudioTTS().execute(
        {"text": "hello", "model_id": "org/model", "output_path": str(output)}
    )

    assert result.success is False
    assert expected in result.error
    assert "org/model" in result.error
    assert not output.exists()
    if model is not None:
        model.generate.assert_called_once_with(text="hello", stream=False)


def test_empty_audio_is_a_clear_failure(tmp_path, monkeypatch):
    model = _model()
    _install_mock_runtime(monkeypatch, [model])

    result = MLXAudioTTS().execute(
        {
            "text": "hello",
            "model_id": "org/model",
            "output_path": str(tmp_path / "speech.wav"),
        }
    )

    assert result.success is False
    assert "generated no audio" in result.error
    assert result.artifacts == []


def test_generation_result_must_declare_sample_rate(tmp_path, monkeypatch):
    model = MagicMock()
    model.sample_rate = 24000
    model.generate.return_value = [
        SimpleNamespace(audio=np.ones(1000, dtype=np.float32))
    ]
    _install_mock_runtime(monkeypatch, [model])

    result = MLXAudioTTS().execute(
        {
            "text": "hello",
            "model_id": "org/model",
            "output_path": str(tmp_path / "speech.wav"),
        }
    )

    assert result.success is False
    assert "no valid sample rate" in result.error
    assert not (tmp_path / "speech.wav").exists()


def test_probe_sample_rate_must_match_generation_result(tmp_path, monkeypatch):
    model = _model(np.ones(1000, dtype=np.float32), sample_rate=24000)
    _install_mock_runtime(
        monkeypatch,
        [model],
        probe_result=_probe_result(sample_rate=16000),
    )

    result = MLXAudioTTS().execute(
        {
            "text": "hello",
            "model_id": "org/model",
            "output_path": str(tmp_path / "speech.wav"),
        }
    )

    assert result.success is False
    assert "sample rate mismatch" in result.error
    assert "24000" in result.error
    assert "16000" in result.error
    assert not (tmp_path / "speech.wav").exists()


def test_audio_probe_failure_is_clear_and_does_not_publish_output(tmp_path, monkeypatch):
    model = _model(np.ones(1000, dtype=np.float32))
    _install_mock_runtime(
        monkeypatch,
        [model],
        probe_result=ToolResult(success=False, error="ffprobe not found on PATH"),
    )

    result = MLXAudioTTS().execute(
        {
            "text": "hello",
            "model_id": "org/model",
            "output_path": str(tmp_path / "speech.wav"),
        }
    )

    assert result.success is False
    assert "Generated WAV validation failed" in result.error
    assert "ffprobe not found on PATH" in result.error
    assert not (tmp_path / "speech.wav").exists()


def test_generation_is_serialized_across_threads(tmp_path, monkeypatch):
    active = 0
    max_active = 0
    active_lock = mlx_provider.threading.Lock()

    def generate(**kwargs):
        nonlocal active, max_active
        with active_lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.02)
        with active_lock:
            active -= 1
        return [SimpleNamespace(audio=np.ones(1000, dtype=np.float32), sample_rate=24000)]

    model = MagicMock()
    model.sample_rate = 24000
    model.generate.side_effect = generate
    _install_mock_runtime(monkeypatch, [model])
    tool = MLXAudioTTS()
    results: list[ToolResult] = []

    def execute(index: int):
        results.append(
            tool.execute(
                {
                    "text": f"speech {index}",
                    "model_id": "org/model",
                    "output_path": str(tmp_path / f"speech-{index}.wav"),
                }
            )
        )

    threads = [mlx_provider.threading.Thread(target=execute, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert all(result.success for result in results)
    assert max_active == 1


def test_selector_discovers_and_routes_only_to_mlx_audio(tmp_path, monkeypatch):
    model = _model(np.ones(1000, dtype=np.float32))
    load_model, _, _, _ = _install_mock_runtime(monkeypatch, [model])
    provider = MLXAudioTTS()
    selector = TTSSelector()
    registry = ToolRegistry()
    registry.register(provider)
    registry.register(selector)
    registry._discovered_packages.add("tools")
    monkeypatch.setattr("tools.tool_registry.registry", registry)

    discovered = selector._providers()
    assert discovered == [provider]

    result = selector.execute(
        {
            "text": "hello",
            "output_path": str(tmp_path / "speech.wav"),
            "preferred_provider": "mlx_audio",
            "allowed_providers": ["mlx_audio"],
            "project_dir": str(tmp_path),
            "sample_mode": False,
            "task_context": {"privacy_required": True},
            "voice_performance": {"tone": "warm"},
        }
    )

    assert result.success is True
    assert result.data["selected_tool"] == "mlx_audio_tts"
    assert result.data["selected_provider"] == "mlx_audio"
    assert result.data["alternatives_considered"] == []
    load_model.assert_called_once_with(mlx_provider.DEFAULT_MODEL_ID)
    model.generate.assert_called_once_with(
        text="hello",
        voice=mlx_provider.DEFAULT_VOICE_ID,
        stream=False,
    )
