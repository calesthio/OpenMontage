import sys
import types
from pathlib import Path

import pytest

from tools.video.stock_sources import SearchFilters, all_sources, get_source
from tools.video.stock_sources.base import Candidate
from tools.video.stock_sources.mixkit import _content_url_from_json_ld
from tools.video.stock_sources.pexels import PexelsSource


from tools.video.stock_sources.openverse import (
    _license_label,
    _matches_orientation,
    _result_to_candidate,
)


from tools.video.stock_sources.base import stable_url_id
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
    assert "openverse" in names


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


def test_pexels_search_sends_compatible_headers(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _EmptyOkResponse()

    _install_fake_transport(monkeypatch, fake_get)

    assert PexelsSource().search("rain", SearchFilters(kind="any")) == []
    assert [url for url, _ in calls] == [
        "https://api.pexels.com/v1/videos/search",
        "https://api.pexels.com/v1/search",
    ]
    for _, kwargs in calls:
        assert kwargs["headers"]["Authorization"] == "test-pexels"
        assert kwargs["headers"]["User-Agent"].startswith("Mozilla/5.0 ")


def test_pexels_download_sends_compatible_user_agent(monkeypatch, tmp_path):
    captured = {}

    class DownloadResponse(_EmptyOkResponse):
        def iter_content(self, chunk_size):
            assert chunk_size == 1 << 16
            yield b"video"

    def fake_get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return DownloadResponse()

    _install_fake_transport(monkeypatch, fake_get)
    candidate = Candidate(
        source="pexels",
        source_id="1",
        source_url="https://www.pexels.com/video/1",
        download_url="https://videos.pexels.com/video-files/1.mp4",
        kind="video",
    )
    output = tmp_path / "clip.mp4"

    assert PexelsSource().download(candidate, output) == output
    assert output.read_bytes() == b"video"
    assert captured["url"] == candidate.download_url
    assert captured["headers"]["User-Agent"].startswith("Mozilla/5.0 ")
    assert "Authorization" not in captured["headers"]


def test_openverse_is_image_only():
    # Openverse has no video endpoint; a video query must short-circuit
    # without touching the network.
    source = get_source("openverse")
    assert source.supports == {"video": False, "image": True}
    assert source.search("rain city", SearchFilters(kind="video", per_page=5)) == []


def test_openverse_maps_result_to_candidate():
    cand = _result_to_candidate(
        {
            "id": "b6829a2c",
            "title": "Illuminated London – The Rain City",
            "url": "https://live.staticflickr.com/5098/5584905187_b.jpg",
            "foreign_landing_url": "https://www.flickr.com/photos/x/5584905187",
            "width": 680,
            "height": 1024,
            "creator": "Sprengben",
            "license": "by-sa",
            "license_version": "2.0",
            "license_url": "https://creativecommons.org/licenses/by-sa/2.0/",
            "source": "flickr",
            "tags": [{"name": "rain"}, {"name": "london"}],
        },
        SearchFilters(kind="image"),
    )

    assert cand is not None
    assert cand.clip_id == "openverse_b6829a2c"
    assert cand.kind == "image"
    assert cand.width == 680 and cand.height == 1024
    assert cand.creator == "Sprengben"
    assert cand.license == "CC BY-SA 2.0"
    assert cand.source_url.startswith("https://www.flickr.com/")
    assert "rain" in cand.source_tags and "london" in cand.source_tags
    assert cand.extra["provider"] == "flickr"


def test_openverse_drops_results_without_a_file_url():
    assert _result_to_candidate({"id": "x"}, SearchFilters(kind="image")) is None


def test_openverse_respects_min_width_and_orientation():
    narrow = {"url": "https://x/y.jpg", "width": 320, "height": 200}
    assert (
        _result_to_candidate(narrow, SearchFilters(kind="image", min_width=1200))
        is None
    )
    landscape = {"url": "https://x/y.jpg", "width": 1920, "height": 1080}
    assert (
        _result_to_candidate(landscape, SearchFilters(kind="image", orientation="portrait"))
        is None
    )
    assert (
        _result_to_candidate(landscape, SearchFilters(kind="image", orientation="landscape"))
        is not None
    )


def test_openverse_license_labels():
    assert _license_label({"license": "cc0", "license_version": "1.0"}) == "CC0 1.0"
    assert _license_label({"license": "by-nc", "license_version": "4.0"}) == "CC BY-NC 4.0"
    assert _license_label({"license": "pdm"}) == "Public Domain Mark"
    assert _license_label({"license_url": "https://example.org/lic"}) == "https://example.org/lic"


def test_openverse_orientation_helper():
    assert _matches_orientation("landscape", 1920, 1080)
    assert _matches_orientation("portrait", 1080, 1920)
    assert _matches_orientation("square", 1000, 1000)
    assert not _matches_orientation("portrait", 1920, 1080)



def test_stable_url_id_is_deterministic_and_url_specific():
    url = "https://example.test/media/launch.mp4"

    assert stable_url_id(url) == "57d3145f3621a60c"
    assert stable_url_id(url) == stable_url_id(url)
    assert stable_url_id(url) != stable_url_id("https://example.test/media/landing.mp4")


@pytest.mark.parametrize("adapter", ["esa.py", "noaa.py", "loc.py"])
def test_url_backed_adapters_do_not_use_randomized_python_hash(adapter):
    source = (
        Path(__file__).parents[2]
        / "tools"
        / "video"
        / "stock_sources"
        / adapter
    ).read_text(encoding="utf-8")

    assert "stable_url_id(" in source
    assert "hash(" not in source


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

# Adapters that still swallow transport failures, recorded as known
# defects rather than encoded as expected behavior. `strict=True` means
# the suite fails the moment one of them is fixed and left in this map.
_STILL_SWALLOWS_TRANSPORT_ERRORS = {
}


class TransportError(Exception):
    """Distinct failure type so the assertion cannot pass by accident."""


class _EmptyOkResponse:
    """A genuine 200 that simply carries no results."""

    status_code = 200
    text = "<html><body></body></html>"
    content = b""

    def raise_for_status(self):
        return None

    def json(self):
        return {}

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _StatusErrorResponse:
    def raise_for_status(self):
        raise TransportError("simulated HTTP 503")


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


def _install_fake_transport(monkeypatch, fake_get, soup_cls=_EmptySoup):
    """Point every adapter's lazy `import requests` at `fake_get`.

    `bs4` is stubbed alongside it: it is an optional dependency (the
    scraping adapters report `is_available() is False` without it), and
    they import it at the top of `search()`. Left alone, those adapters
    would fail on the import rather than on the request, and the test
    would pass for the wrong reason wherever bs4 is not installed.

    `soup_cls` lets a test stand in a soup that actually answers a
    selector; the default finds nothing.
    """
    requests_stub = types.ModuleType("requests")
    requests_stub.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", requests_stub)

    bs4_stub = types.ModuleType("bs4")
    bs4_stub.BeautifulSoup = soup_cls
    monkeypatch.setitem(sys.modules, "bs4", bs4_stub)

    for var, value in _SOURCE_CREDENTIALS.items():
        monkeypatch.setenv(var, value)


def _adapter_names():
    return [source.name for source in all_sources()]


def test_pond5_availability_requires_credentials(monkeypatch):
    source = get_source("pond5_pd")

    monkeypatch.delenv("POND5_API_KEY", raising=False)
    assert source.is_available() is False

    monkeypatch.setenv("POND5_API_KEY", "test-pond5")
    assert source.is_available() is True


def test_pond5_search_sends_configured_credentials(monkeypatch):
    captured = {}

    def fake_get(*_args, **kwargs):
        captured.update(kwargs)
        return _EmptyOkResponse()

    _install_fake_transport(monkeypatch, fake_get)
    get_source("pond5_pd").search(
        "ocean waves", SearchFilters(kind="video", per_page=5)
    )

    assert captured["headers"]["Authorization"] == "Bearer test-pond5"


def test_pond5_search_propagates_status_errors(monkeypatch):
    _install_fake_transport(monkeypatch, lambda *_a, **_k: _StatusErrorResponse())

    with pytest.raises(TransportError, match="HTTP 503"):
        get_source("pond5_pd").search(
            "ocean waves", SearchFilters(kind="video", per_page=5)
        )


def _transport_error_params():
    params = []
    for name in _adapter_names():
        reason = _STILL_SWALLOWS_TRANSPORT_ERRORS.get(name)
        marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
        params.append(pytest.param(name, marks=marks, id=name))
    return params


@pytest.mark.parametrize("source_name", _transport_error_params())
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
    _install_fake_transport(monkeypatch, lambda *_a, **_k: _EmptyOkResponse())

    assert (
        get_source(source_name).search(
            "ocean waves", SearchFilters(kind="any", per_page=5)
        )
        == []
    )


# ---------------------------------------------------------------------
# Mixkit download-URL resolution (issue #572)
#
# `MixkitSource.download()` scraped the detail page for a download button,
# then for `video source[src]`. Mixkit puts `src` on the <video> tag
# itself, so neither matched and every download died on "Could not find
# download URL on Mixkit page" — while `search()` two hundred lines up was
# already matching both shapes.
#
# The page's own JSON-LD `VideoObject.contentUrl` names the file and does
# not move when the player markup does, so it is now read first; the DOM
# selectors stay as fallbacks. These tests pin the parser against the
# JSON-LD shapes pages actually ship, and pin the `video[src]` fallback so
# the selector cannot narrow again.
# ---------------------------------------------------------------------

_CONTENT_URL = "https://assets.mixkit.co/videos/preview/mixkit-rain-42-large.mp4"


def _ld_page(payload: str) -> str:
    return (
        "<html><head>"
        f'<script type="application/ld+json">{payload}</script>'
        "</head><body></body></html>"
    )


def test_mixkit_json_ld_reads_a_plain_video_object():
    html = _ld_page(
        '{"@context":"https://schema.org","@type":"VideoObject",'
        f'"name":"Rain on a city street","contentUrl":"{_CONTENT_URL}"}}'
    )
    assert _content_url_from_json_ld(html) == _CONTENT_URL


def test_mixkit_json_ld_reads_a_graph_wrapper():
    # Yoast-style wrapper: the VideoObject is nested under "@graph"
    html = _ld_page(
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"WebPage","name":"Free Stock Video"},'
        f'{{"@type":["VideoObject","MediaObject"],"contentUrl":"{_CONTENT_URL}"}}'
        "]}"
    )
    assert _content_url_from_json_ld(html) == _CONTENT_URL


