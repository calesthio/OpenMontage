"""Tests for the Kokoro local TTS tool (tools/audio/kokoro_tts.py).

Model-free: exercises availability gating, free cost, input validation, and the
stdlib WAV assembly — none of which load the kokoro model.
"""
from __future__ import annotations

import wave

import pytest

from tools.audio.kokoro_tts import KokoroTTS, _SAMPLE_RATE
from tools.base_tool import ToolStatus


@pytest.fixture
def tool():
    return KokoroTTS()


def test_status_gated_on_package(tool):
    # This env has no `kokoro` installed → UNAVAILABLE, and execute fails cleanly
    # rather than raising, so it never breaks a pipeline.
    assert tool.get_status() == ToolStatus.UNAVAILABLE
    result = tool.execute({"text": "hello"})
    assert result.success is False
    assert "not available" in result.error.lower()


def test_cost_is_free(tool):
    assert tool.estimate_cost({"text": "anything at all"}) == 0.0


def test_empty_text_rejected(tool, monkeypatch):
    # Force "available" so we reach the validation branch without a model.
    monkeypatch.setattr(tool, "get_status", lambda: ToolStatus.AVAILABLE)
    result = tool.execute({"text": "   "})
    assert result.success is False
    assert "text" in result.error.lower()


def test_write_wav_roundtrip(tool, tmp_path):
    out = tmp_path / "clip.wav"
    tool._write_wav([0.0, 1.0, -1.0, 0.5], out, _SAMPLE_RATE)
    assert out.exists()
    with wave.open(str(out), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == _SAMPLE_RATE
        assert w.getnframes() == 4


def test_write_wav_clamps_out_of_range(tool, tmp_path):
    out = tmp_path / "loud.wav"
    # Values beyond [-1, 1] must clamp to the 16-bit rails, not overflow.
    tool._write_wav([2.0, -2.0], out, _SAMPLE_RATE)
    with wave.open(str(out), "rb") as w:
        frames = w.readframes(w.getnframes())
    import struct
    left, right = struct.unpack("<2h", frames)
    assert left == 32767
    assert right == -32768
