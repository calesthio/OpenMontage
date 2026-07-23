from __future__ import annotations

from pathlib import Path

from tools.base_tool import ToolStatus
from tools.tool_registry import ToolRegistry
from tools.video.stock_sources import Candidate
from tools.video.corpus_builder import CorpusBuilder
from tools.video.direct_clip_search import DirectClipSearch
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


def test_video_compose_surfaces_all_three_runtimes():
    """Preflight must see remotion, hyperframes, and ffmpeg as separate engines."""
    import shutil

    info = VideoCompose().get_info()
    engines = info["render_engines"]
    assert set(engines.keys()) == {"remotion", "hyperframes", "ffmpeg"}
    assert engines["ffmpeg"] is bool(shutil.which("ffmpeg"))
    assert "hyperframes_note" in info
    assert "runtime_governance" in info


def test_video_compose_ffmpeg_engine_reflects_path_availability(monkeypatch):
    """Regression: `get_info()["render_engines"]["ffmpeg"]` must actually check
    shutil.which("ffmpeg"), not hardcode True. A machine without ffmpeg on PATH
    must not have the agent believe render_runtime='ffmpeg' is safe to lock."""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    info = VideoCompose().get_info()
    assert info["render_engines"]["ffmpeg"] is False

    monkeypatch.setattr(
        shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None
    )
    info = VideoCompose().get_info()
    assert info["render_engines"]["ffmpeg"] is True


def test_video_compose_blocks_silent_hyperframes_swap(tmp_path, monkeypatch):
    """Governance: if render_runtime='hyperframes' is locked but runtime
    is missing, the tool MUST return a structured blocker and NOT route to
    Remotion or FFmpeg."""
    monkeypatch.setattr(
        VideoCompose, "_hyperframes_available", lambda self: False, raising=True
    )
    result = VideoCompose().execute(
        {
            "operation": "render",
            "edit_decisions": {
                "version": "1.0",
                "renderer_family": "animation-first",
                "render_runtime": "hyperframes",
                "cuts": [
                    {"id": "c1", "source": "x", "in_seconds": 0, "out_seconds": 2}
                ],
            },
            "asset_manifest": {"assets": [{"id": "x", "path": "missing.png"}]},
            "output_path": str(tmp_path / "out.mp4"),
        }
    )
    assert not result.success
    err = (result.error or "").lower()
    assert "hyperframes" in err
    # Error MUST mention it's a blocker, not silently pick a different engine.
    assert ("blocker" in err) or ("not available" in err)


def test_video_compose_rejects_unknown_render_runtime(tmp_path):
    result = VideoCompose().execute(
        {
            "operation": "render",
            "edit_decisions": {
                "version": "1.0",
                "renderer_family": "explainer-data",
                "render_runtime": "bogus-runtime",
                "cuts": [
                    {"id": "c1", "source": "x", "in_seconds": 0, "out_seconds": 2}
                ],
            },
            "asset_manifest": {"assets": []},
            "output_path": str(tmp_path / "out.mp4"),
        }
    )
    assert not result.success
    assert "unknown render_runtime" in (result.error or "").lower()


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


def test_direct_clip_search_honors_overall_timeout(monkeypatch, tmp_path):
    """F-13 regression: direct clip search must stop on its own deadline and
    return partial progress instead of relying on an external PTY interrupt."""
    import tools.video.direct_clip_search as direct_clip_search
    import tools.video.stock_sources as stock_sources

    class SlowSource(_DummySource):
        def search(self, query: str, filters):
            return [
                Candidate(
                    source=self.name,
                    source_id="slow-1",
                    source_url="https://example.test/slow-1",
                    download_url="https://example.test/slow-1.mp4",
                    kind="video",
                )
            ]

        def download(self, candidate, out_path: Path):
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"0" * 2048)
            return out_path

    source = SlowSource("slow_source", True)
    monkeypatch.setattr(stock_sources, "all_sources", lambda: [source])
    monkeypatch.setattr(stock_sources, "available_sources", lambda: [source])
    monkeypatch.setattr(
        stock_sources,
        "source_summary",
        lambda: {
            "configured": 1,
            "total": 1,
            "available_source_names": ["slow_source"],
            "unavailable_source_names": [],
        },
    )

    ticks = iter([0.0, 2.0, 2.0, 2.0])
    monkeypatch.setattr(direct_clip_search.time, "time", lambda: next(ticks, 2.0))

    result = DirectClipSearch().execute(
        {
            "output_dir": str(tmp_path / "clips"),
            "queries": [{"query": "foggy harbor", "slot_id": "sc5"}],
            "timeout_seconds": 1,
            "extract_thumbnails": False,
        }
    )

    assert not result.success
    assert "timed out" in (result.error or "").lower()
    assert result.data["timed_out"] is True
    assert result.data["phase"] in {"query", "search", "download"}
    assert result.data["clips"] == []


