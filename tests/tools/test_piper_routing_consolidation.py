"""Piper's routing witness and CLI must agree on installed voice locations."""

import subprocess
from pathlib import Path

import pytest

from tools.audio.piper_tts import PiperTTS
from tools.provider_routing import filter_explicit_route


@pytest.fixture
def voice_home(monkeypatch, tmp_path):
    home = tmp_path / "home"
    directory = home / ".piper" / "models"
    directory.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return directory


def test_home_voice_is_confirmed_in_auto_mode(voice_home):
    model = "es_ES-davefx-medium"
    (voice_home / f"{model}.onnx").write_bytes(b"mock model")
    piper = PiperTTS()
    assert piper.vouches_for_model(model)
    assert filter_explicit_route({"model": model}, [piper]) == [piper]


def test_cli_and_witness_use_the_same_home_directory(monkeypatch, voice_home, tmp_path):
    model = "en_US-lessac-medium"
    (voice_home / f"{model}.onnx").write_bytes(b"mock model")
    output = tmp_path / "voice.wav"
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        output.write_bytes(b"RIFF")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    piper = PiperTTS()
    assert piper.vouches_for_model(model)
    result = piper._generate({"text": "día", "model": model, "output_path": str(output)})
    assert result.success
    command, kwargs = calls[0]
    assert command[command.index("--model") + 1] == model
    assert command[command.index("--data-dir") + 1] == str(voice_home)
    assert kwargs["encoding"] == "utf-8"


@pytest.mark.parametrize("field", ["model_id", "model_name"])
def test_witness_does_not_accept_a_field_piper_ignores(voice_home, field):
    model = voice_home / "known.onnx"
    model.write_bytes(b"mock model")
    piper = PiperTTS()
    assert filter_explicit_route({field: str(model), "preferred_tool": piper.name}, [piper]) == []


def test_unconfirmed_voice_requires_an_explicit_target(voice_home):
    piper = PiperTTS()
    assert not piper.vouches_for_model("not-installed")
    assert filter_explicit_route({"model": "not-installed"}, [piper]) == []
    assert filter_explicit_route(
        {"model": "not-installed", "preferred_provider": "piper"}, [piper]
    ) == [piper]


def test_home_voice_does_not_override_host_constraint(voice_home):
    (voice_home / "known.onnx").write_bytes(b"mock model")
    assert filter_explicit_route(
        {"model": "known", "hosting_provider": "other"}, [PiperTTS()]
    ) == []
