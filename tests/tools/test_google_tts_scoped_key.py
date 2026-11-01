from tools.audio.google_tts import GoogleTTS
from tools.google_credentials import has_google_credentials


def test_tts_only_key_does_not_enable_shared_google_providers(monkeypatch):
    monkeypatch.setenv("GOOGLE_TTS_API_KEY", "test-tts-only-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    assert GoogleTTS().get_status().value == "available"
    assert has_google_credentials() is False


def test_tts_key_uses_header_and_is_redacted_from_errors(monkeypatch, tmp_path):
    import requests

    secret = "test-production-shaped-tts-key"
    monkeypatch.setenv("GOOGLE_TTS_API_KEY", secret)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    def fail_request(url, **kwargs):
        assert kwargs["headers"]["x-goog-api-key"] == secret
        assert "params" not in kwargs
        raise requests.HTTPError(f"403 for {url}?key={secret}")

    monkeypatch.setattr(requests, "post", fail_request)
    result = GoogleTTS().execute(
        {"text": "safe test sentence", "output_path": str(tmp_path / "speech.mp3")}
    )

    assert result.success is False
    assert secret not in result.error
    assert "[REDACTED]" in result.error
