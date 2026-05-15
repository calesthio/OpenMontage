"""LLM provider routing for OpenMontage.

Supported providers and their OpenAI-compatible base URLs / env vars:

  anthropic       ANTHROPIC_API_KEY   (native SDK)
  openai          OPENAI_API_KEY      https://api.openai.com/v1
  gemini          GOOGLE_API_KEY      (native SDK)
  openrouter      OPENROUTER_API_KEY  https://openrouter.ai/api/v1
  ollama          (no key)            http://localhost:11434/v1
  mistral         MISTRAL_API_KEY     https://api.mistral.ai/v1
  minimax         MINIMAX_API_KEY     https://api.minimax.chat/v1
  astraflow       ASTRAFLOW_API_KEY   https://api-us-ca.umodelverse.ai/v1
  astraflow-cn    ASTRAFLOW_CN_API_KEY https://api.modelverse.cn/v1
"""

from __future__ import annotations

import os
from typing import Any, Optional


# Registry of OpenAI-compatible provider configurations.
# Each entry: (base_url, env_var_name)
OPENAI_COMPATIBLE_PROVIDERS: dict[str, tuple[str, str]] = {
    "openai":        ("https://api.openai.com/v1",              "OPENAI_API_KEY"),
    "openrouter":    ("https://openrouter.ai/api/v1",           "OPENROUTER_API_KEY"),
    "ollama":        ("http://localhost:11434/v1",               ""),
    "mistral":       ("https://api.mistral.ai/v1",              "MISTRAL_API_KEY"),
    "minimax":       ("https://api.minimax.chat/v1",            "MINIMAX_API_KEY"),
    "astraflow":     ("https://api-us-ca.umodelverse.ai/v1",    "ASTRAFLOW_API_KEY"),
    "astraflow-cn":  ("https://api.modelverse.cn/v1",           "ASTRAFLOW_CN_API_KEY"),
}


def get_provider_config(provider: str) -> dict[str, Any]:
    """Return base_url and api_key for the given provider name.

    For OpenAI-compatible providers, returns:
        {"base_url": str, "api_key": str}

    For native-SDK providers (anthropic, gemini), returns:
        {"api_key": str}

    Raises ValueError if the provider is unknown.
    Raises EnvironmentError if the required API key env var is not set.
    """
    provider = provider.lower().strip()

    if provider in OPENAI_COMPATIBLE_PROVIDERS:
        base_url, env_var = OPENAI_COMPATIBLE_PROVIDERS[provider]
        api_key: Optional[str] = None
        if env_var:
            api_key = os.environ.get(env_var)
            if not api_key:
                raise EnvironmentError(
                    f"Provider {provider!r} requires env var {env_var!r} to be set."
                )
        return {"base_url": base_url, "api_key": api_key or ""}

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "Provider 'anthropic' requires env var 'ANTHROPIC_API_KEY' to be set."
            )
        return {"api_key": api_key}

    if provider == "gemini":
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "Provider 'gemini' requires env var 'GOOGLE_API_KEY' to be set."
            )
        return {"api_key": api_key}

    raise ValueError(
        f"Unknown LLM provider: {provider!r}. "
        f"Supported: anthropic, gemini, "
        + ", ".join(OPENAI_COMPATIBLE_PROVIDERS)
    )


def is_openai_compatible(provider: str) -> bool:
    """Return True if the provider uses the OpenAI-compatible API."""
    return provider.lower().strip() in OPENAI_COMPATIBLE_PROVIDERS