def test_mixkit_json_ld_skips_malformed_and_non_video_blocks():
    # A half-templated block earlier in the page must not hide the real
    # one, and a BreadcrumbList must not be mistaken for the video
    html = (
        "<html><head>"
        '<script type="application/ld+json">{"@type":"VideoObject",</script>'
        '<script type="application/ld+json">'
        '{"@type":"BreadcrumbList","itemListElement":[]}</script>'
        '<script type="application/ld+json">'
        f'[{{"@type":"VideoObject","contentUrl":["{_CONTENT_URL}"]}}]</script>'
        "</head></html>"
    )
    assert _content_url_from_json_ld(html) == _CONTENT_URL


def test_mixkit_json_ld_returns_empty_when_no_video_is_declared():
    assert _content_url_from_json_ld("<html><body>no metadata</body></html>") == ""
    assert (
        _content_url_from_json_ld(_ld_page('{"@type":"VideoObject","name":"no url"}'))
        == ""
    )


class _HtmlResponse:
    """A 200 carrying a specific page body."""

    status_code = 200

    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class _VideoTagSoup(_EmptySoup):
    """Soup for a page whose `src` sits on the <video> tag itself.

    Answers only a selector that actually asks for `video[src]`, which is
    the markup Mixkit ships today. A `video source[src]`-only selector
    gets nothing back — that is the #572 regression this pins.
    """

    def select(self, selector, *_args, **_kwargs):
        if "video[src]" not in selector:
            return []
        return [_SrcTag(_CONTENT_URL)]


