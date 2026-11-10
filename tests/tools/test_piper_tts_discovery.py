"""piper_tts must see the Piper that `make setup` installed, and its voices.

`make setup` puts the `piper` command into the project venv, and the documented
way to run tools is `.venv/bin/python` without activating that venv. PATH then
does not contain `piper`, and a voice model has to be downloaded separately.
These tests pin both: where the command is looked for, and which voice a call
uses.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.audio import piper_tts
from tools.audio.piper_tts import PiperTTS
from tools.base_tool import ToolStatus


def _install_voice(data_dir: Path, name: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / f"{name}.onnx").write_bytes(b"onnx")
    (data_dir / f"{name}.onnx.json").write_text("{}")


@pytest.fixture
def venv(tmp_path, monkeypatch):
    """An interpreter folder with a `piper` command that is not on PATH."""
    bin_dir = tmp_path / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "piper").write_text("#!/bin/sh\n")
    real_which = shutil.which
    monkeypatch.setattr(
        shutil, "which", lambda cmd, *a, **k: None if cmd == "piper" else real_which(cmd, *a, **k)
    )
    monkeypatch.setattr(sys, "executable", str(bin_dir / "python"))
    data_dir = tmp_path / "voices"
    monkeypatch.setenv("PIPER_DATA_DIR", str(data_dir))
    return bin_dir, data_dir


@pytest.fixture
def piper_runs(monkeypatch):
    """Record the piper command line instead of running it."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        Path(cmd[cmd.index("--output_file") + 1]).write_bytes(b"RIFF")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(piper_tts.subprocess, "run", fake_run)
    return calls


def _option(cmd: list[str], flag: str) -> str:
    return cmd[cmd.index(flag) + 1]


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------


def test_available_with_piper_next_to_the_interpreter_and_a_voice(venv):
    _, data_dir = venv
    _install_voice(data_dir, "en_US-ljspeech-high")
    assert PiperTTS().get_status() == ToolStatus.AVAILABLE


def test_degraded_when_piper_is_installed_but_no_voice_is(venv):
    assert PiperTTS().get_status() == ToolStatus.DEGRADED


def test_a_model_without_its_config_does_not_count_as_a_voice(venv):
    _, data_dir = venv
    data_dir.mkdir(parents=True)
    (data_dir / "half-download.onnx").write_bytes(b"onnx")
    assert PiperTTS().get_status() == ToolStatus.DEGRADED


def test_unavailable_without_the_command_even_when_a_voice_is_there(venv):
    bin_dir, data_dir = venv
    (bin_dir / "piper").unlink()
    _install_voice(data_dir, "en_US-ljspeech-high")
    assert PiperTTS().get_status() == ToolStatus.UNAVAILABLE


def test_info_lists_the_installed_voices_and_where_they_live(venv):
    _, data_dir = venv
    _install_voice(data_dir, "en_US-ljspeech-high")
    _install_voice(data_dir, "en_GB-alba-medium")
    info = PiperTTS().get_info()
    assert info["installed_voices"] == ["en_GB-alba-medium", "en_US-ljspeech-high"]
    assert info["data_dir"] == str(data_dir)


# ------------------------------------------------------------------
# execute(): command line and voice choice
# ------------------------------------------------------------------


def test_execute_runs_the_venv_piper_against_the_voice_folder(venv, piper_runs, tmp_path):
    bin_dir, data_dir = venv
    _install_voice(data_dir, "en_US-ljspeech-high")
    result = PiperTTS().execute({"text": "Hello.", "output_path": str(tmp_path / "o.wav")})
    assert result.success, result.error
    cmd = piper_runs[0]
    assert cmd[0] == str(bin_dir / "piper")
    assert _option(cmd, "--data-dir") == str(data_dir)


def test_execute_uses_the_installed_voice_when_the_default_is_not_installed(
    venv, piper_runs, tmp_path
):
    _, data_dir = venv
    _install_voice(data_dir, "en_US-ljspeech-high")
    result = PiperTTS().execute({"text": "Hello.", "output_path": str(tmp_path / "o.wav")})
    assert result.success, result.error
    assert _option(piper_runs[0], "--model") == "en_US-ljspeech-high"
    assert result.data["model"] == "en_US-ljspeech-high"
    assert result.model == "en_US-ljspeech-high"


def test_execute_prefers_the_documented_default_voice_when_it_is_installed(
    venv, piper_runs, tmp_path
):
    _, data_dir = venv
    _install_voice(data_dir, "en_GB-alba-medium")
    _install_voice(data_dir, "en_US-lessac-medium")
    PiperTTS().execute({"text": "Hello.", "output_path": str(tmp_path / "o.wav")})
    assert _option(piper_runs[0], "--model") == "en_US-lessac-medium"


def test_execute_honours_an_explicit_installed_voice(venv, piper_runs, tmp_path):
    _, data_dir = venv
    _install_voice(data_dir, "en_GB-alba-medium")
    _install_voice(data_dir, "en_US-lessac-medium")
    PiperTTS().execute(
        {"text": "Hello.", "model": "en_GB-alba-medium", "output_path": str(tmp_path / "o.wav")}
    )
    assert _option(piper_runs[0], "--model") == "en_GB-alba-medium"


def test_execute_accepts_a_path_to_a_model_file_outside_the_voice_folder(
    venv, piper_runs, tmp_path
):
    elsewhere = tmp_path / "elsewhere"
    _install_voice(elsewhere, "custom")
    model_path = elsewhere / "custom.onnx"
    result = PiperTTS().execute(
        {"text": "Hello.", "model": str(model_path), "output_path": str(tmp_path / "o.wav")}
    )
    assert result.success, result.error
    assert _option(piper_runs[0], "--model") == str(model_path)


def test_execute_names_the_download_command_when_the_voice_is_not_installed(
    venv, piper_runs, tmp_path
):
    _, data_dir = venv
    _install_voice(data_dir, "en_US-ljspeech-high")
    result = PiperTTS().execute(
        {"text": "Hello.", "model": "de_DE-thorsten-high", "output_path": str(tmp_path / "o.wav")}
    )
    assert result.success is False
    error = result.error or ""
    assert "de_DE-thorsten-high" in error
    assert "piper.download_voices" in error
    assert "en_US-ljspeech-high" in error, "says what is installed"
    assert piper_runs == []


def test_execute_without_any_voice_says_how_to_get_one(venv, piper_runs, tmp_path):
    result = PiperTTS().execute({"text": "Hello.", "output_path": str(tmp_path / "o.wav")})
    assert result.success is False
    assert "piper.download_voices" in (result.error or "")
    assert piper_runs == []
