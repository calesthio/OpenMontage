"""MiniMax chat-model provider (OpenAI-compatible interface).

Wraps the MiniMax /v1/chat/completions endpoint so that any part of
OpenMontage that needs a general-purpose LLM client can route to MiniMax
by setting ``llm.provider: minimax`` in *config.yaml*.

Models supported
----------------
* ``MiniMax-M2.7``            – Peak performance.  Ultimate value.
* ``MiniMax-M2.7-highspeed`` – Same capability, faster and more agile.

API reference
-------------
https://platform.minimax.io/docs/api-reference/text-openai-api

Environment variable
--------------------
``MINIMAX_API_KEY`` — obtain a key at https://platform.minimax.io/
"""

from __future__ import annotations

import os
from typing import Any

import requests

from lib.providers.base import BaseLLMProvider

_CHAT_ENDPOINT = "https://api.minimax.io/v1/chat/completions"

MINIMAX_MODELS = [
    "MiniMax-M2.7",
    "MiniMax-M2.7-highspeed",
]

_DEFAULT_MODEL = "MiniMax-M2.7"
_DEFAULT_TEMPERATURE = 1.0  # MiniMax range is (0.0, 1.0]; 0 is not accepted


class MiniMaxProvider(BaseLLMProvider):
    """MiniMax chat provider using the OpenAI-compatible API.

    Parameters
    ----------
    api_key:
        MiniMax API key.  Falls back to the ``MINIMAX_API_KEY`` environment
        variable when not supplied explicitly.
    base_url:
        Override the default endpoint root (useful for testing or proxies).
    """

    name = "minimax"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.minimax.io",
    ) -> None:
        self._api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self._base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """Return True if an API key is configured."""
        return bool(self._api_key)

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = _DEFAULT_MODEL,
        temperature: float = _DEFAULT_TEMPERATURE,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a chat completion request to MiniMax.

        Parameters
        ----------
        messages:
            Conversation history in OpenAI format
            (``[{"role": "user", "content": "..."}]``).
        model:
            One of :data:`MINIMAX_MODELS`.  Defaults to ``MiniMax-M2.7``.
        temperature:
            Sampling temperature in the range ``(0.0, 1.0]``.
            Values of 0 are not accepted by the MiniMax API.
        max_tokens:
            Maximum tokens in the completion.
        **kwargs:
            Additional fields forwarded verbatim to the API payload.

        Returns
        -------
        dict
            Raw response body from the MiniMax API (OpenAI-compatible shape).

        Raises
        ------
        EnvironmentError
            When no API key is configured.
        requests.HTTPError
            On non-2xx responses from the API.
        """
        if not self._api_key:
            raise EnvironmentError(
                "MINIMAX_API_KEY is not set. "
                "Get a key at https://platform.minimax.io/"
            )

        # Clamp temperature: MiniMax rejects 0; cap at 1.0
        temperature = max(0.01, min(float(temperature), 1.0))

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        response = requests.post(
            f"{self._base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    def get_info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "models": MINIMAX_MODELS,
            "default_model": _DEFAULT_MODEL,
            "base_url": self._base_url,
            "available": self.is_available,
        }