def test_direct_clip_search_times_out_streaming_download(monkeypatch, tmp_path):
    """F-13 regression: a streaming adapter download must not run past the
    tool-level deadline just because bytes keep arriving."""
    import tools.video.direct_clip_search as direct_clip_search
    import tools.video.stock_sources as stock_sources
    import requests

    clock = {"now": 0.0}

    class StreamingResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=1024):
            clock["now"] = 2.0
            yield b"0" * 2048

    class StreamingSource(_DummySource):
        def search(self, query: str, filters):
            return [
                Candidate(
                    source=self.name,
                    source_id="stream-1",
                    source_url="https://example.test/stream-1",
                    download_url="https://example.test/stream-1.mp4",
                    kind="video",
                )
            ]

        def download(self, candidate, out_path: Path):
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with requests.get(candidate.download_url, stream=True, timeout=300) as response:
                response.raise_for_status()
                with out_path.open("wb") as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
            return out_path

    source = StreamingSource("streaming_source", True)
    monkeypatch.setattr(stock_sources, "all_sources", lambda: [source])
    monkeypatch.setattr(stock_sources, "available_sources", lambda: [source])
    monkeypatch.setattr(
        stock_sources,
        "source_summary",
        lambda: {
            "configured": 1,
            "total": 1,
            "available_source_names": ["streaming_source"],
            "unavailable_source_names": [],
        },
    )
    monkeypatch.setattr(direct_clip_search.time, "time", lambda: clock["now"])
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: StreamingResponse())

    result = DirectClipSearch().execute(
        {
            "output_dir": str(tmp_path / "clips"),
            "queries": [{"query": "foggy harbor", "slot_id": "sc5"}],
            "timeout_seconds": 1,
            "extract_thumbnails": False,
        }
    )

    assert not result.success
    assert result.data["timed_out"] is True
    assert result.data["phase"] == "download"
    assert result.data["clips"] == []


def test_direct_clip_search_reports_downloaded_clip_when_thumbnail_times_out(
    monkeypatch, tmp_path
):
    """F-13 regression: timeout data should include a clip that was already
    downloaded and validated before thumbnail extraction hit the deadline."""
    import tools.video.direct_clip_search as direct_clip_search
    import tools.video.stock_sources as stock_sources

    clock = {"now": 0.0}

    class SlowThumbnailSource(_DummySource):
        def search(self, query: str, filters):
            return [
                Candidate(
                    source=self.name,
                    source_id="thumb-1",
                    source_url="https://example.test/thumb-1",
                    download_url="https://example.test/thumb-1.mp4",
                    kind="video",
                )
            ]

        def download(self, candidate, out_path: Path):
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"0" * 2048)
            clock["now"] = 2.0
            return out_path

    source = SlowThumbnailSource("thumb_source", True)
    monkeypatch.setattr(stock_sources, "all_sources", lambda: [source])
    monkeypatch.setattr(stock_sources, "available_sources", lambda: [source])
    monkeypatch.setattr(
        stock_sources,
        "source_summary",
        lambda: {
            "configured": 1,
            "total": 1,
            "available_source_names": ["thumb_source"],
            "unavailable_source_names": [],
        },
    )
    monkeypatch.setattr(direct_clip_search.time, "time", lambda: clock["now"])

    result = DirectClipSearch().execute(
        {
            "output_dir": str(tmp_path / "clips"),
            "queries": [{"query": "foggy harbor", "slot_id": "sc5"}],
            "timeout_seconds": 1,
            "extract_thumbnails": True,
        }
    )

    assert not result.success
    assert result.data["timed_out"] is True
    assert result.data["phase"] == "thumbnail"
    assert result.data["clips_downloaded"] == 1
    assert result.data["total_clips"] == 1
    assert result.data["clips"][0]["clip_id"] == "thumb_source_thumb-1"
    assert result.data["clips"][0]["thumbnail"] == ""
