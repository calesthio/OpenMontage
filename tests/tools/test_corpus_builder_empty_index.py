import tools.video.stock_sources as stock_sources
from lib.corpus import Corpus
from tools.base_tool import ToolResult
from tools.video.corpus_builder import CorpusBuilder


class _FakeCandidate:
    def __init__(self, clip_id):
        self.clip_id = clip_id


class _FakeSource:
    name = "fake_source"

    def is_available(self):
        return True

    def search(self, query, filters):
        return [_FakeCandidate("clip-1"), _FakeCandidate("clip-2")]


def test_execute_fails_when_every_candidate_fails_to_embed(tmp_path, monkeypatch):
    # Mirrors the transformers>=5 CLIP break: every candidate raises at the
    # embed step, so the corpus is saved with zero new rows. That must be a
    # failure, not a success that hides an empty index from downstream retrieval.
    monkeypatch.setattr(stock_sources, "available_sources", lambda: [_FakeSource()])

    def _boom(self, **kwargs):
        raise RuntimeError("clip embed failed")

    monkeypatch.setattr(CorpusBuilder, "_process_candidate", _boom)

    result = CorpusBuilder().execute({
        "corpus_dir": str(tmp_path / "corpus"),
        "queries": [{"query": "city timelapse"}],
    })

    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error
    assert result.data["candidates_seen"] == 2
    assert result.data["clips_added"] == 0
    assert result.data["clips_failed"] == 2


def test_execute_succeeds_when_all_candidates_already_present(tmp_path, monkeypatch):
    # A run that only skips already-present clips (no failures) has nothing new
    # to add but is still a success — the failure floor must not trip on it.
    monkeypatch.setattr(stock_sources, "available_sources", lambda: [_FakeSource()])
    monkeypatch.setattr(Corpus, "has", lambda self, clip_id: True)

    result = CorpusBuilder().execute({
        "corpus_dir": str(tmp_path / "corpus"),
        "queries": [{"query": "city timelapse"}],
    })

    assert result.success is True
    assert result.error is None
    assert result.data["clips_added"] == 0
    assert result.data["clips_skipped_existing"] == 2
