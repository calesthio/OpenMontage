"""Piper on Windows: UTF-8 stdin and explicit-model routing through selectors."""

import subprocess

from tools.audio.piper_tts import PiperTTS
from tools.provider_routing import filter_explicit_route


def test_explicit_local_voice_routes_to_piper(monkeypatch, tmp_path):
    (tmp_path / "es_ES-davefx-medium.onnx").write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    piper = PiperTTS()

    assert filter_explicit_route({"model": "es_ES-davefx-medium"}, [piper]) == [piper]
    assert filter_explicit_route({"model": "not-installed"}, [piper]) == []


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
