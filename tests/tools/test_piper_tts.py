"""Offline Piper discovery and launch regressions (no voice downloads)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.audio.piper_tts import PiperTTS
from tools.base_tool import ToolStatus


@pytest.fixture
def launchers(tmp_path, monkeypatch):
    scripts = tmp_path / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    monkeypatch.setattr(sys, "executable", str(scripts / "python.exe"))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    return scripts


def executable(directory):
    path = directory / ("piper.exe" if os.name == "nt" else "piper")
    path.write_bytes(b"test launcher")
    path.chmod(0o755)
    return path


def test_interpreter_adjacent_launcher_is_available(launchers):
    executable(launchers)
    assert PiperTTS().get_status() == ToolStatus.AVAILABLE


def test_adjacent_launcher_reaches_registry_and_selector(launchers, monkeypatch):
    from tools.tool_registry import ToolRegistry
    from tools.audio.tts_selector import TTSSelector

    executable(launchers)
    registry = ToolRegistry()
    registry.register(PiperTTS())
    monkeypatch.setattr(registry, "ensure_discovered", lambda: None)
    monkeypatch.setattr("tools.tool_registry.registry", registry)
    assert registry.provider_menu()["tts"]["configured"] == 1
    assert TTSSelector().get_status() == ToolStatus.AVAILABLE


@pytest.mark.parametrize("on_path", [False, True])
def test_launch_uses_discovered_executable(launchers, tmp_path, monkeypatch, on_path):
    sibling = executable(launchers)
    selected = sibling
    if on_path:
        path_dir = tmp_path / "path"
        path_dir.mkdir()
        selected = executable(path_dir)
        monkeypatch.setenv("PATH", str(path_dir))
    output = tmp_path / "audio.wav"

    def run(argv, **kwargs):
        assert Path(argv[0]) == selected
        assert argv[1:] == ["--model", "voice.onnx", "--speaker", "0",
                        "--length-scale", "1.0", "--sentence-silence", "0.3",
                        "--output_file", str(output)]
        assert kwargs == {"input": "Hello", "capture_output": True, "text": True,
                          "timeout": 300}
        output.write_bytes(b"audio")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    result = PiperTTS().execute({"text": "Hello", "model": "voice.onnx",
                                 "output_path": str(output)})
    assert result.success, result.error
    assert result.artifacts == [str(output)]


def test_missing_launcher_stays_unavailable(launchers):
    assert PiperTTS().get_status() == ToolStatus.UNAVAILABLE


def test_directory_is_not_a_launcher(launchers):
    (launchers / "piper").mkdir()
    (launchers / "piper.exe").mkdir()
    assert PiperTTS().get_status() == ToolStatus.UNAVAILABLE


def test_unrelated_working_directory_is_not_searched(launchers, tmp_path, monkeypatch):
    executable(tmp_path)
    monkeypatch.chdir(tmp_path)
    # Preserve the platform's existing PATH lookup rules, but disallow cwd there
    # on Windows so this specifically tests the new adjacent lookup boundary.
    monkeypatch.setenv("NoDefaultCurrentDirectoryInExePath", "1")
    assert PiperTTS().get_status() == ToolStatus.UNAVAILABLE


@pytest.mark.skipif(os.name != "nt", reason="Windows executable suffixes")
def test_non_launcher_suffix_is_unavailable(launchers):
    (launchers / "piper.txt").write_text("not executable")
    assert PiperTTS().get_status() == ToolStatus.UNAVAILABLE


@pytest.mark.skipif(os.name == "nt", reason="POSIX execute permissions")
def test_non_executable_launcher_is_unavailable(launchers):
    path = executable(launchers)
    path.chmod(0o644)
    assert PiperTTS().get_status() == ToolStatus.UNAVAILABLE


@pytest.mark.skipif(os.name == "nt", reason="POSIX venv interpreter symlinks")
def test_interpreter_symlink_keeps_venv_location(launchers, tmp_path, monkeypatch):
    base_python = tmp_path / "base-python"
    base_python.touch()
    interpreter = launchers / "python"
    interpreter.symlink_to(base_python)
    monkeypatch.setattr(sys, "executable", str(interpreter))
    executable(launchers)
    assert PiperTTS().get_status() == ToolStatus.AVAILABLE


@pytest.mark.parametrize("failure", ["exit", "missing", "timeout", "removed"])
def test_generation_failures_remain_failures(launchers, tmp_path, monkeypatch, failure):
    executable(launchers)

    def run(argv, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, 300)
        if failure == "removed":
            raise FileNotFoundError("launcher removed")
        return subprocess.CompletedProcess(argv, 2 if failure == "exit" else 0,
                                           "", "voice unavailable")

    monkeypatch.setattr(subprocess, "run", run)
    result = PiperTTS().execute({"text": "Hello", "output_path": str(tmp_path / "a.wav")})
    assert not result.success
    assert {"exit": "Piper failed (exit 2)", "missing": "Piper output file missing",
            "timeout": "Local TTS generation failed", "removed": "launcher removed"}[failure] in result.error
