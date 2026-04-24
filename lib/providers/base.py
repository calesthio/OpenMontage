"""Abstract base class for LLM provider clients.

Each provider wraps an HTTP API and exposes a unified chat() interface
that mirrors the OpenAI chat completions contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """Minimal contract every LLM provider must satisfy."""

    #: Short machine-readable provider name (e.g. "minimax", "openai")
    name: str = ""

    @abstractmethod
    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Send a chat completion request and return the raw API response.

        Args:
            messages: List of role/content message dicts (OpenAI format).
            **kwargs: Extra parameters forwarded to the underlying API
                      (model, temperature, max_tokens, …).

        Returns:
            The raw response body as a Python dict.
        """

    def get_info(self) -> dict[str, Any]:
        """Return provider metadata."""
        return {"name": self.name}
