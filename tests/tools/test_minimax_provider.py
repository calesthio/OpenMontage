"""Unit tests for the MiniMax LLM chat provider (lib/providers/minimax.py).

These tests do not require a MINIMAX_API_KEY or real network access.
All HTTP calls are mocked via unittest.mock.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.providers import MiniMaxProvider, build_provider
from lib.providers.minimax import (
    MINIMAX_MODELS,
    _CHAT_ENDPOINT,
    _DEFAULT_MODEL,
    _DEFAULT_TEMPERATURE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chat_response(content: str = "Hello!") -> MagicMock:
    """Return a mock requests.Response for a successful chat completion."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "id": "chatcmpl-test-id",
        "object": "chat.completion",
        "model": "MiniMax-M2.7",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    return mock_resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def provider() -> MiniMaxProvider:
    return MiniMaxProvider()


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure MINIMAX_API_KEY is unset by default."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

class TestAvailability:
    def test_unavailable_without_api_key(self, provider: MiniMaxProvider) -> None:
        assert not provider.is_available

    def test_available_with_env_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
        p = MiniMaxProvider()
        assert p.is_available

    def test_available_with_explicit_key(self) -> None:
        p = MiniMaxProvider(api_key="explicit-key")
        assert p.is_available


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_name_is_minimax(self, provider: MiniMaxProvider) -> None:
        assert provider.name == "minimax"

    def test_default_model_in_models_list(self) -> None:
        assert _DEFAULT_MODEL in MINIMAX_MODELS

    def test_models_list_contains_highspeed(self) -> None:
        assert "MiniMax-M2.7-highspeed" in MINIMAX_MODELS

    def test_default_temperature_is_one(self) -> None:
        assert _DEFAULT_TEMPERATURE == 1.0

    def test_endpoint_uses_correct_domain(self) -> None:
        assert "api.minimax.io" in _CHAT_ENDPOINT
        assert "api.minimax.chat" not in _CHAT_ENDPOINT

    def test_get_info_contains_models(self, provider: MiniMaxProvider) -> None:
        info = provider.get_info()
        assert info["name"] == "minimax"
        assert "MiniMax-M2.7" in info["models"]
        assert info["default_model"] == "MiniMax-M2.7"

    def test_base_url_is_international(self, provider: MiniMaxProvider) -> None:
        assert provider.get_info()["base_url"].startswith("https://api.minimax.io")


# ---------------------------------------------------------------------------
# chat() — no API key
# ---------------------------------------------------------------------------

class TestChatWithoutKey:
    def test_raises_environment_error(self, provider: MiniMaxProvider) -> None:
        with pytest.raises(EnvironmentError, match="MINIMAX_API_KEY"):
            provider.chat([{"role": "user", "content": "Hi"}])


# ---------------------------------------------------------------------------
# chat() — happy path (mocked HTTP)
# ---------------------------------------------------------------------------

class TestChatSuccess:
    @patch("lib.providers.minimax.requests")
    def test_returns_response_dict(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_requests.post.return_value = _make_chat_response("Greetings")
        p = MiniMaxProvider()

        result = p.chat([{"role": "user", "content": "Hello"}])

        assert result["choices"][0]["message"]["content"] == "Greetings"

    @patch("lib.providers.minimax.requests")
    def test_uses_correct_endpoint(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_requests.post.return_value = _make_chat_response()
        p = MiniMaxProvider()

        p.chat([{"role": "user", "content": "Hi"}])

        url = mock_requests.post.call_args[0][0]
        assert "api.minimax.io" in url
        assert url.endswith("/v1/chat/completions")

    @patch("lib.providers.minimax.requests")
    def test_sends_bearer_auth_header(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        api_key = "minimax-key-abc"
        monkeypatch.setenv("MINIMAX_API_KEY", api_key)
        mock_requests.post.return_value = _make_chat_response()
        p = MiniMaxProvider()

        p.chat([{"role": "user", "content": "Hi"}])

        headers = mock_requests.post.call_args[1]["headers"]
        assert headers["Authorization"] == f"Bearer {api_key}"

    @patch("lib.providers.minimax.requests")
    def test_default_model_in_payload(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_requests.post.return_value = _make_chat_response()
        p = MiniMaxProvider()

        p.chat([{"role": "user", "content": "Hi"}])

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["model"] == "MiniMax-M2.7"

    @patch("lib.providers.minimax.requests")
    def test_highspeed_model_forwarded(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_requests.post.return_value = _make_chat_response()
        p = MiniMaxProvider()

        p.chat([{"role": "user", "content": "Hi"}], model="MiniMax-M2.7-highspeed")

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["model"] == "MiniMax-M2.7-highspeed"

    @patch("lib.providers.minimax.requests")
    def test_messages_forwarded(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_requests.post.return_value = _make_chat_response()
        p = MiniMaxProvider()
        msgs = [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Hi"}]

        p.chat(msgs)

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["messages"] == msgs


# ---------------------------------------------------------------------------
# Temperature clamping
# ---------------------------------------------------------------------------

class TestTemperatureClamping:
    @patch("lib.providers.minimax.requests")
    def test_zero_is_clamped_above_zero(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """MiniMax does not accept temperature=0; it must be clamped."""
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_requests.post.return_value = _make_chat_response()
        p = MiniMaxProvider()

        p.chat([{"role": "user", "content": "Hi"}], temperature=0)

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["temperature"] > 0

    @patch("lib.providers.minimax.requests")
    def test_temperature_above_one_is_clamped(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_requests.post.return_value = _make_chat_response()
        p = MiniMaxProvider()

        p.chat([{"role": "user", "content": "Hi"}], temperature=2.0)

        payload = mock_requests.post.call_args[1]["json"]
        assert payload["temperature"] <= 1.0

    @patch("lib.providers.minimax.requests")
    def test_valid_temperature_preserved(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_requests.post.return_value = _make_chat_response()
        p = MiniMaxProvider()

        p.chat([{"role": "user", "content": "Hi"}], temperature=0.7)

        payload = mock_requests.post.call_args[1]["json"]
        assert abs(payload["temperature"] - 0.7) < 1e-9


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestChatErrors:
    @patch("lib.providers.minimax.requests")
    def test_http_error_propagates(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import requests as req_lib

        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req_lib.HTTPError("401 Unauthorized")
        mock_requests.post.return_value = mock_resp
        p = MiniMaxProvider()

        with pytest.raises(req_lib.HTTPError):
            p.chat([{"role": "user", "content": "Hi"}])

    @patch("lib.providers.minimax.requests")
    def test_network_exception_propagates(
        self,
        mock_requests: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-test")
        mock_requests.post.side_effect = ConnectionError("network down")
        p = MiniMaxProvider()

        with pytest.raises(ConnectionError):
            p.chat([{"role": "user", "content": "Hi"}])


# ---------------------------------------------------------------------------
# build_provider factory
# ---------------------------------------------------------------------------

class TestBuildProvider:
    def test_returns_minimax_provider(self) -> None:
        from lib.config_model import LLMConfig

        cfg = LLMConfig(provider="minimax")
        p = build_provider(cfg)
        assert isinstance(p, MiniMaxProvider)

    def test_unsupported_provider_raises(self) -> None:
        from lib.config_model import LLMConfig

        cfg = LLMConfig(provider="anthropic")
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            build_provider(cfg)

    def test_provider_name_is_case_insensitive(self) -> None:
        from lib.config_model import LLMConfig

        cfg = LLMConfig(provider="MiniMax")
        p = build_provider(cfg)
        assert isinstance(p, MiniMaxProvider)
