"""Piper on Windows: UTF-8 stdin and explicit-model routing through selectors."""

import subprocess
from pathlib import Path

import pytest

from tools.audio.piper_tts import PiperTTS
from tools.provider_routing import filter_explicit_route


@pytest.fixture
def voices(monkeypatch, tmp_path):
    """A voice in the cwd (piper's default data dir) and one stored elsewhere."""
    work, elsewhere = tmp_path / "work", tmp_path / "voices"
    work.mkdir()
    elsewhere.mkdir()
    (work / "es_ES-davefx-medium.onnx").write_bytes(b"")
    (elsewhere / "es_ES-sharvard-medium.onnx").write_bytes(b"")
    monkeypatch.chdir(work)
    return work, elsewhere


def test_installed_voice_name_routes_to_piper(voices):
    piper = PiperTTS()

    assert filter_explicit_route({"model": "es_ES-davefx-medium"}, [piper]) == [piper]
    # Unconfirmed names fall through to the generic policy (rejected when untargeted).
    assert filter_explicit_route({"model": "not-installed"}, [piper]) == []


@pytest.mark.parametrize(
    "model",
    [
        "es_ES-davefx-medium.onnx",  # relative path, cwd
        str(Path("..") / "voices" / "es_ES-sharvard-medium.onnx"),  # relative path, elsewhere
        "ABS_CWD",
        "ABS_ELSEWHERE",
    ],
)
def test_onnx_paths_route_to_piper(voices, model):
    work, elsewhere = voices
    model = {
        "ABS_CWD": str(work / "es_ES-davefx-medium.onnx"),
        "ABS_ELSEWHERE": str(elsewhere / "es_ES-sharvard-medium.onnx"),
    }.get(model, model)
    piper = PiperTTS()

    assert filter_explicit_route({"preferred_tool": "piper_tts", "model": model}, [piper]) == [piper]
    assert filter_explicit_route({"model": model}, [piper]) == [piper]


def test_text_is_sent_as_utf8(monkeypatch, tmp_path):
    calls = {}

    def fake_run(cmd, **kwargs):
        calls.update(kwargs)
        (tmp_path / "out.wav").write_bytes(b"RIFF")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = PiperTTS()._generate({"text": "Ananké, día", "output_path": str(tmp_path / "out.wav")})

    assert result.success
    assert calls["input"] == "Ananké, día"
    assert calls["encoding"] == "utf-8"
    assert calls["env"]["PYTHONIOENCODING"] == "utf-8"