class _SrcTag:
    def __init__(self, src):
        self._src = src

    def get(self, name, default=""):
        return self._src if name == "src" else default


def _mixkit_candidate():
    return Candidate(
        source="mixkit",
        source_id="mixkit_rain_42",
        source_url="https://mixkit.co/free-stock-video/rain-42/",
        download_url="https://mixkit.co/free-stock-video/rain-42/",
        kind="video",
        extra={"detail_url": "https://mixkit.co/free-stock-video/rain-42/"},
    )


def _resolved_download_url(monkeypatch, page, tmp_path, soup_cls=_EmptySoup):
    """Run `download()` against `page` and report the URL it resolved to."""
    _install_fake_transport(
        monkeypatch, lambda *_a, **_k: _HtmlResponse(page), soup_cls=soup_cls
    )

    streamed = {}

    def fake_stream(_self, url, out_path):
        streamed["url"] = url
        return out_path

    monkeypatch.setattr(
        type(get_source("mixkit")), "_stream_download", fake_stream, raising=True
    )
    get_source("mixkit").download(_mixkit_candidate(), tmp_path / "clip.mp4")
    return streamed.get("url")


def test_mixkit_download_resolves_from_json_ld_alone(monkeypatch, tmp_path):
    # No download button and no <video> anywhere in the DOM stub: the
    # structured metadata has to carry the resolution on its own.
    page = _ld_page(f'{{"@type":"VideoObject","contentUrl":"{_CONTENT_URL}"}}')
    assert _resolved_download_url(monkeypatch, page, tmp_path) == _CONTENT_URL


