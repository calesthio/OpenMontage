"""Credential precedence for google_tts when several are configured at once.

Cloud TTS takes either an OAuth token or an API key that belongs to a Cloud
project with Text-to-Speech enabled. Installs commonly hold both a shared
GOOGLE_API_KEY (driving Imagen, Veo and Gemini) and a service account, and
sometimes a TTS-scoped key on top, so which one wins has to be deliberate.
"""

import pytest
import requests

from tools.audio.google_tts import GoogleTTS

SCOPED = "test-scoped-tts-key"
SHARED = "test-shared-google-key"
SA_PATH = "/nonexistent/service-account.json"


@pytest.fixture
def clean_env(monkeypatch):
    for var in (
        "GOOGLE_TTS_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def _capture(monkeypatch):
    """Record the auth headers of the synthesize call, then stop it."""
    seen = {}

    def fake_post(url, **kwargs):
        seen["headers"] = kwargs.get("headers", {})
        raise requests.HTTPError("stopped before the network")

    monkeypatch.setattr(requests, "post", fake_post)
    return seen


def _run(tmp_path):
    return GoogleTTS().execute(
        {"text": "precedence probe", "output_path": str(tmp_path / "out.mp3")}
    )


def test_scoped_key_beats_service_account(clean_env, tmp_path, monkeypatch):
    """A TTS-only key is an explicit choice and must not be discarded."""
    clean_env.setenv("GOOGLE_TTS_API_KEY", SCOPED)
    clean_env.setenv("GOOGLE_APPLICATION_CREDENTIALS", SA_PATH)
    monkeypatch.setattr(
        "tools.audio.google_tts.service_account_configured", lambda: True
    )
    monkeypatch.setattr(
        "tools.audio.google_tts.get_access_token",
        lambda: pytest.fail("the scoped key should have been used instead"),
    )
    seen = _capture(monkeypatch)

    _run(tmp_path)

    assert seen["headers"]["x-goog-api-key"] == SCOPED
    assert "Authorization" not in seen["headers"]


def test_service_account_beats_shared_key(clean_env, tmp_path, monkeypatch):
    """The shared key is the weakest signal of intent, so OAuth wins."""
    clean_env.setenv("GOOGLE_API_KEY", SHARED)
    clean_env.setenv("GOOGLE_APPLICATION_CREDENTIALS", SA_PATH)
    monkeypatch.setattr(
        "tools.audio.google_tts.service_account_configured", lambda: True
    )
    monkeypatch.setattr(
        "tools.audio.google_tts.get_access_token", lambda: ("bearer-abc", None)
    )
    seen = _capture(monkeypatch)

    _run(tmp_path)

    assert seen["headers"]["Authorization"] == "Bearer bearer-abc"
    assert "x-goog-api-key" not in seen["headers"]


def test_shared_key_used_when_no_service_account(clean_env, tmp_path, monkeypatch):
    clean_env.setenv("GEMINI_API_KEY", SHARED)
    monkeypatch.setattr(
        "tools.audio.google_tts.service_account_configured", lambda: False
    )
    seen = _capture(monkeypatch)

    _run(tmp_path)

    assert seen["headers"]["x-goog-api-key"] == SHARED


def test_mint_failure_falls_back_to_shared_key(clean_env, tmp_path, monkeypatch):
    """A broken service account should not strand a usable key."""
    clean_env.setenv("GOOGLE_API_KEY", SHARED)
    clean_env.setenv("GOOGLE_APPLICATION_CREDENTIALS", SA_PATH)
    monkeypatch.setattr(
        "tools.audio.google_tts.service_account_configured", lambda: True
    )

    def boom():
        raise RuntimeError("could not mint a token")

    monkeypatch.setattr("tools.audio.google_tts.get_access_token", boom)
    seen = _capture(monkeypatch)

    _run(tmp_path)

    assert seen["headers"]["x-goog-api-key"] == SHARED


def test_mint_failure_without_any_key_surfaces_the_mint_error(
    clean_env, tmp_path, monkeypatch
):
    clean_env.setenv("GOOGLE_APPLICATION_CREDENTIALS", SA_PATH)
    monkeypatch.setattr(
        "tools.audio.google_tts.service_account_configured", lambda: True
    )

    def boom():
        raise RuntimeError("could not mint a token")

    monkeypatch.setattr("tools.audio.google_tts.get_access_token", boom)

    result = _run(tmp_path)

    assert result.success is False
    assert "could not mint a token" in result.error


def test_no_credentials_at_all_is_reported_clearly(clean_env, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tools.audio.google_tts.service_account_configured", lambda: False
    )

    result = _run(tmp_path)

    assert result.success is False
    assert "No Google credentials found" in result.error
