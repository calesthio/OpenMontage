from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import tools.video.stock_sources as stock_sources
from lib.corpus import Corpus
from tools.video.corpus_builder import (
    CorpusBuilder,
    _is_safe_clip_id,
    _safe_child_path,
)


@dataclass
class DummyCandidate:
    source: str
    source_id: str
    source_url: str = "https://example.com/item"
    download_url: str = "https://example.com/file.mp4"
    kind: str = "video"
    width: int = 1920
    height: int = 1080
    duration: float = 10.0
    creator: str = "author"
    license: str = "cc0"
    source_tags: str = "nature water"
    thumbnail_url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def clip_id(self) -> str:
        return f"{self.source}_{self.source_id}"


class DummyTraversingSource:
    name = "traversing_source"

    def __init__(self, candidates: list[DummyCandidate]) -> None:
        self.candidates = candidates
        self.download_called_with: list[Path] = []

    def is_available(self) -> bool:
        return True

    def search(self, query, filters):
        return self.candidates

    def download(self, candidate, out_path: Path) -> Path:
        self.download_called_with.append(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"dummy video content" * 100)
        return out_path


@pytest.mark.parametrize(
    "clip_id",
    [
        "../../traversal",
        "../../../etc/passwd",
        "..\\..\\windows_traversal",
        "clip/nested",
        "clip\\nested",
        "nested/../../escape",
        "C:drive_escape",
        "/absolute/root",
        "\\backslash_root",
        "\x00nullbyte",
        "bad\x1fcontrol",
        "",
        "   ",
        ".",
        "..",
        "...",
    ],
)
def test_is_safe_clip_id_rejects_malicious_and_traversal_ids(clip_id: str) -> None:
    assert _is_safe_clip_id(clip_id) is False


@pytest.mark.parametrize(
    "clip_id",
    [
        "pexels_12345",
        "archive_org_nasa_apollo",
        "pixabay_video_9876",
        "clip-0",
        "source_item-alpha.1",
        "wikimedia_Apollo_11_launch",
    ],
)
def test_is_safe_clip_id_accepts_valid_ids(clip_id: str) -> None:
    assert _is_safe_clip_id(clip_id) is True


def test_safe_child_path_confines_paths(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()

    # Valid relative paths
    valid = _safe_child_path(base, "clips/valid.mp4")
    assert valid is not None
    assert valid.is_relative_to(base)
    assert valid.name == "valid.mp4"

    # Escaping relative paths
    assert _safe_child_path(base, "clips/../../escape.mp4") is None
    assert _safe_child_path(base, "../escape.mp4") is None
    assert _safe_child_path(base, "..") is None
    assert _safe_child_path(base, ".") is None


def test_process_candidate_rejects_traversing_clip_id(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    corp = Corpus(corpus_dir)
    corp.ensure_dirs()

    builder = CorpusBuilder()
    cand = DummyCandidate(
        source="evil",
        source_id="../../escaped_clip",
    )
    src = DummyTraversingSource([cand])

    class DummyCache:
        def try_link(self, *args, **kwargs):
            return False

        def ingest(self, *args, **kwargs):
            return False

    with pytest.raises(ValueError, match="[Uu]nsafe clip_id"):
        builder._process_candidate(
            cand=cand,
            src=src,
            corp=corp,
            query="test",
            thumbs_per_video=3,
            cache=DummyCache(),
            run_cache_stats={"hits": 0, "misses": 0, "bytes_saved": 0},
        )

    # Ensure no file was created outside the corpus directory
    assert not (tmp_path / "escaped_clip.mp4").exists()
    assert not (tmp_path / "thumbnails" / "evil_../../escaped_clip").exists()
    assert len(src.download_called_with) == 0


def test_corpus_builder_execute_skips_and_records_unsafe_candidates(
    monkeypatch, tmp_path: Path
) -> None:
    corpus_dir = tmp_path / "corpus"
    escape_file = tmp_path / "escaped_clip.mp4"

    cand_bad = DummyCandidate(
        source="evil",
        source_id="../../escaped_clip",
    )
    cand_good = DummyCandidate(
        source="good",
        source_id="clip123",
    )

    source = DummyTraversingSource([cand_bad, cand_good])
    monkeypatch.setattr(stock_sources, "available_sources", lambda: [source])
    monkeypatch.setattr(stock_sources, "source_summary", lambda: {})

    # Mock _process_candidate for cand_good so we don't need real CLIP/opencv models
    orig_process = CorpusBuilder._process_candidate

    def mock_process_candidate(self, cand, *args, **kwargs):
        if not _is_safe_clip_id(cand.clip_id):
            return orig_process(self, cand, *args, **kwargs)
        from lib.corpus import ClipRecord
        return ClipRecord(
            clip_id=cand.clip_id,
            source=cand.source,
            source_id=cand.source_id,
            source_url=cand.source_url,
            local_path=f"clips/{cand.clip_id}.mp4",
            kind=cand.kind,
        )

    monkeypatch.setattr(CorpusBuilder, "_process_candidate", mock_process_candidate)

    result = CorpusBuilder().execute({
        "corpus_dir": str(corpus_dir),
        "queries": [{"query": "nature"}],
        "max_new_clips": 10,
    })

    assert result.success is True
    assert result.data["clips_added"] == 1
    assert result.data["clips_failed"] == 1
    assert result.data["added_ids"] == ["good_clip123"]
    assert not escape_file.exists()
