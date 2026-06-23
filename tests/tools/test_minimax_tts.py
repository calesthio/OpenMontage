import json
from pathlib import Path

import pytest

from tools.audio.tts_selector import TTSSelector
from tools.audio.minimax_tts import MiniMaxTTS
from tools.base_tool import ToolStatus


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200):
        self._payload = payload
        self.content = content
        self.status_code = status_code

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_status_requires_api_key(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    assert MiniMaxTTS().get_status() == ToolStatus.UNAVAILABLE

    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    assert MiniMaxTTS().get_status() == ToolStatus.AVAILABLE


def test_execute_decodes_hex_audio_and_writes_metadata(monkeypatch, tmp_path):
    post_calls = []

    def fake_post(url, headers, json, timeout):
        post_calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(
            {
                "data": {"audio": b"audio-bytes".hex(), "status": 2, "subtitle_file": "subtitle-id"},
                "extra_info": {
                    "audio_length": 1234,
                    "audio_sample_rate": 32000,
                    "usage_characters": 12,
                    "audio_format": "mp3",
                    "audio_channel": 1,
                },
                "trace_id": "trace-123",
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        )

    class FakeRequests:
        post = staticmethod(fake_post)

    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    output_path = tmp_path / "sample.mp3"
    result = MiniMaxTTS().execute(
        {
            "text": "hello minimax",
            "voice_id": "voice-1",
            "output_path": str(output_path),
            "model": "speech-2.8-hd",
        }
    )

    assert result.success
    assert output_path.read_bytes() == b"audio-bytes"
    metadata = json.loads(Path(result.data["metadata_path"]).read_text(encoding="utf-8"))
    assert metadata["trace_id"] == "trace-123"
    assert result.data["audio_duration_seconds"] == 1.23
    assert result.data["subtitle_file"] == "subtitle-id"
    assert result.cost_usd > 0

    request = post_calls[0]
    assert request["url"] == "https://api.minimax.io/v1/t2a_v2"
    assert request["headers"]["Authorization"] == "Bearer test-key"
    assert request["json"]["voice_setting"]["voice_id"] == "voice-1"
    assert request["json"]["subtitle_enable"] is True
    assert request["json"]["output_format"] == "hex"


def test_tts_selector_routes_preferred_provider_to_minimax(monkeypatch, tmp_path):
    def fake_post(url, headers, json, timeout):
        assert url == "https://api.minimax.io/v1/t2a_v2"
        return FakeResponse(
            {
                "data": {"audio": b"selector-audio".hex(), "status": 2},
                "extra_info": {"audio_length": 1500, "usage_characters": 14},
                "trace_id": "trace-selector",
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        )

    class FakeRequests:
        post = staticmethod(fake_post)

    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    output_path = tmp_path / "selector.mp3"
    result = TTSSelector().execute(
        {
            "preferred_provider": "minimax",
            "text": "hello selector",
            "voice_id": "Chinese (Mandarin)_Reliable_Executive",
            "output_path": str(output_path),
        }
    )

    assert result.success
    assert output_path.read_bytes() == b"selector-audio"
    assert result.data["selected_tool"] == "minimax_tts"
    assert result.data["selected_provider"] == "minimax"
    assert result.data["trace_id"] == "trace-selector"


def test_execute_downloads_url_audio(monkeypatch, tmp_path):
    def fake_post(url, headers, json, timeout):
        return FakeResponse(
            {
                "data": {"audio": "https://example.com/audio.mp3", "status": 2},
                "extra_info": {},
                "trace_id": "trace-url",
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        )

    def fake_get(url, timeout):
        assert url == "https://example.com/audio.mp3"
        return FakeResponse(content=b"url-audio")

    class FakeRequests:
        post = staticmethod(fake_post)
        get = staticmethod(fake_get)

    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    output_path = tmp_path / "url.mp3"
    result = MiniMaxTTS().execute(
        {
            "text": "hello",
            "voice_id": "voice-1",
            "output_path": str(output_path),
            "output_format": "url",
        }
    )

    assert result.success
    assert output_path.read_bytes() == b"url-audio"


def test_list_voices_calls_get_voice(monkeypatch):
    post_calls = []

    def fake_post(url, headers, json, timeout):
        post_calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(
            {
                "system_voice": [
                    {
                        "voice_id": "Chinese (Mandarin)_Reliable_Executive",
                        "voice_name": "Steady Executive",
                    }
                ],
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        )

    class FakeRequests:
        post = staticmethod(fake_post)

    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    payload = MiniMaxTTS().list_voices("system")

    assert payload["system_voice"][0]["voice_id"] == "Chinese (Mandarin)_Reliable_Executive"
    request = post_calls[0]
    assert request["url"] == "https://api.minimax.io/v1/get_voice"
    assert request["headers"]["Authorization"] == "Bearer test-key"
    assert request["json"] == {"voice_type": "system"}


def test_list_voices_rejects_unknown_voice_type(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    with pytest.raises(ValueError, match="voice_type"):
        MiniMaxTTS().list_voices("unknown")


def test_rejects_text_above_http_limit(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    result = MiniMaxTTS().execute({"text": "x" * 10001, "voice_id": "voice-1"})

    assert not result.success
    assert "10000 characters" in result.error


def test_minimax_error_redacts_api_key(monkeypatch):
    def fake_post(url, headers, json, timeout):
        return FakeResponse(
            {
                "data": None,
                "base_resp": {
                    "status_code": 1001,
                    "status_msg": "invalid api key test-secret",
                },
            },
            status_code=401,
        )

    class FakeRequests:
        post = staticmethod(fake_post)

    monkeypatch.setenv("MINIMAX_API_KEY", "test-secret")
    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    result = MiniMaxTTS().execute({"text": "hello", "voice_id": "voice-1"})

    assert not result.success
    assert "test-secret" not in result.error
    assert "[redacted]" in result.error


def test_request_body_omits_optional_payloads_by_default():
    body = MiniMaxTTS()._request_body(
        {"text": "hello"},
        voice_id="voice-1",
        model="speech-2.8-hd",
        output_format="hex",
    )

    assert body["stream"] is False
    assert body["language_boost"] == "auto"
    assert body["voice_setting"]["voice_id"] == "voice-1"
    assert "pronunciation_dict" not in body
    assert "voice_modify" not in body
