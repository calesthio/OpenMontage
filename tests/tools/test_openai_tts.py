from tools.audio.openai_tts import OpenAITTS


class FakeResponse:
    def __init__(self, content=b"fake mp3"):
        self.content = content

    def raise_for_status(self):
        return None


def test_openai_tts_uses_current_voice_formats_and_instructions(monkeypatch, tmp_path):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("requests.post", fake_post)

    output_path = tmp_path / "speech.flac"
    result = OpenAITTS().execute(
        {
            "text": "Read this line.",
            "voice": "cedar",
            "model": "gpt-4o-mini-tts",
            "format": "flac",
            "instructions": "Confident but not dramatic.",
            "speed": 1.1,
            "output_path": str(output_path),
        }
    )

    assert result.success
    assert output_path.read_bytes() == b"fake mp3"
    request = calls[0]
    assert request["url"] == "https://api.openai.com/v1/audio/speech"
    assert request["headers"]["Authorization"] == "Bearer test-key"
    call = request["json"]
    assert call["model"] == "gpt-4o-mini-tts"
    assert call["voice"] == "cedar"
    assert call["response_format"] == "flac"
    assert call["instructions"] == "Confident but not dramatic."
    assert call["speed"] == 1.1
    assert result.data["voice"] == "cedar"
    assert result.data["instructions_applied"] is True
    assert result.data["timestamps"] is False


def test_openai_tts_skips_instructions_for_legacy_models(monkeypatch, tmp_path):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(json)
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("requests.post", fake_post)

    result = OpenAITTS().execute(
        {
            "text": "Read this line.",
            "voice": "nova",
            "model": "tts-1",
            "instructions": "This should not be sent.",
            "output_path": str(tmp_path / "speech.mp3"),
        }
    )

    assert result.success
    assert "instructions" not in calls[0]
    assert result.data["instructions_applied"] is False


def test_openai_tts_supports_custom_voice_id(monkeypatch, tmp_path):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(json)
        return FakeResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("requests.post", fake_post)

    result = OpenAITTS().execute(
        {
            "text": "Read this line.",
            "voice_id": "voice_1234",
            "output_path": str(tmp_path / "speech.mp3"),
        }
    )

    assert result.success
    assert calls[0]["voice"] == {"id": "voice_1234"}
    assert result.data["voice"] == "voice_1234"
