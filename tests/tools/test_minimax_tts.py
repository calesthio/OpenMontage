"""Unit tests for the MiniMax TTS provider tool (tools/audio/minimax_tts.py).

These tests do not require a MINIMAX_API_KEY or network access.
All HTTP calls are mocked via unittest.mock.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.audio.minimax_tts import MINIMAX_VOICE_IDS, MiniMaxTTS, _TTS_ENDPOINT
from tools.base_tool import ToolStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tool() -> MiniMaxTTS:
    return MiniMaxTTS()


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure MINIMAX_API_KEY is unset by default; individual tests set it."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# Status / availability
# ---------------------------------------------------------------------------

class TestToolStatus:
    def test_unavailable_without_api_key(self, tool: MiniMaxTTS) -> None:
        assert tool.get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_api_key(
        self, tool: MiniMaxTTS, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        assert tool.get_status() == ToolStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Metadata checks
# ---------------------------------------------------------------------------

class TestToolMetadata:
    def test_capability_is_tts(self, tool: MiniMaxTTS) -> None:
        assert tool.capability == "tts"

    def test_provider_is_minimax(self, tool: MiniMaxTTS) -> None:
        assert tool.provider == "minimax"

    def test_default_model_is_hd(self, tool: MiniMaxTTS) -> None:
        schema_props = tool.input_schema["properties"]
        assert schema_props["model"]["default"] == "speech-2.8-hd"

    def test_voice_ids_are_non_empty(self) -> None:
        assert len(MINIMAX_VOICE_IDS) > 0
        for vid in MINIMAX_VOICE_IDS:
            assert isinstance(vid, str) and vid

    def test_endpoint_uses_correct_domain(self) -> None:
        assert "api.minimax.io" in _TTS_ENDPOINT
        assert "api.minimax.chat" not in _TTS_ENDPOINT


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

class TestCostEstimation:
    def test_cost_scales_with_text_length(self, tool: MiniMaxTTS) -> None:
        short_cost = tool.estimate_cost({"text": "Hi"})
        long_cost = tool.estimate_cost({"text": "Hi" * 1000})
        assert long_cost > short_cost

    def test_cost_is_non_negative(self, tool: MiniMaxTTS) -> None:
        assert tool.estimate_cost({"text": ""}) >= 0


# ---------------------------------------------------------------------------
# Execute — missing API key
# ---------------------------------------------------------------------------

class TestExecuteWithoutKey:
    def test_returns_failure_without_api_key(self, tool: MiniMaxTTS) -> None:
        result = tool.execute({"text": "Hello"})
        assert not result.success
        assert "MINIMAX_API_KEY" in result.error


# ---------------------------------------------------------------------------
# Execute — happy path (mocked HTTP)
# ---------------------------------------------------------------------------

def _make_api_response(hex_audio: str = "494433") -> MagicMock:
    """Return a mock requests.Response for the MiniMax TTS API."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": {"audio": hex_audio, "status": 2},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }
    return mock_resp


