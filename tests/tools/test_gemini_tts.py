"""Tests for Gemini 3.1 Flash TTS hero voice (tools/audio/gemini_tts.py).

Network-free: key gating, the generateContent request body, PCM extraction from a
fake response, PCM→WAV wrapping, and that it's additive (ElevenLabs untouched).
"""
from __future__ import annotations

import base64
import wave

import pytest

from tools.audio.gemini_tts import GeminiTTS, _DEFAULT_MODEL, _DEFAULT_RATE
from tools.base_tool import ToolStatus


@pytest.fixture
def tool():
    return GeminiTTS()


def test_gated_on_google_key(tool, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert tool.get_status() == ToolStatus.UNAVAILABLE
    result = tool.execute({"text": "hi"})
    assert result.success is False and "unavailable" in result.error.lower()


def test_available_with_gemini_key(tool, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "k")  # either key works, mirroring Imagen
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_request_body_requests_audio_and_voice(tool):
    body = tool._build_request("hello world", "Puck", None)
    assert body["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert body["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Puck"
    assert body["contents"][0]["parts"][0]["text"] == "hello world"


def test_instructions_prefix_steers_delivery(tool):
    body = tool._build_request("the news today", "Kore", "Say dramatically")
    assert body["contents"][0]["parts"][0]["text"] == "Say dramatically: the news today"


def test_extract_pcm_reads_inline_data_and_rate(tool):
    raw = b"\x01\x02\x03\x04"
    resp = {"candidates": [{"content": {"parts": [
        {"inlineData": {"data": base64.b64encode(raw).decode(), "mimeType": "audio/L16;rate=16000"}}
    ]}}]}
    pcm, rate = tool._extract_pcm(resp)
    assert pcm == raw and rate == 16000


def test_extract_pcm_defaults_rate_and_raises_when_absent(tool):
    raw = b"\xaa\xbb"
    ok = {"candidates": [{"content": {"parts": [{"inlineData": {"data": base64.b64encode(raw).decode()}}]}}]}
    assert tool._extract_pcm(ok) == (raw, _DEFAULT_RATE)
    with pytest.raises(RuntimeError):
        tool._extract_pcm({"candidates": [{"content": {"parts": [{"text": "no audio"}]}}]})


def test_pcm_to_wav_roundtrip(tool, tmp_path):
    out = tmp_path / "v.wav"
    pcm = b"\x00\x00\xff\x7f\x00\x80"  # 3 samples: 0, +max, -max
    tool._pcm_to_wav(pcm, out, _DEFAULT_RATE)
    with wave.open(str(out), "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        assert w.getframerate() == _DEFAULT_RATE
        assert w.getnframes() == 3


def test_default_model_is_the_arena_winner(tool):
    assert _DEFAULT_MODEL == "gemini-3.1-flash-tts"


def test_additive_elevenlabs_untouched():
    from tools.audio.elevenlabs_tts import ElevenLabsTTS
    assert ElevenLabsTTS.provider == "elevenlabs"
    assert GeminiTTS.provider == "gemini"
    assert ElevenLabsTTS.capability == GeminiTTS.capability == "tts"
