"""Unit tests for the Audexum TTS provider (tools/audio/audexum_tts.py).

The real API is never called: requests.post is patched.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.audio.audexum_tts import AudexumTTS
from tools.base_tool import ToolStatus


def _ok(content: bytes = b"ID3fake-audio") -> MagicMock:
    resp = MagicMock()
    resp.content = content
    return resp


def test_status_follows_api_key(monkeypatch):
    monkeypatch.delenv("AUDEXUM_API_KEY", raising=False)
    assert AudexumTTS().get_status() == ToolStatus.UNAVAILABLE
    monkeypatch.setenv("AUDEXUM_API_KEY", "sk_live_x")
    assert AudexumTTS().get_status() == ToolStatus.AVAILABLE


def test_execute_without_key_fails(monkeypatch):
    monkeypatch.delenv("AUDEXUM_API_KEY", raising=False)
    result = AudexumTTS().execute({"text": "hello"})
    assert result.success is False
    assert "AUDEXUM_API_KEY" in result.error


def test_request_shape_and_output(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDEXUM_API_KEY", "sk_live_x")
    out = tmp_path / "a.mp3"
    with patch("requests.post", return_value=_ok(b"AUDIO")) as post:
        result = AudexumTTS().execute(
            {"text": "hello", "voice_id": "Atlas", "output_path": str(out)}
        )
    assert result.success is True
    assert out.read_bytes() == b"AUDIO"
    args, kwargs = post.call_args
    assert args[0] == "https://audexum.com/v1/text-to-speech/Atlas"
    assert kwargs["headers"]["xi-api-key"] == "sk_live_x"
    assert kwargs["json"]["text"] == "hello"


@pytest.mark.parametrize("text", ["", "   ", "x" * 5001])
def test_rejects_bad_text(monkeypatch, tmp_path, text):
    monkeypatch.setenv("AUDEXUM_API_KEY", "sk_live_x")
    result = AudexumTTS().execute({"text": text, "output_path": str(tmp_path / "a.mp3")})
    assert result.success is False


def test_http_error_is_reported(monkeypatch, tmp_path):
    monkeypatch.setenv("AUDEXUM_API_KEY", "sk_live_x")
    resp = _ok()
    resp.raise_for_status.side_effect = RuntimeError("HTTP 402")
    with patch("requests.post", return_value=resp):
        result = AudexumTTS().execute({"text": "hi", "output_path": str(tmp_path / "a.mp3")})
    assert result.success is False
    assert "402" in result.error
