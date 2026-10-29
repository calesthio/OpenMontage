import sys
import types

import pytest

from tools.video.stock_sources import SearchFilters, all_sources, get_source
from tools.video.stock_sources.archive_org import _METADATA_URL
from tools.video.stock_sources.unsplash import _build_download_url, _orientation_for_unsplash
from tools.video.stock_sources.wikimedia import (
    _build_search_queries,
    _kind_from_mime,
    _meta_value,
)


def test_stock_source_autodiscovery_includes_new_sources():
    names = {source.name for source in all_sources()}
    assert "wikimedia" in names
    assert "unsplash" in names


def test_wikimedia_search_query_respects_kind():
    # The cascade's first ("full") query should always carry the
    # filetype filter for video/image kinds. "any" drops the prefix.
    video_cascade = _build_search_queries("rain city", "video")
    assert video_cascade[0][0] == "full"
    assert video_cascade[0][1].startswith("filetype:video")

    image_cascade = _build_search_queries("rain city", "image")
    assert image_cascade[0][0] == "full"
    assert image_cascade[0][1].startswith("filetype:image")

    any_cascade = _build_search_queries("rain city", "any")
    assert any_cascade[0][0] == "full"
    assert any_cascade[0][1] == "rain city"


def test_wikimedia_cascade_falls_back_on_multi_word():
    # Multi-word query should produce a 3-stage cascade: full, top2_or,
    # single_best. Tokens are picked by length, so "television" beats
    # "family" and "watching".
    cascade = _build_search_queries(
        "1950s family watching television", "video"
    )
    labels = [label for label, _ in cascade]
    assert labels == ["full", "top2_or", "single_best"]
    assert cascade[1][1] == "filetype:video television watching"
    assert cascade[2][1] == "filetype:video television"


def test_wikimedia_cascade_strips_source_hints_and_years():
    # "prelinger" is a source hint (redundant on Commons) and "1955" is
    # a year — both are excluded from distinctive-token picks.
    cascade = _build_search_queries(
        "Prelinger 1955 housewife kitchen", "video"
    )
    # Full query keeps the source hint + year (first attempt is strict).
    assert cascade[0][1] == "filetype:video Prelinger 1955 housewife kitchen"
    # Distinctive picks do NOT include prelinger or 1955.
    joined = " ".join(sq for _, sq in cascade[1:])
    assert "housewife" in joined
    assert "kitchen" in joined
    assert "prelinger" not in joined.lower()
    assert "1955" not in joined


def test_wikimedia_kind_and_metadata_helpers():
    assert _kind_from_mime("video/webm", "File:foo.webm") == "video"
    assert _kind_from_mime("image/jpeg", "File:foo.jpg") == "image"
    assert _meta_value({"Artist": {"value": "<a href='/wiki/User:Test'>Test User</a>"}}, "Artist") == "Test User"


def test_unsplash_helpers_preserve_query_params():
    assert _orientation_for_unsplash("square") == "squarish"
    url = _build_download_url("https://images.unsplash.com/photo-123?ixid=abc", 1920)
    assert "ixid=abc" in url
    assert "w=1920" in url
    assert "fm=jpg" in url


# ---------------------------------------------------------------------
# Transport-error contract (issue #511)
#
# `base.StockSource.search` states the rule: "Network errors should be
# raised — the corpus builder catches and logs per-source so one flaky
# API doesn't poison the whole run." An adapter that swallows the error
# and returns `[]` is indistinguishable from a source that genuinely has
# nothing to offer, so `direct_clip_search` reports `success: True,
# clips_downloaded: 0, errors: []` on a run where every request failed.
#
# The two tests below pin both halves of the contract across *every*
# registered adapter, so a new source cannot quietly reintroduce the bug.
# ---------------------------------------------------------------------

# Adapters that gate on a key before they reach the network. Without
# these the key-gated sources would return early and the test would
# assert nothing.
_SOURCE_CREDENTIALS = {
    "COVERR_API_KEY": "test-coverr",
    "NARA_API_KEY": "test-nara",
    "NASA_API_KEY": "test-nasa",
    "PEXELS_API_KEY": "test-pexels",
    "PIXABAY_API_KEY": "test-pixabay",
    "POND5_API_KEY": "test-pond5",
    "UNSPLASH_ACCESS_KEY": "test-unsplash",
    "VIDEVO_API_KEY": "test-videvo",
}


