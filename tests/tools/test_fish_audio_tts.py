"""Unit tests for the fish.audio TTS provider (tools/audio/fish_audio_tts.py).

The real API is never called — requests.post is patched to return synthetic
audio bytes. Covers status gating, the required-model contract, the
voice_id -> reference_id alias, request shape, output writing, cost, and
API-key redaction on error.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tools.audio.fish_audio_tts import FishAudioTTS
from tools.base_tool import ToolStatus


class _FakeResponse:
    def __init__(self, content: bytes = b"ID3fake-audio", status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-fish-secret")
    return "sk-fish-secret"


@pytest.fixture
def no_api_key(monkeypatch):
    monkeypatch.delenv("FISH_AUDIO_API_KEY", raising=False)


# ----------------------------------------------------------------------
# Status gating
# ----------------------------------------------------------------------


class TestStatus:
    def test_unavailable_without_key(self, no_api_key):
        assert FishAudioTTS().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key(self, api_key):
        assert FishAudioTTS().get_status() == ToolStatus.AVAILABLE

    def test_execute_fails_without_key(self, no_api_key):
        result = FishAudioTTS().execute({"text": "hello", "model": "s1"})
        assert result.success is False
        assert "fish.audio API key" in result.error


# ----------------------------------------------------------------------
# Required-model contract
# ----------------------------------------------------------------------


class TestModelContract:
    def test_missing_model_errors_with_valid_values(self, api_key):
        result = FishAudioTTS().execute({"text": "hello"})
        assert result.success is False
        assert "requires an explicit 'model'" in result.error
        assert "s1" in result.error

    def test_unknown_model_errors(self, api_key):
        result = FishAudioTTS().execute({"text": "hello", "model": "gpt-voice"})
        assert result.success is False
        assert "Unknown fish.audio model" in result.error

    def test_retired_legacy_model_rejected(self, api_key):
        # speech-1.x / s1-mini are gone from the current fish.audio lineup.
        result = FishAudioTTS().execute({"text": "hello", "model": "speech-1.5"})
        assert result.success is False
        assert "Unknown fish.audio model" in result.error


# ----------------------------------------------------------------------
# Happy path
# ----------------------------------------------------------------------


class TestGenerate:
    def test_writes_audio_and_reports_metadata(self, api_key, tmp_path):
        out = tmp_path / "narration.mp3"
        with patch("requests.post", return_value=_FakeResponse(b"AUDIOBYTES")) as mock_post:
            result = FishAudioTTS().execute(
                {"text": "hello world", "model": "s1", "output_path": str(out)}
            )

        assert result.success is True
        assert out.read_bytes() == b"AUDIOBYTES"
        assert result.data["provider"] == "fish_audio"
        assert result.data["model"] == "s1"
        assert result.data["format"] == "mp3"
        assert str(out) in result.artifacts
        assert result.cost_usd > 0
        assert result.model == "fish-audio/s1"

        # model goes in the HTTP header, not the body
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["model"] == "s1"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-fish-secret"
        assert kwargs["json"]["text"] == "hello world"

    def test_s2_pro_model_sent_in_header(self, api_key, tmp_path):
        out = tmp_path / "s2.mp3"
        with patch("requests.post", return_value=_FakeResponse()) as mock_post:
            result = FishAudioTTS().execute(
                {"text": "hello", "model": "s2-pro", "output_path": str(out)}
            )

        assert result.success is True
        assert result.model == "fish-audio/s2-pro"
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["model"] == "s2-pro"

    def test_temperature_and_top_p_sent_in_body(self, api_key, tmp_path):
        out = tmp_path / "expressive.mp3"
        with patch("requests.post", return_value=_FakeResponse()) as mock_post:
            FishAudioTTS().execute(
                {
                    "text": "hello",
                    "model": "s2.1-pro",
                    "temperature": 0.9,
                    "top_p": 0.5,
                    "output_path": str(out),
                }
            )
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["temperature"] == 0.9
        assert kwargs["json"]["top_p"] == 0.5

    def test_voice_id_maps_to_reference_id(self, api_key, tmp_path):
        out = tmp_path / "clone.mp3"
        with patch("requests.post", return_value=_FakeResponse()) as mock_post:
            result = FishAudioTTS().execute(
                {
                    "text": "cloned voice",
                    "model": "s1",
                    "voice_id": "voice-abc123",
                    "output_path": str(out),
                }
            )

        assert result.success is True
        assert result.data["reference_id"] == "voice-abc123"
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["reference_id"] == "voice-abc123"

    def test_reference_id_takes_precedence_over_voice_id(self, api_key, tmp_path):
        out = tmp_path / "clone.mp3"
        with patch("requests.post", return_value=_FakeResponse()) as mock_post:
            FishAudioTTS().execute(
                {
                    "text": "x",
                    "model": "s1",
                    "reference_id": "primary",
                    "voice_id": "fallback",
                    "output_path": str(out),
                }
            )
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["reference_id"] == "primary"


# ----------------------------------------------------------------------
# Cost — byte-based, not char-based
# ----------------------------------------------------------------------


class TestCost:
    def test_cost_uses_utf8_bytes(self):
        tool = FishAudioTTS()
        # 3 CJK chars = 9 UTF-8 bytes, larger than a 3-char ASCII cost.
        cjk = tool.estimate_cost({"text": "你好吗", "model": "s1"})
        ascii_cost = tool.estimate_cost({"text": "abc", "model": "s1"})
        assert cjk > ascii_cost

    def test_s2_1_pro_free_costs_zero(self):
        tool = FishAudioTTS()
        assert tool.estimate_cost({"text": "same text here", "model": "s2.1-pro-free"}) == 0.0


# ----------------------------------------------------------------------
# Safety — never leak the API key
# ----------------------------------------------------------------------


class TestKeyRedaction:
    def test_error_does_not_leak_key(self, api_key):
        def _boom(*args, **kwargs):
            raise RuntimeError("upstream error for key sk-fish-secret at host")

        with patch("requests.post", side_effect=_boom):
            result = FishAudioTTS().execute({"text": "hello", "model": "s1"})

        assert result.success is False
        assert "sk-fish-secret" not in result.error
        assert "***" in result.error
