"""Regression tests: corpus_builder must not report success on a total failure.

Per-candidate errors are caught and collected so one flaky URL or broken codec
cannot poison a run — that tolerance is deliberate and still holds. But
`execute()` returned `success=True` unconditionally, so a run where every
candidate failed the same way reported success with `clips_added: 0` and wrote
a 0-row `index.jsonl`.

The realistic trigger is a broken CLIP stack: `transformers` is unpinned, and
`>=5.0` changed the `get_image_features` return type that `lib/clip_embedder.py`
depends on. Every candidate then fails identically, the tool exits 0, and the
empty corpus only surfaces later as a mystifying retrieval miss in
`clip_search`.

Systemic breakage is not per-candidate bad luck, so it must fail loudly at the
point it happens. See issue #357.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import tools.video.stock_sources as stock_sources  # noqa: E402
from tools.video.corpus_builder import CorpusBuilder  # noqa: E402


class _Candidate:
    def __init__(self, index: int) -> None:
        self.clip_id = f"fake_{index}"


class _Record:
    def __init__(self, clip_id: str) -> None:
        self.clip_id = clip_id


class _Source:
    """Stock source that yields `count` candidates for any query."""

    name = "fake"

    def __init__(self, count: int) -> None:
        self._count = count

    def is_available(self) -> bool:
        return True

    def search(self, query, filters):
        return [_Candidate(i) for i in range(self._count)]


@pytest.fixture
def build(monkeypatch, tmp_path):
    """Run CorpusBuilder against a fake source with a stubbed processor."""

    def _run(count, processor, **inputs):
        monkeypatch.setattr(stock_sources, "available_sources", lambda: [_Source(count)])
        monkeypatch.setattr(stock_sources, "source_summary", lambda: {})
        monkeypatch.setattr(CorpusBuilder, "_process_candidate", processor)
        payload = {
            "corpus_dir": str(tmp_path / inputs.pop("dirname", "corpus")),
            "queries": [{"query": "city at night"}],
            "max_new_clips": 50,
        }
        payload.update(inputs)
        return CorpusBuilder().execute(payload)

    return _run


def _clip_stack_broken(*args, **kwargs):
    # What transformers>=5 raises through lib/clip_embedder.py.
    raise AttributeError("'BaseModelOutput' object has no attribute 'norm'")


def _always_ok(self, cand, **kwargs):
    return _Record(cand.clip_id)


def _every_other_fails(self, cand, **kwargs):
    if int(cand.clip_id.split("_")[1]) % 2:
        raise ValueError("unsupported codec")
    return _Record(cand.clip_id)


def test_total_embedding_failure_is_not_success(build):
    result = build(705, _clip_stack_broken)

    assert result.success is False
    assert result.data["candidates_seen"] == 705
    assert result.data["clips_added"] == 0
    assert result.data["clips_failed"] == 705


def test_total_failure_error_names_the_likely_cause(build):
    result = build(12, _clip_stack_broken)

    assert "705" not in (result.error or "")
    assert "12" in result.error
    # The operator needs to know where to look, not just that it broke.
    assert "transformers" in result.error
    assert "empty" in result.error.lower()
    # And a sample of the underlying exception, not a bare count.
    assert "BaseModelOutput" in result.error


def test_total_failure_still_reports_diagnostics(build):
    result = build(4, _clip_stack_broken)

    # Failing must not cost the caller the payload it needs to debug.
    assert result.data["errors"]
    assert result.data["errors"][0]["phase"] == "process"
    assert "corpus_dir" in result.data


def test_partial_failure_remains_a_success(build):
    """One bad codec must not poison a run — the documented contract."""
    result = build(10, _every_other_fails)

    assert result.success is True
    assert result.data["clips_added"] == 5
    assert result.data["clips_failed"] == 5


def test_all_candidates_succeed(build):
    result = build(10, _always_ok)

    assert result.success is True
    assert result.data["clips_added"] == 10
    assert result.data["clips_failed"] == 0


def test_no_candidates_found_is_not_a_failure(build):
    """An empty search result is a legitimate outcome, not a broken run."""
    result = build(0, _always_ok)

    assert result.success is True
    assert result.data["candidates_seen"] == 0
    assert result.data["clips_added"] == 0


def test_single_candidate_failure_is_a_total_failure(build):
    # One candidate, one failure: nothing embedded, so the corpus is empty.
    result = build(1, _clip_stack_broken)

    assert result.success is False