class TransportError(Exception):
    """Distinct failure type so the assertion cannot pass by accident."""


class _OkResponse:
    """A genuine 200 carrying `payload` (empty by default)."""

    status_code = 200
    content = b""

    def __init__(self, payload=None, text="<html><body></body></html>"):
        self._payload = payload if payload is not None else {}
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _EmptySoup:
    """Stand-in for `BeautifulSoup`: parses anything, finds nothing."""

    def __init__(self, *_args, **_kwargs):
        pass

    def select(self, *_args, **_kwargs):
        return []

    def select_one(self, *_args, **_kwargs):
        return None

    def find_all(self, *_args, **_kwargs):
        return []

    def find(self, *_args, **_kwargs):
        return None


def _install_fake_transport(monkeypatch, fake_get):
    """Point every adapter's lazy `import requests` at `fake_get`.

    `bs4` is stubbed alongside it: it is an optional dependency (the
    scraping adapters report `is_available() is False` without it), and
    they import it at the top of `search()`. Left alone, those adapters
    would fail on the import rather than on the request, and the test
    would pass for the wrong reason wherever bs4 is not installed.
    """
    requests_stub = types.ModuleType("requests")
    requests_stub.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", requests_stub)

    bs4_stub = types.ModuleType("bs4")
    bs4_stub.BeautifulSoup = _EmptySoup
    monkeypatch.setitem(sys.modules, "bs4", bs4_stub)

    for var, value in _SOURCE_CREDENTIALS.items():
        monkeypatch.setenv(var, value)


def _adapter_names():
    return [source.name for source in all_sources()]


@pytest.mark.parametrize("source_name", _adapter_names(), ids=_adapter_names())
def test_search_propagates_transport_errors(source_name, monkeypatch):
    def boom(*_args, **_kwargs):
        raise TransportError("simulated connection reset")

    _install_fake_transport(monkeypatch, boom)

    with pytest.raises(TransportError):
        get_source(source_name).search(
            "ocean waves", SearchFilters(kind="any", per_page=5)
        )


@pytest.mark.parametrize("source_name", _adapter_names(), ids=_adapter_names())
def test_search_returns_empty_when_the_source_has_no_results(
    source_name, monkeypatch
):
    # The other half of the contract: `[]` still has to mean "nothing
    # matched". A 200 with an empty payload must not raise.
    _install_fake_transport(monkeypatch, lambda *_a, **_k: _OkResponse())

    assert (
        get_source(source_name).search(
            "ocean waves", SearchFilters(kind="any", per_page=5)
        )
        == []
    )


# ---------------------------------------------------------------------
# Cascade and fallback semantics (issue #511, second half)
#
# `archive_org` and `wikimedia` walk a query cascade, and `pond5_pd`
# falls back from its API to a web scraper. All three are *designed* to
# absorb a failure and keep going, which is why they could not take the
# plain re-raise the other eight got. The rule they follow instead: a
# partial failure is fine, but returning `[]` means the source itself
# said "nothing" — so it requires having actually heard that.
# ---------------------------------------------------------------------

_ARCHIVE_DOC = {
    "identifier": "ocean-waves",
    "title": "Ocean waves",
    "description": "Waves breaking on a shore",
    "collection": "prelinger",
}

_ARCHIVE_METADATA = {
    "files": [
        {
            "format": "h.264",
            "name": "ocean-waves.mp4",
            "size": str(8 * 1024 * 1024),
            "length": "12.0",
            "width": "1920",
            "height": "1080",
        }
    ]
}

_WIKIMEDIA_PAGE = {
    "pageid": 42,
    "index": 1,
    "title": "File:Ocean waves.webm",
    "canonicalurl": "https://commons.wikimedia.org/wiki/File:Ocean_waves.webm",
    "imageinfo": [
        {
            "mime": "video/webm",
            "width": 1920,
            "height": 1080,
            "duration": 12.0,
            "url": "https://upload.wikimedia.org/ocean-waves.webm",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Ocean_waves.webm",
            "extmetadata": {},
        }
    ],
}


