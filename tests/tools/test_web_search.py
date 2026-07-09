from __future__ import annotations

from tools.analysis.web_search import WebSearch
from tools.tool_registry import ToolRegistry


def test_registry_discovers_web_search_tool():
    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("web_search")
    assert tool is not None
    assert tool.capability == "research"
    assert "web_search" in tool.capabilities


def test_duckduckgo_html_parser_extracts_redirected_results(monkeypatch):
    html = """
    <html><body>
      <a rel="nofollow" class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Ffilm">Example Film</a>
      <a class="result__snippet">A useful cinematic reference.</a>
    </body></html>
    """

    class Response:
        text = html

        def raise_for_status(self) -> None:
            return None

    def fake_get(*args, **kwargs):
        return Response()

    monkeypatch.setattr("tools.analysis.web_search.requests.get", fake_get)

    results = WebSearch()._duckduckgo_html(
        query="example",
        max_results=5,
        region="us-en",
        safe_search="moderate",
    )

    assert results == [
        {
            "title": "Example Film",
            "url": "https://example.com/film",
            "snippet": "A useful cinematic reference.",
            "source": "duckduckgo",
        }
    ]
