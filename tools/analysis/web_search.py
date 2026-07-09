"""No-key web search tool for hosted research stages.

This is intentionally small: it gives the hosted stage directors a real
registered ``web_search`` capability without introducing a paid search API key.
It uses DuckDuckGo's HTML endpoint first and Wikipedia OpenSearch only as a
fallback when no general results can be parsed.
"""

from __future__ import annotations

import html
import re
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


class _DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._active_link: dict[str, str] | None = None
        self._capture_snippet = False
        self._snippet_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        classes = set(attr.get("class", "").split())
        if tag == "a" and "result__a" in classes:
            self._active_link = {"title": "", "url": _clean_duckduckgo_url(attr.get("href", ""))}
            return
        if ("result__snippet" in classes or "result__snippet" in attr.get("class", "")) and self.results:
            self._capture_snippet = True
            self._snippet_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active_link is not None:
            title = _clean_text(self._active_link.get("title", ""))
            url = self._active_link.get("url", "")
            if title and url:
                self.results.append({"title": title, "url": url, "snippet": ""})
            self._active_link = None
            return
        if self._capture_snippet and tag in {"a", "div"}:
            snippet = _clean_text(" ".join(self._snippet_parts))
            if snippet and self.results and not self.results[-1].get("snippet"):
                self.results[-1]["snippet"] = snippet
            self._capture_snippet = False
            self._snippet_parts = []

    def handle_data(self, data: str) -> None:
        if self._active_link is not None:
            self._active_link["title"] = self._active_link.get("title", "") + data
        elif self._capture_snippet:
            self._snippet_parts.append(data)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _clean_duckduckgo_url(value: str) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    parsed = urlparse(value)
    if parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    if value.startswith("//duckduckgo.com/l/"):
        parsed = urlparse("https:" + value)
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return value


class WebSearch(BaseTool):
    name = "web_search"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "research"
    provider = "duckduckgo"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = ["python:requests"]
    install_instructions = "Install requests. No API key is required."
    agent_skills = []

    capabilities = ["web_search", "search_web", "research_source_discovery"]
    supports = {
        "no_api_key": True,
        "live_search": True,
        "safe_search": True,
        "result_limit": True,
    }
    best_for = [
        "research-stage source discovery",
        "finding public URLs for visual, audio, and subject references",
        "zero-cost hosted search when a paid search API is not configured",
    ]
    not_good_for = [
        "guaranteed exhaustive search coverage",
        "queries requiring authenticated or paid search indexes",
    ]

    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10},
            "region": {"type": "string", "default": "us-en"},
            "safe_search": {
                "type": "string",
                "enum": ["strict", "moderate", "off"],
                "default": "moderate",
            },
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "results": {"type": "array"},
            "result_count": {"type": "integer"},
            "source": {"type": "string"},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=10, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, backoff_seconds=1.0, retryable_errors=["timeout"])
    idempotency_key_fields = ["query", "max_results", "region", "safe_search"]
    side_effects = ["calls public web search endpoints"]
    user_visible_verification = ["Open cited URLs before relying on claims."]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        query = str(inputs.get("query") or "").strip()
        if not query:
            return ToolResult(success=False, error="query is required")
        max_results = max(1, min(10, int(inputs.get("max_results") or 5)))

        try:
            results = self._duckduckgo_html(
                query=query,
                max_results=max_results,
                region=str(inputs.get("region") or "us-en"),
                safe_search=str(inputs.get("safe_search") or "moderate"),
            )
            source = "duckduckgo_html"
            if not results:
                results = self._wikipedia_opensearch(query, max_results)
                source = "wikipedia_opensearch"
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": results[:max_results],
                    "result_count": len(results[:max_results]),
                    "source": source,
                },
                duration_seconds=time.time() - started,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"web_search failed: {exc}",
                duration_seconds=time.time() - started,
            )

    def _duckduckgo_html(
        self,
        *,
        query: str,
        max_results: int,
        region: str,
        safe_search: str,
    ) -> list[dict[str, str]]:
        params = {
            "q": query,
            "kl": region,
            "kp": {"strict": "1", "moderate": "-1", "off": "-2"}.get(safe_search, "-1"),
        }
        response = requests.get(
            "https://duckduckgo.com/html/",
            params=params,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                )
            },
            timeout=20,
        )
        response.raise_for_status()
        parser = _DuckDuckGoHTMLParser()
        parser.feed(response.text)
        deduped: list[dict[str, str]] = []
        seen: set[str] = set()
        for result in parser.results:
            url = result.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            deduped.append({**result, "source": "duckduckgo"})
            if len(deduped) >= max_results:
                break
        return deduped

    def _wikipedia_opensearch(self, query: str, max_results: int) -> list[dict[str, str]]:
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "opensearch",
                "search": query,
                "limit": max_results,
                "namespace": 0,
                "format": "json",
            },
            headers={"User-Agent": "OpenMontageBot/0.1"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        titles = data[1] if len(data) > 1 and isinstance(data[1], list) else []
        snippets = data[2] if len(data) > 2 and isinstance(data[2], list) else []
        urls = data[3] if len(data) > 3 and isinstance(data[3], list) else []
        results = []
        for title, snippet, url in zip(titles, snippets, urls):
            if title and url:
                results.append(
                    {
                        "title": str(title),
                        "url": str(url),
                        "snippet": _clean_text(str(snippet)),
                        "source": "wikipedia",
                    }
                )
        return results
