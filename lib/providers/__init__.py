"""LLM provider registry for OpenMontage.

Usage
-----
Import :func:`build_provider` to get a provider instance from a
:class:`~lib.config_model.LLMConfig`::

    from lib.config_model import OpenMontageConfig
    from lib.providers import build_provider

    config = OpenMontageConfig.load()
    provider = build_provider(config.llm)
    response = provider.chat([{"role": "user", "content": "Hello!"}])

Supported ``llm.provider`` values
----------------------------------
* ``minimax`` — MiniMax-M2.7 via OpenAI-compatible API

More providers can be registered here as the project grows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lib.providers.base import BaseLLMProvider
from lib.providers.minimax import MiniMaxProvider

if TYPE_CHECKING:
    from lib.config_model import LLMConfig

__all__ = [
    "BaseLLMProvider",
    "MiniMaxProvider",
    "build_provider",
]

_REGISTRY: dict[str, type[BaseLLMProvider]] = {
    "minimax": MiniMaxProvider,
}


def build_provider(llm_config: "LLMConfig") -> BaseLLMProvider:
    """Instantiate the LLM provider described by *llm_config*.

    Parameters
    ----------
    llm_config:
        The ``llm`` section of :class:`~lib.config_model.OpenMontageConfig`.

    Returns
    -------
    BaseLLMProvider
        A ready-to-use provider instance.

    Raises
    ------
    ValueError
        When ``llm_config.provider`` names an unsupported provider.
    """
    key = llm_config.provider.lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unsupported LLM provider {key!r}. "
            f"Supported values: {supported}. "
            "For other providers (anthropic, openai, gemini, …) use the "
            "native SDK of the coding assistant driving OpenMontage."
        )
    return cls()
