"""Unit tests for the VieNeu-TTS provider (runner subprocess is mocked)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from tools.audio import vieneu_tts
from tools.audio.vieneu_tts import VieNeuTTS, split_lines
from tools.base_tool import ToolStatus


def test_split_lines_drops_blank_lines():
    assert split_lines("a\n\n  b  \n") == ["a", "b"]


def test_status_unavailable_without_interpreter(monkeypatch):
    monkeypatch.setenv("VIENEU_PYTHON", "Z:/nope/python.exe")
    monkeypatch.setattr(vieneu_tts, "_DEFAULT_PYTHON_CANDIDATES", [])
    assert VieNeuTTS().get_status() == ToolStatus.UNAVAILABLE


def test_execute_returns_segments(tmp_path, monkeypatch):
    fake_py = tmp_path / "python.exe"
    fake_py.write_text("")
    monkeypatch.setenv("VIENEU_PYTHON", str(fake_py))
    out = tmp_path / "out.wav"

    def fake_run(cmd, **kwargs):
        job = json.loads(kwargs["input"])
        assert job["lines"] == ["Câu một.", "Câu hai."]
        assert job["voice"] == "Thanh Bình"
        Path(job["output_path"]).write_bytes(b"RIFF")
        payload = {
            "output": job["output_path"], "sample_rate": 48000, "duration_seconds": 3.2,
            "voice": "Thanh Bình", "voices_available": ["Thanh Bình"],
            "segments": [{"text": "Câu một.", "start": 0, "end": 1.4},
                         {"text": "Câu hai.", "start": 1.8, "end": 3.2}],
        }
        return subprocess.CompletedProcess(cmd, 0, stdout="noise\n" + json.dumps(payload), stderr="")

    with patch.object(vieneu_tts, "_has_vieneu", return_value=True), patch.object(subprocess, "run", fake_run):
        result = VieNeuTTS().execute({"text": "Câu một.\n\nCâu hai.", "output_path": str(out)})

    assert result.success, result.error
    assert result.data["segments"][1]["start"] == 1.8
    assert result.artifacts == [str(out)]


def test_execute_surfaces_runner_error(tmp_path, monkeypatch):
    fake_py = tmp_path / "python.exe"
    fake_py.write_text("")
    monkeypatch.setenv("VIENEU_PYTHON", str(fake_py))

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 2, stdout=json.dumps({"error": "Unknown voice 'X'"}), stderr="")

    with patch.object(vieneu_tts, "_has_vieneu", return_value=True), patch.object(subprocess, "run", fake_run):
        result = VieNeuTTS().execute({"text": "xin chào", "voice": "X"})

    assert not result.success
    assert "Unknown voice" in result.error
