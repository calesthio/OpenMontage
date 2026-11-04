from dataclasses import dataclass

import pytest

import tools.video.stock_sources as stock_sources
from lib.corpus import Corpus
from tools.video.corpus_builder import CorpusBuilder


@dataclass
class _Candidate:
    clip_id: str


class _Source:
    name = "fake"

    def __init__(self, count: int) -> None:
        self.count = count

    def is_available(self) -> bool:
        return True

    def search(self, query, filters):
        return [_Candidate(f"clip-{index}") for index in range(self.count)]


@pytest.fixture
def run_builder(monkeypatch, tmp_path):
    def run(count: int, processor, existing: tuple[str, ...] = ()):
        monkeypatch.setattr(stock_sources, "available_sources", lambda: [_Source(count)])
        monkeypatch.setattr(stock_sources, "source_summary", lambda: {})
        monkeypatch.setattr(CorpusBuilder, "_process_candidate", processor)
        monkeypatch.setattr(Corpus, "has", lambda self, clip_id: clip_id in existing)
        return CorpusBuilder().execute({
            "corpus_dir": str(tmp_path / f"corpus-{count}"),
            "queries": [{"query": "city at night"}],
            "max_new_clips": 50,
        })

    return run


def test_all_candidate_failures_fail_closed_with_diagnostics(run_builder) -> None:
    def broken_clip_stack(*args, **kwargs):
        raise AttributeError("BaseModelOutput has no attribute norm")

    result = run_builder(4, broken_clip_stack)

    assert result.success is False
    assert result.data["candidates_seen"] == 4
    assert result.data["clips_failed"] == 4
    assert "corpus index is empty" in result.error
    assert "BaseModelOutput" in result.error


def test_total_failure_is_reported_even_when_some_clips_were_skipped(run_builder) -> None:
    """One already-present clip must not mask a total processing failure.

    `skipped` counts clips that were already in the corpus, so it says nothing
    about whether the candidates we actually processed succeeded. Exempting
    every run that contains a skip means a broken decoder or CLIP stack reports
    success as soon as a single prior clip happens to be present, which is the
    same silent-empty-index failure this guard exists to prevent.
    """

    def broken_clip_stack(*args, **kwargs):
        raise AttributeError("BaseModelOutput has no attribute norm")

    result = run_builder(5, broken_clip_stack, existing=("clip-0", "clip-1"))

    assert result.data["clips_skipped_existing"] == 2
    assert result.data["clips_failed"] == 3
    assert result.data["clips_added"] == 0
    assert result.success is False
    assert "2 already present" in result.error
    assert "BaseModelOutput" in result.error


def test_skip_only_run_stays_successful(run_builder) -> None:
    """Nothing processed means nothing failed, so the run is still valid."""

    def never_called(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("_process_candidate should not run for skipped clips")

    result = run_builder(3, never_called, existing=("clip-0", "clip-1", "clip-2"))

    assert result.success is True
    assert result.data["clips_skipped_existing"] == 3
    assert result.data["clips_failed"] == 0


def test_no_candidates_is_a_valid_empty_search(run_builder) -> None:
    result = run_builder(0, lambda *args, **kwargs: None)

    assert result.success is True
    assert result.data["candidates_seen"] == 0
