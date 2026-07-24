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


def _install_fake_voice(d: Path, name: str = "en_US-lessac-medium") -> None:
    (d / f"{name}.onnx").write_bytes(b"\x00")
    (d / f"{name}.onnx.json").write_text("{}")


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


def test_degraded_when_only_nondefault_voice_present(monkeypatch, tmp_path):
    # A non-default voice is installed, but the default en_US-lessac-medium is
    # not — preflight must not claim AVAILABLE since the default execute path
    # would fail.
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/piper")
    _install_fake_voice(tmp_path, name="en_GB-alba-medium")
    monkeypatch.setattr(PiperTTS, "_voice_search_dirs", staticmethod(lambda: [tmp_path]))
    assert PiperTTS().get_status() == ToolStatus.DEGRADED


def test_execute_degraded_gives_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/piper")
    monkeypatch.setattr(PiperTTS, "_voice_search_dirs", staticmethod(lambda: [tmp_path]))
    r = PiperTTS().execute({"text": "hello", "output_path": str(tmp_path / "o.wav")})
    assert r.success is False
    assert "download_voices" in (r.error or "")


def test_execute_passes_resolved_onnx_path_for_voice_outside_cwd(monkeypatch, tmp_path):
    # A voice installed in a search dir (not cwd) must be passed to piper as its
    # resolved .onnx path, otherwise piper looks only in cwd and fails to load
    # despite passing the availability gate.
    voice_dir = tmp_path / "voices"
    voice_dir.mkdir()
    _install_fake_voice(voice_dir)  # default voice, outside cwd
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/piper")
    monkeypatch.setattr(PiperTTS, "_voice_search_dirs", staticmethod(lambda: [voice_dir]))

    captured = {}

    class FakeProc:
        returncode = 0
        stderr = ""

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        Path(cmd[cmd.index("--output_file") + 1]).write_bytes(b"\x00")  # create output
        return FakeProc()

    monkeypatch.setattr("subprocess.run", fake_run)

    r = PiperTTS().execute({"text": "hi", "output_path": str(tmp_path / "o.wav")})
    assert r.success is True, r.error
    model_arg = captured["cmd"][captured["cmd"].index("--model") + 1]
    assert model_arg == str(voice_dir / "en_US-lessac-medium.onnx")


def test_execute_names_the_missing_requested_model(monkeypatch, tmp_path):
    # The default voice is present, but the caller requests a different, absent
    # model — the error must name the requested model, not the default.
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/piper")
    _install_fake_voice(tmp_path)  # default present
    monkeypatch.setattr(PiperTTS, "_voice_search_dirs", staticmethod(lambda: [tmp_path]))
    r = PiperTTS().execute(
        {"text": "hi", "model": "en_US-ryan-high", "output_path": str(tmp_path / "o.wav")}
    )
    assert r.success is False
    assert "en_US-ryan-high" in (r.error or "")


def test_find_voice_requires_companion_json_for_explicit_path(tmp_path):
    # A bare .onnx with no sibling .onnx.json must not resolve. Piper needs the
    # pair; returning the lone model passes preflight and then fails at synthesis.
    lonely = tmp_path / "custom.onnx"
    lonely.write_bytes(b"\x00")
    assert PiperTTS()._find_voice(str(lonely)) is None

    # Companion present -> the explicit path resolves.
    (tmp_path / "custom.onnx.json").write_text("{}")
    assert PiperTTS()._find_voice(str(lonely)) == lonely


def test_execute_rejects_explicit_onnx_without_companion(monkeypatch, tmp_path):
    # The full execute path must refuse a companion-less explicit model rather
    # than shelling out to piper with a model it cannot load.
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/piper")
    _install_fake_voice(tmp_path)  # default voice present, so the tool is AVAILABLE
    monkeypatch.setattr(PiperTTS, "_voice_search_dirs", staticmethod(lambda: [tmp_path]))

    lonely = tmp_path / "custom.onnx"  # explicit path, no .onnx.json
    lonely.write_bytes(b"\x00")

    def fail_if_called(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("piper was invoked with a companion-less model")

    monkeypatch.setattr("subprocess.run", fail_if_called)

    r = PiperTTS().execute(
        {"text": "hi", "model": str(lonely), "output_path": str(tmp_path / "o.wav")}
    )
    assert r.success is False
    assert str(lonely) in (r.error or "")
