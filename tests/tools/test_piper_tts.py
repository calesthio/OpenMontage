"""Piper on Windows: UTF-8 stdin and explicit-model routing through selectors."""

import subprocess
import sys
from pathlib import Path

import pytest

from tools.audio.piper_tts import PiperTTS
from tools.base_tool import DependencyError, ToolStatus
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


def test_find_piper_resolves_beside_sys_executable(monkeypatch, tmp_path):
    py_dir = tmp_path / "venv" / "bin"
    py_dir.mkdir(parents=True)
    piper_bin = py_dir / "piper"
    piper_bin.write_bytes(b"")
    piper_bin.chmod(0o755)

    monkeypatch.setattr(sys, "executable", str(py_dir / "python"))
    monkeypatch.setattr("shutil.which", lambda _name: None)

    assert PiperTTS._find_piper() == str(piper_bin)
    assert PiperTTS().get_status() == ToolStatus.AVAILABLE
    PiperTTS().check_dependencies()


def test_find_piper_falls_back_to_path(monkeypatch, tmp_path):
    empty_dir = tmp_path / "venv" / "bin"
    empty_dir.mkdir(parents=True)

    monkeypatch.setattr(sys, "executable", str(empty_dir / "python"))
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/piper" if name == "piper" else None)

    assert PiperTTS._find_piper() == "/usr/local/bin/piper"
    assert PiperTTS().get_status() == ToolStatus.AVAILABLE


def test_piper_unavailable_when_neither_present(monkeypatch, tmp_path):
    empty_dir = tmp_path / "venv" / "bin"
    empty_dir.mkdir(parents=True)

    monkeypatch.setattr(sys, "executable", str(empty_dir / "python"))
    monkeypatch.setattr("shutil.which", lambda _name: None)

    assert PiperTTS._find_piper() is None
    assert PiperTTS().get_status() == ToolStatus.UNAVAILABLE
    with pytest.raises(DependencyError):
        PiperTTS().check_dependencies()


def test_generate_invokes_resolved_piper(monkeypatch, tmp_path):
    py_dir = tmp_path / "venv" / "bin"
    py_dir.mkdir(parents=True)
    piper_bin = py_dir / "piper"
    piper_bin.write_bytes(b"")
    piper_bin.chmod(0o755)

    monkeypatch.setattr(sys, "executable", str(py_dir / "python"))
    monkeypatch.setattr("shutil.which", lambda _name: None)

    invoked_cmd = []

    def fake_run(cmd, **kwargs):
        invoked_cmd.extend(cmd)
        (tmp_path / "out.wav").write_bytes(b"RIFF")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = PiperTTS()._generate({"text": "Hello world", "output_path": str(tmp_path / "out.wav")})

    assert result.success
    assert invoked_cmd[0] == str(piper_bin)
