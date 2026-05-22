import base64
from pathlib import Path

from tools.audio.openai_audio_tts import OpenAIAudioTTS
from tools.audio.openai_tts import OpenAITTS
from tools.audio.piper_tts import PiperTTS
from tools.audio.tts_selector import TTSSelector


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_openai_audio_tts_posts_chat_audio_request(monkeypatch, tmp_path):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "audio": {
                                "data": base64.b64encode(b"fake wav bytes").decode("ascii"),
                                "transcript": "Read this exactly.",
                            }
                        }
                    }
                ]
            }
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("requests.post", fake_post)

    output_path = tmp_path / "sample.wav"
    result = OpenAIAudioTTS().execute(
        {
            "text": "Read this exactly.",
            "voice": "cedar",
            "format": "wav",
            "instructions": "Calm, confident product narration.",
            "output_path": str(output_path),
        }
    )

    assert result.success
    assert output_path.read_bytes() == b"fake wav bytes"
    assert result.data["provider"] == "openai_audio"
    assert result.data["model"] == "gpt-audio-1.5"
    assert result.data["voice"] == "cedar"
    assert result.data["transcript"] == "Read this exactly."
    assert result.data["instructions_applied"] is True
    assert result.data["strict_script"] is True
    assert result.data["timestamps"] is False

    request = calls[0]
    assert request["url"] == "https://api.openai.com/v1/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer test-key"
    assert request["json"]["model"] == "gpt-audio-1.5"
    assert request["json"]["modalities"] == ["text", "audio"]
    assert request["json"]["audio"] == {"voice": "cedar", "format": "wav"}
    assert request["json"]["messages"][1]["content"] == "Read this exactly."
    assert "verbatim" in request["json"]["messages"][0]["content"]
    assert "Calm, confident product narration." in request["json"]["messages"][0]["content"]


def test_openai_audio_tts_supports_pcm16_extension(monkeypatch, tmp_path):
    def fake_post(url, headers, json, timeout):
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "audio": {
                                "data": base64.b64encode(b"pcm bytes").decode("ascii")
                            }
                        }
                    }
                ]
            }
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("requests.post", fake_post)

    result = OpenAIAudioTTS().execute({"text": "Hello", "format": "pcm16", "output_path": str(tmp_path / "out.pcm")})

    assert result.success
    assert Path(result.data["output"]).suffix == ".pcm"


def test_tts_selector_rank_respects_openai_audio_allowed_provider(monkeypatch):
    monkeypatch.setattr(
        TTSSelector,
        "_providers",
        lambda self: [PiperTTS(), OpenAIAudioTTS()],
    )

    result = TTSSelector().execute(
        {
            "operation": "rank",
            "text": "Rank only OpenAI audio.",
            "allowed_providers": ["openai_audio"],
        }
    )

    assert result.success
    assert [item["provider"] for item in result.data["rankings"]] == ["openai_audio"]


def test_tts_selector_can_prefer_openai_audio_tool(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    selector = TTSSelector()
    candidates = [OpenAITTS(), OpenAIAudioTTS()]

    tool, score = selector._select_best_tool(
        {"preferred_tool": "openai_audio_tts", "text": "Read this."},
        candidates,
        selector._prepare_task_context({"text": "Read this."}),
    )

    assert tool.name == "openai_audio_tts"
    assert score is None


def test_tts_selector_routes_openai_to_audio_output_when_requested(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    selector = TTSSelector()
    candidates = [OpenAITTS(), OpenAIAudioTTS()]

    tool, _ = selector._select_best_tool(
        {
            "preferred_provider": "openai",
            "prefer_audio_output": True,
            "text": "Read this with delivery direction.",
        },
        candidates,
        selector._prepare_task_context({"text": "Read this with delivery direction."}),
    )

    assert tool.name == "openai_audio_tts"
