"""Hosted director-model clients for OpenMontage stage execution."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import requests


class DirectorClientError(RuntimeError):
    """Raised when the hosted director LLM cannot produce a usable response."""


@dataclass(frozen=True)
class ChatCompletionsDirectorClient:
    """OpenAI-compatible chat-completions client.

    OpenRouter is preferred when `OPENROUTER_API_KEY` is present; otherwise this
    falls back to OpenAI. The executor owns checkpointing, repair loops, budget
    reserves, and schema validation; this class only performs the model call and
    parses JSON.
    """

    base_url: str
    api_key: str
    model: str
    app_title: str = "iKawn Ray"
    referer: str = "https://ikawn-ray.fly.dev"
    timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> "ChatCompletionsDirectorClient":
        if os.environ.get("OPENROUTER_API_KEY"):
            return cls(
                base_url="https://openrouter.ai/api/v1/chat/completions",
                api_key=os.environ["OPENROUTER_API_KEY"],
                model=os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
                referer=os.environ.get("RAY_PUBLIC_URL", "https://ikawn-ray.fly.dev"),
            )
        if os.environ.get("OPENAI_API_KEY"):
            return cls(
                base_url="https://api.openai.com/v1/chat/completions",
                api_key=os.environ["OPENAI_API_KEY"],
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            )
        raise DirectorClientError("No LLM key configured. Set OPENROUTER_API_KEY or OPENAI_API_KEY.")

    def step(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        request_messages = self._messages_with_contract(messages, tools)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter.ai" in self.base_url:
            headers["HTTP-Referer"] = self.referer
            headers["X-Title"] = self.app_title
        payload = {
            "model": self.model,
            "messages": request_messages,
            "temperature": 0.35,
            "response_format": {"type": "json_object"},
        }
        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise DirectorClientError(f"director LLM failed: {response.status_code} {response.text[:500]}")
        body = response.json()
        content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
        if not isinstance(content, str):
            raise DirectorClientError("director LLM response missing message content")
        data = self._parse_json(content)
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        data.setdefault("metadata", {})
        if isinstance(data["metadata"], dict):
            data["metadata"]["director_model"] = self.model
            data["metadata"]["director_usage"] = usage
        data["cost_usd"] = self._estimated_cost_from_usage(usage)
        return data

    @staticmethod
    def _messages_with_contract(
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        contract = {
            "role": "system",
            "content": (
                "Return only a JSON object. Preferred response shape: "
                '{"type":"final_artifact","artifact_name":"<canonical>",'
                '"artifact":{...},"supplementary_artifacts":{},'
                '"review":{"decision":"PASS","findings":[],"summary":"..."},'
                '"metadata":{...}}. '
                "For M1, do not request or call paid media generation tools. "
                "If live web_search is unavailable, mark research metadata as "
                "recorded_only_no_web_search_tool and do not claim live searches ran."
            ),
        }
        return [contract, *messages]

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start < 0 or end < start:
                raise DirectorClientError("director LLM response did not contain JSON")
            data = json.loads(content[start:end + 1])
        if not isinstance(data, dict):
            raise DirectorClientError("director LLM JSON response must be an object")
        return data

    @staticmethod
    def _estimated_cost_from_usage(usage: dict[str, Any]) -> float:
        prompt_tokens = float(usage.get("prompt_tokens") or 0.0)
        completion_tokens = float(usage.get("completion_tokens") or 0.0)
        if prompt_tokens <= 0 and completion_tokens <= 0:
            return 0.0
        # Low conservative default for OpenRouter/OpenAI mini-class planning.
        return round(((prompt_tokens + completion_tokens) / 1000.0) * 0.001, 6)