def test_mixkit_download_falls_back_to_src_on_the_video_tag(monkeypatch, tmp_path):
    page = "<html><body><video src='...'></video></body></html>"
    assert (
        _resolved_download_url(
            monkeypatch, page, tmp_path, soup_cls=_VideoTagSoup
        )
        == _CONTENT_URL
    )


def test_mixkit_download_still_reports_a_page_it_cannot_resolve(monkeypatch, tmp_path):
    # The failure path stays intact: nothing to find is an error, not a
    # silent zero-byte file.
    with pytest.raises(RuntimeError, match="Could not find download URL"):
        _resolved_download_url(
            monkeypatch, "<html><body>no video here</body></html>", tmp_path
        )


# NARA — the v2 catalog API.
#
# The adapter used to call `/api/v2/search` with `rows`/`offset` and read
# `results[]`. That path now serves the catalog's HTML app rather than
# JSON, so every search raised on `.json()`. These tests pin the shape of
# the working endpoint so a silent regression back to v1 is caught here
# rather than as an empty corpus.
# ---------------------------------------------------------------------

_NARA_RECORD = {
    "naId": 7500,
    "title": "APOLLO 8 NASA MOON FOOTAGE",
    "generalNotes": ["Following is a general summary of scenes in the roll."],
    "shotList": "CU Radar antenna. Overall view of earth.",
    "subjects": [{"heading": "National Aeronautics and Space Administration."}],
    "digitalObjects": [
        {
            "objectId": "14869152",
            "objectFilename": "33050.mp4",
            "objectType": "Audio/Visual File (MP4)",
            "objectUrl": "https://catalog.archives.gov/media/33050.mp4",
            "objectFileSize": 12345,
        },
        {
            "objectId": "14869153",
            "objectFilename": "97-445.jpg",
            "objectType": "Image (JPG)",
            "objectUrl": "https://catalog.archives.gov/media/97-445.jpg",
        },
    ],
}


class _NARAResponse:
    """A 200 carrying one record in the v2 envelope."""

    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"body": {"hits": {"hits": [{"_source": {"record": _NARA_RECORD}}]}}}


def _nara_search(monkeypatch, kind, page=1):
    seen = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers or {}
        seen["params"] = params or {}
        return _NARAResponse()

    _install_fake_transport(monkeypatch, fake_get)
    results = get_source("nara").search(
        "apollo", SearchFilters(kind=kind, per_page=5, page=page)
    )
    return seen, results


def test_nara_requires_a_key():
    # v2 serves HTML without x-api-key, so "no key" is unavailable, not
    # merely rate-limited.
    source = get_source("nara")
    assert source.is_available() is False


def test_nara_calls_the_v2_records_endpoint(monkeypatch):
    seen, _ = _nara_search(monkeypatch, "video", page=3)

    assert seen["url"].endswith("/api/v2/records/search")
    assert seen["headers"]["x-api-key"] == "test-nara"
    # v2 paginates by 1-based `page`; offset/from/start are ignored.
    assert seen["params"]["page"] == 3
    assert "offset" not in seen["params"]
    assert seen["params"]["limit"] == 5
    assert seen["params"]["availableOnline"] == "true"


def test_nara_pushes_the_kind_filter_server_side(monkeypatch):
    seen, _ = _nara_search(monkeypatch, "video")
    assert seen["params"]["typeOfMaterials"] == "Moving Images"

    seen, _ = _nara_search(monkeypatch, "image")
    assert seen["params"]["typeOfMaterials"] == "Photographs and other Graphic Materials"

    # "any" must not constrain the search to one material type.
    seen, _ = _nara_search(monkeypatch, "any")
    assert "typeOfMaterials" not in seen["params"]


