"""Tests for Cartesia Sonic hero voice (tools/audio/cartesia_tts.py).

Network-free: key gating, the required-voice_id guard, the /tts/bytes request body,
cost, and that it's additive (ElevenLabs untouched).
"""
from __future__ import annotations

import pytest

from tools.audio.cartesia_tts import CartesiaTTS, _DEFAULT_MODEL, _SAMPLE_RATE
from tools.base_tool import ToolStatus


@pytest.fixture
def tool():
    return CartesiaTTS()


def test_gated_on_api_key(tool, monkeypatch):
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
    assert tool.get_status() == ToolStatus.UNAVAILABLE
    result = tool.execute({"text": "hi", "voice_id": "v"})
    assert result.success is False and "unavailable" in result.error.lower()


def test_available_with_key(tool, monkeypatch):
    monkeypatch.setenv("CARTESIA_API_KEY", "k")
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_voice_id_required(tool, monkeypatch):
    # Missing voice_id must fail loudly, not pick a wrong default that 500s at Cartesia.
    monkeypatch.setenv("CARTESIA_API_KEY", "k")
    result = tool.execute({"text": "hello"})
    assert result.success is False and "voice_id" in result.error.lower()


def test_request_body_shape(tool):
    body = tool._build_request("hello", "voice-123", _DEFAULT_MODEL, "en")
    assert body["model_id"] == _DEFAULT_MODEL
    assert body["transcript"] == "hello"
    assert body["voice"] == {"mode": "id", "id": "voice-123"}
    assert body["language"] == "en"
    # WAV container is requested so the response needs no PCM wrapping.
    assert body["output_format"]["container"] == "wav"
    assert body["output_format"]["sample_rate"] == _SAMPLE_RATE


def test_cost_scales_with_text(tool):
    short = tool.estimate_cost({"text": "hi"})
    long = tool.estimate_cost({"text": "hi" * 200})
    assert 0 < short < long


def test_additive_elevenlabs_untouched():
    from tools.audio.elevenlabs_tts import ElevenLabsTTS
    assert ElevenLabsTTS.provider == "elevenlabs"
    assert CartesiaTTS.provider == "cartesia"
    assert ElevenLabsTTS.capability == CartesiaTTS.capability == "tts"