def test_archive_org_cascade_survives_one_failed_strategy(monkeypatch):
    # The cascade exists precisely so a weak strategy can be skipped.
    # A failed one must not become an error as long as a later strategy
    # gets an answer.
    searches = []

    def fake_get(url, **_kwargs):
        if url.startswith(_METADATA_URL):
            return _OkResponse(_ARCHIVE_METADATA)
        searches.append(url)
        if len(searches) == 1:
            raise TransportError("first strategy died")
        return _OkResponse({"response": {"docs": [_ARCHIVE_DOC]}})

    _install_fake_transport(monkeypatch, fake_get)

    out = get_source("archive_org").search(
        "ocean waves", SearchFilters(kind="video", per_page=5)
    )

    assert [c.source_id for c in out] == ["ocean-waves"]
    assert len(searches) == 2


def test_wikimedia_cascade_survives_one_failed_strategy(monkeypatch):
    calls = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise TransportError("first strategy died")
        return _OkResponse({"query": {"pages": {"42": _WIKIMEDIA_PAGE}}})

    _install_fake_transport(monkeypatch, fake_get)

    out = get_source("wikimedia").search(
        "ocean waves", SearchFilters(kind="video", per_page=5)
    )

    assert [c.source_id for c in out] == ["42"]
    assert len(calls) == 2


def test_archive_org_raises_when_every_item_fetch_fails(monkeypatch):
    # The search request lands, so the cascade knows the query matched
    # items — it just can't hydrate any of them. `[]` here would claim
    # Archive.org has nothing, which is the opposite of what happened.
    def fake_get(url, **_kwargs):
        if url.startswith(_METADATA_URL):
            raise TransportError("metadata endpoint down")
        return _OkResponse({"response": {"docs": [_ARCHIVE_DOC]}})

    _install_fake_transport(monkeypatch, fake_get)

    with pytest.raises(TransportError):
        get_source("archive_org").search(
            "ocean waves", SearchFilters(kind="video", per_page=5)
        )


def test_archive_org_returns_empty_when_no_item_has_a_usable_file(monkeypatch):
    # Every request lands and every item is inspected — the items just
    # hold nothing playable. That is a real answer, so it stays `[]`.
    def fake_get(url, **_kwargs):
        if url.startswith(_METADATA_URL):
            return _OkResponse({"files": [{"format": "JPEG", "name": "cover.jpg"}]})
        return _OkResponse({"response": {"docs": [_ARCHIVE_DOC]}})

    _install_fake_transport(monkeypatch, fake_get)

    assert (
        get_source("archive_org").search(
            "ocean waves", SearchFilters(kind="video", per_page=5)
        )
        == []
    )


def test_pond5_raises_when_the_web_fallback_cannot_run(monkeypatch):
    def boom(*_args, **_kwargs):
        raise TransportError("pond5 api down")

    _install_fake_transport(monkeypatch, boom)
    source = get_source("pond5_pd")

    # The fallback is still a stub, so it reports that it could not run
    # and the API's error is what the caller has to see.
    assert source._search_web_fallback("ocean waves", "video", SearchFilters()) is None
    with pytest.raises(TransportError):
        source.search("ocean waves", SearchFilters(kind="video", per_page=5))


def test_pond5_stays_quiet_when_the_web_fallback_can_run(monkeypatch):
    # The other half of "raise only when both paths fail": once the
    # fallback is implemented, an API outage it covers for is not an
    # error the caller needs to hear about.
    def boom(*_args, **_kwargs):
        raise TransportError("pond5 api down")

    _install_fake_transport(monkeypatch, boom)
    source = get_source("pond5_pd")
    monkeypatch.setattr(
        type(source), "_search_web_fallback", lambda *_a, **_k: []
    )

    assert source.search("ocean waves", SearchFilters(kind="video", per_page=5)) == []
