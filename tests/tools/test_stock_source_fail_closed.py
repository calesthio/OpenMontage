"""Stock source adapters must not report an empty search when the
transport layer failed.

Context: `corpus_builder` already fails closed with diagnostics when
every candidate fails (see test_corpus_builder_total_failure.py). The
fast path (`direct_clip_search` + the source adapters) did not have the
same guarantee: `ArchiveOrgSource.search` caught every exception in its
strategy cascade and returned `[]`, which is indistinguishable from
"archive.org genuinely has no footage for this query".

The visible consequence, reproduced against a real 503 from
archive.org, was `direct_clip_search` returning:

    success: True, clips_downloaded: 0, errors: []

A production run silently proceeds with zero footage and no signal.
"""

import pytest

from tools.video.stock_sources.archive_org import ArchiveOrgSource
from tools.video.stock_sources.base import SearchFilters


class _Response:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def patch_requests(monkeypatch):
    """Patch the lazily-imported requests.get used inside search()."""

    def apply(handler):
        import requests

        monkeypatch.setattr(requests, "get", handler)

    return apply


def test_transport_failure_on_every_strategy_fails_closed(patch_requests) -> None:
    def always_503(*args, **kwargs):
        return _Response(503)

    patch_requests(always_503)

    with pytest.raises(RuntimeError) as excinfo:
        ArchiveOrgSource().search("newspaper printing press", SearchFilters())

    message = str(excinfo.value)
    assert "archive_org" in message
    # The diagnostics must name the failing strategies, not just say
    # "something went wrong".
    assert "503" in message


def test_genuinely_empty_result_is_still_an_empty_list(patch_requests) -> None:
    """No transport failure, no hits: that is a valid empty search."""

    def empty_ok(*args, **kwargs):
        return _Response(200, {"response": {"docs": []}})

    patch_requests(empty_ok)

    assert ArchiveOrgSource().search("zzzz no such footage", SearchFilters()) == []


def test_one_failing_strategy_does_not_break_a_later_success(patch_requests) -> None:
    """The cascade must still degrade gracefully when a later strategy works."""

    calls = {"n": 0}

    def fail_then_succeed(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _Response(503)
        return _Response(200, {"response": {"docs": []}})

    patch_requests(fail_then_succeed)

    # Later strategies returned cleanly, so this is an empty search and
    # not a hard failure, even though the first strategy died.
    assert ArchiveOrgSource().search("city street", SearchFilters()) == []
