"""Tests for the ACE-Step open-weight music tool (tools/audio/acestep_music.py).

Network-free: exercises availability gating, near-free cost, the input mapping,
and the worker-output extraction — none of which touch RunPod.
"""
from __future__ import annotations

import base64

import pytest

from tools.audio.acestep_music import AceStepMusic
from tools.base_tool import ToolStatus


@pytest.fixture
def tool():
    return AceStepMusic()


def test_unavailable_without_env(tool, monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.delenv("RUNPOD_ACESTEP_ENDPOINT_ID", raising=False)
    assert tool.get_status() == ToolStatus.UNAVAILABLE
    # Never breaks a flow — it fails cleanly with guidance instead of raising.
    result = tool.execute({"prompt": "anything"})
    assert result.success is False
    assert "not configured" in result.error.lower()


def test_available_with_env(tool, monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "k")
    monkeypatch.setenv("RUNPOD_ACESTEP_ENDPOINT_ID", "e")
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_cost_is_near_free(tool):
    # ~$0.05/30s is the paid-music baseline; ACE-Step must be far below it.
    assert tool.estimate_cost({"duration_seconds": 60}) < 0.01
    assert tool.estimate_cost({"duration_seconds": 300}) < 0.05


def test_build_input_instrumental_and_params(tool):
    payload = tool._build_input({"prompt": "lofi", "duration_seconds": 30, "bpm": 85, "key": "F Major"})
    assert payload["task"] == "text2music"
    assert payload["force_instrumental"] is True  # no lyrics => instrumental
    assert payload["bpm"] == 85
    assert payload["key"] == "F Major"
    assert payload["duration"] == 30


def test_build_input_with_lyrics_is_not_instrumental(tool):
    payload = tool._build_input({"prompt": "indie pop", "lyrics": "[Verse]\nhello"})
    assert payload["force_instrumental"] is False
    assert payload["lyrics"] == "[Verse]\nhello"


def test_extract_audio_base64_string(tool):
    raw = b"ID3fake-audio-bytes"
    assert tool._extract_audio(base64.b64encode(raw).decode()) == (raw, "mp3")


def test_extract_audio_dict_with_format(tool):
    raw = b"RIFFfake-wav"
    out = {"audio": base64.b64encode(raw).decode(), "format": "wav"}
    assert tool._extract_audio(out) == (raw, "wav")


def test_extract_audio_raises_on_unknown_shape(tool):
    with pytest.raises(RuntimeError):
        tool._extract_audio({"unexpected": "shape"})