class TestExecuteSuccess:
    @patch("tools.audio.minimax_tts.requests")
    def test_writes_audio_file(
        self,
        mock_requests: MagicMock,
        tool: MiniMaxTTS,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_requests.post.return_value = _make_api_response("494433")

        output = tmp_path / "out.mp3"
        result = tool.execute({"text": "Hello world", "output_path": str(output)})

        assert result.success, result.error
        assert output.exists()
        assert output.read_bytes() == bytes.fromhex("494433")

    @patch("tools.audio.minimax_tts.requests")
    def test_uses_correct_endpoint(
        self,
        mock_requests: MagicMock,
        tool: MiniMaxTTS,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_requests.post.return_value = _make_api_response()

        tool.execute({"text": "Test", "output_path": str(tmp_path / "out.mp3")})

        call_args = mock_requests.post.call_args
        assert call_args[0][0] == _TTS_ENDPOINT

    @patch("tools.audio.minimax_tts.requests")
    def test_sends_bearer_auth_header(
        self,
        mock_requests: MagicMock,
        tool: MiniMaxTTS,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        api_key = "minimax-test-key-123"
        monkeypatch.setenv("MINIMAX_API_KEY", api_key)
        mock_requests.post.return_value = _make_api_response()

        tool.execute({"text": "Test", "output_path": str(tmp_path / "out.mp3")})

        headers = mock_requests.post.call_args[1]["headers"]
        assert headers["Authorization"] == f"Bearer {api_key}"

    @patch("tools.audio.minimax_tts.requests")
    def test_result_contains_provider_info(
        self,
        mock_requests: MagicMock,
        tool: MiniMaxTTS,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_requests.post.return_value = _make_api_response()

        result = tool.execute({"text": "Hello", "output_path": str(tmp_path / "out.mp3")})

        assert result.success
        assert result.data["provider"] == "minimax"
        assert result.data["model"] == "speech-2.8-hd"

    @patch("tools.audio.minimax_tts.requests")
    def test_default_voice_is_used_when_not_specified(
        self,
        mock_requests: MagicMock,
        tool: MiniMaxTTS,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_requests.post.return_value = _make_api_response()

        tool.execute({"text": "Hello", "output_path": str(tmp_path / "out.mp3")})

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["voice_setting"]["voice_id"] == "English_expressive_narrator"

    @patch("tools.audio.minimax_tts.requests")
    def test_custom_voice_and_model_forwarded(
        self,
        mock_requests: MagicMock,
        tool: MiniMaxTTS,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_requests.post.return_value = _make_api_response()

        tool.execute({
            "text": "Custom",
            "voice_id": "English_Lucky_Robot",
            "model": "speech-2.8-turbo",
            "output_path": str(tmp_path / "out.mp3"),
        })

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["voice_setting"]["voice_id"] == "English_Lucky_Robot"
        assert payload["model"] == "speech-2.8-turbo"


# ---------------------------------------------------------------------------
# Execute — API error handling
# ---------------------------------------------------------------------------

class TestExecuteErrors:
    @patch("tools.audio.minimax_tts.requests")
    def test_api_status_code_error(
        self,
        mock_requests: MagicMock,
        tool: MiniMaxTTS,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": {},
            "base_resp": {"status_code": 1004, "status_msg": "Auth failed"},
        }
        mock_requests.post.return_value = mock_resp

        result = tool.execute({"text": "Hello", "output_path": str(tmp_path / "out.mp3")})

        assert not result.success
        assert "1004" in result.error

    @patch("tools.audio.minimax_tts.requests")
    def test_empty_audio_response(
        self,
        mock_requests: MagicMock,
        tool: MiniMaxTTS,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": {"audio": ""},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }
        mock_requests.post.return_value = mock_resp

        result = tool.execute({"text": "Hello", "output_path": str(tmp_path / "out.mp3")})

        assert not result.success
        assert "empty" in result.error.lower()

    @patch("tools.audio.minimax_tts.requests")
    def test_network_exception_is_caught(
        self,
        mock_requests: MagicMock,
        tool: MiniMaxTTS,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        mock_requests.post.side_effect = ConnectionError("network down")

        result = tool.execute({"text": "Hello", "output_path": str(tmp_path / "out.mp3")})

        assert not result.success
        assert "MiniMax TTS failed" in result.error


# ---------------------------------------------------------------------------
# Hex decoding correctness
# ---------------------------------------------------------------------------

class TestHexDecoding:
    def test_hex_roundtrip(self) -> None:
        original = b"\x49\x44\x33\x00\x00"
        hex_str = original.hex()
        assert bytes.fromhex(hex_str) == original

    def test_non_base64_decode(self) -> None:
        """Verify we use hex, not base64."""
        import base64
        hex_data = "494433"
        hex_decoded = bytes.fromhex(hex_data)
        # base64 decoding of the same string yields different bytes
        b64_decoded = base64.b64decode(hex_data + "==")
        assert hex_decoded != b64_decoded
