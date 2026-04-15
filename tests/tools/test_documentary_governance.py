from __future__ import annotations

from pathlib import Path

from tools.base_tool import ToolStatus
from tools.tool_registry import ToolRegistry
from tools.video.corpus_builder import CorpusBuilder
from tools.video.video_compose import VideoCompose


class _DummySource:
    def __init__(self, name: str, available: bool) -> None:
        self.name = name
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def search(self, query: str, filters):  # pragma: no cover - protocol stub
        return []

    def download(self, candidate, out_path: Path):  # pragma: no cover - protocol stub
        return out_path


def test_corpus_builder_reports_source_level_discoverability(monkeypatch):
    import tools.video.stock_sources as stock_sources

    monkeypatch.setattr(
        stock_sources,
        "all_sources",
        lambda: [_DummySource("pexels", False), _DummySource("archive_org", True)],
    )
    monkeypatch.setattr(
        stock_sources,
        "available_sources",
        lambda: [_DummySource("archive_org", True)],
    )
    monkeypatch.setattr(
        stock_sources,
        "source_catalog",
        lambda: [
            {"name": "pexels", "status": "unavailable"},
            {"name": "archive_org", "status": "available"},
        ],
    )
    monkeypatch.setattr(
        stock_sources,
        "source_summary",
        lambda: {
            "configured": 1,
            "total": 2,
            "available_source_names": ["archive_org"],
            "unavailable_source_names": ["pexels"],
        },
    )

    tool = CorpusBuilder()
    assert tool.get_status() == ToolStatus.DEGRADED

    info = tool.get_info()
    assert info["source_provider_summary"]["configured"] == 1
    assert info["source_provider_summary"]["total"] == 2
    assert {entry["name"] for entry in info["source_provider_menu"]} == {
        "pexels",
        "archive_org",
    }


def test_corpus_builder_rejects_unavailable_pinned_sources(monkeypatch, tmp_path):
    import tools.video.stock_sources as stock_sources

    sources = {
        "pexels": _DummySource("pexels", False),
        "archive_org": _DummySource("archive_org", True),
    }

    monkeypatch.setattr(stock_sources, "all_sources", lambda: list(sources.values()))
    monkeypatch.setattr(
        stock_sources,
        "available_sources",
        lambda: [sources["archive_org"]],
    )
    monkeypatch.setattr(stock_sources, "get_source", lambda name: sources[name])
    monkeypatch.setattr(
        stock_sources,
        "source_summary",
        lambda: {
            "configured": 1,
            "total": 2,
            "available_source_names": ["archive_org"],
            "unavailable_source_names": ["pexels"],
        },
    )

    result = CorpusBuilder().execute({
        "corpus_dir": str(tmp_path / "corpus"),
        "queries": [{"query": "rain at night"}],
        "sources": ["pexels"],
    })

    assert not result.success
    assert "Requested stock sources are unavailable" in result.error
    assert "archive_org" in result.error


def test_documentary_renderer_family_maps_to_remotion():
    assert VideoCompose._get_composition_id("documentary-montage") == "CinematicRenderer"


def test_provider_menu_preserves_tool_discovery_metadata(monkeypatch):
    import tools.video.stock_sources as stock_sources

    monkeypatch.setattr(stock_sources, "all_sources", lambda: [_DummySource("archive_org", True)])
    monkeypatch.setattr(stock_sources, "available_sources", lambda: [_DummySource("archive_org", True)])
    monkeypatch.setattr(
        stock_sources,
        "source_catalog",
        lambda: [{"name": "archive_org", "status": "available"}],
    )
    monkeypatch.setattr(
        stock_sources,
        "source_summary",
        lambda: {
            "configured": 1,
            "total": 1,
            "available_source_names": ["archive_org"],
            "unavailable_source_names": [],
        },
    )

    registry = ToolRegistry()
    registry.register(CorpusBuilder())
    menu = registry.provider_menu()
    entry = menu["corpus_population"]["available"][0]

    assert entry["name"] == "corpus_builder"
    assert entry["source_provider_summary"]["configured"] == 1
    assert entry["source_provider_menu"][0]["name"] == "archive_org"