def test_nara_extracts_objects_from_the_v2_envelope(monkeypatch):
    _, videos = _nara_search(monkeypatch, "video")

    assert len(videos) == 1
    clip = videos[0]
    assert clip.download_url == "https://catalog.archives.gov/media/33050.mp4"
    assert clip.kind == "video"
    assert clip.source_url == "https://catalog.archives.gov/id/7500"
    assert clip.source_id == "7500_14869152"
    # v2 reports no dimensions or duration; the Candidate says so rather
    # than inventing them.
    assert (clip.width, clip.height, clip.duration) == (0, 0, 0.0)

    _, images = _nara_search(monkeypatch, "image")
    assert [i.kind for i in images] == ["image"]
    assert images[0].download_url.endswith("97-445.jpg")


def test_nara_tags_flatten_the_scattered_prose_fields(monkeypatch):
    # v2 dropped scopeAndContentNote; the description now lives across
    # generalNotes, shotList and subjects.
    _, videos = _nara_search(monkeypatch, "video")
    tags = videos[0].source_tags

    assert "APOLLO 8 NASA MOON FOOTAGE" in tags
    assert "general summary of scenes" in tags
    assert "Radar antenna" in tags
    assert "National Aeronautics" in tags


class _JsonResponse(_EmptyOkResponse):
    def __init__(self, payload=None, text=""):
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_coverr_requests_download_urls_and_reads_max_dimensions(monkeypatch):
    # The API omits `urls` unless asked, which made every hit drop out.
    seen = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        seen["params"] = params
        return _JsonResponse({"hits": [{
            "id": "abc", "slug": "taking-vitamins", "title": "Taking vitamins",
            "duration": "15.39", "max_width": 1920, "max_height": 1080,
            "urls": {"mp4_download": "https://cdn.coverr.co/v.mp4"},
        }]})

    _install_fake_transport(monkeypatch, fake_get)
    results = get_source("coverr").search("medicine", SearchFilters(kind="video", per_page=5))

    assert seen["params"]["urls"] == "true"
    assert len(results) == 1
    assert results[0].download_url == "https://cdn.coverr.co/v.mp4"
    assert (results[0].width, results[0].height) == (1920, 1080)


def _mixkit_json_ld_search(monkeypatch, extra_fields=""):
    # Mixkit's current markup has no result cards, only schema.org JSON-LD.
    pytest.importorskip("bs4")
    html = """<html><head><script type="application/ld+json">
    {"@graph": [
      {"@type": "BreadcrumbList"},
      {"@type": "VideoObject",
       "@id": "https://mixkit.co/free-stock-video/candle-lighting-in-the-dark-3458/#video",
       "name": "Candle lighting in the dark",
       "description": "Round candle lit illuminating while it goes out.",
       "thumbnailUrl": "https://assets.mixkit.co/videos/3458/3458-thumb-720-0.jpg",
       "contentUrl": "https://assets.mixkit.co/videos/3458/3458-1080.mp4",
       %s
       "embedUrl": "https://assets.mixkit.co/videos/3458/3458-360.mp4"}
    ]}</script></head><body></body></html>""" % extra_fields
    requests_stub = types.ModuleType("requests")
    requests_stub.get = lambda *_a, **_k: _JsonResponse(text=html)
    monkeypatch.setitem(sys.modules, "requests", requests_stub)
    return get_source("mixkit").search("candle", SearchFilters(kind="video", per_page=5))


def test_mixkit_falls_back_to_json_ld_video_objects(monkeypatch):
    results = _mixkit_json_ld_search(monkeypatch)

    assert len(results) == 1
    clip = results[0]
    assert clip.source_id == "mixkit_3458"
    assert clip.download_url == "https://assets.mixkit.co/videos/3458/3458-1080.mp4"
    assert clip.extra["detail_url"] == clip.download_url
    assert "Candle lighting in the dark" in clip.source_tags
    # No declared size: stay unknown rather than guessing from the "-1080" suffix.
    assert (clip.width, clip.height) == (0, 0)


@pytest.mark.parametrize(
    "fields",
    [
        '"width": 1080, "height": 1920,',
        '"width": "1080", "height": "1920 px",',
        '"width": {"@type": "QuantitativeValue", "value": 1080},'
        ' "height": {"@type": "QuantitativeValue", "value": 1920},',
    ],
    ids=["numbers", "strings", "quantitative-value"],
)
def test_mixkit_json_ld_keeps_declared_portrait_dimensions(monkeypatch, fields):
    (clip,) = _mixkit_json_ld_search(monkeypatch, fields)

    assert (clip.width, clip.height) == (1080, 1920)
