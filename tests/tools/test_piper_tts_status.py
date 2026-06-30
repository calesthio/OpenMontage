"""Tests for piper_tts status honesty (issue #237).

get_status() must not report AVAILABLE when no voice model is installed, and
execute() must give an actionable download hint in that state.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.piper_tts import PiperTTS
from tools.base_tool import ToolStatus


def _install_fake_voice(d: Path) -> None:
    (d / "en_US-lessac-medium.onnx").write_bytes(b"\x00")
    (d / "en_US-lessac-medium.onnx.json").write_text("{}")


def test_unavailable_when_not_installed(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    import builtins

    real_import = builtins.__import__

    def no_piper(name, *a, **k):
        if name == "piper":
            raise ImportError("no piper")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_piper)
    assert PiperTTS().get_status() == ToolStatus.UNAVAILABLE


def test_degraded_when_installed_without_voice(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/piper")  # "installed"
    monkeypatch.setattr(PiperTTS, "_voice_search_dirs", staticmethod(lambda: [tmp_path]))
    assert PiperTTS().get_status() == ToolStatus.DEGRADED


def test_available_when_voice_present(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/piper")
    _install_fake_voice(tmp_path)
    monkeypatch.setattr(PiperTTS, "_voice_search_dirs", staticmethod(lambda: [tmp_path]))
    assert PiperTTS().get_status() == ToolStatus.AVAILABLE


def test_execute_degraded_gives_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/piper")
    monkeypatch.setattr(PiperTTS, "_voice_search_dirs", staticmethod(lambda: [tmp_path]))
    r = PiperTTS().execute({"text": "hello", "output_path": str(tmp_path / "o.wav")})
    assert r.success is False
    assert "download_voices" in (r.error or "")
