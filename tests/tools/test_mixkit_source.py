"""Mixkit stock-source licensing and rendition resolution.

Pages below are trimmed copies of mixkit.co markup: a listing page whose
schema.org data declares each clip's licence, and detail pages for a
Free clip (720p + 1080p published) and a Restricted clip (720p, personal
use only). No network is used.
"""
from __future__ import annotations

import json
import sys
import types

import pytest

pytest.importorskip("bs4")

from tools.video.stock_sources.base import SearchFilters  # noqa: E402
from tools.video.stock_sources.mixkit import (  # noqa: E402
    LICENSE_FREE,
    LICENSE_RESTRICTED,
    MixkitLicenseError,
    MixkitSource,
    listing_licenses,
    parse_detail_offer,
)

FREE_URL = "https://mixkit.co/free-stock-video/stewing-tomato-sauce-3804/"
RESTRICTED_URL = "https://mixkit.co/free-stock-video/wet-red-tomatoes-on-a-board-9457/"


def _ld(nodes):
    return ('<script type="application/ld+json" data-test-id="schema_org_data-0">'
            + json.dumps({"@context": "https://schema.org", "@graph": nodes}) + "</script>")


LISTING = "<html><head>" + _ld([{
    "@type": "ItemList",
    "itemListElement": [
        {"@type": "VideoObject", "@id": FREE_URL + "#video", "copyrightNotice": "Free",
         "license": "https://mixkit.co/license/#videoFree"},
        {"@type": "VideoObject", "@id": RESTRICTED_URL + "#video", "copyrightNotice": "Mixkit Restricted License",
         "license": "https://mixkit.co/license/#videoRestricted"},
    ],
}]) + """</head><body>
<div class="item-grid-card"><a href="/free-stock-video/stewing-tomato-sauce-3804/">Stewing tomato sauce</a>
  <span class="item-grid-video-player__overlay-video-title">Stewing tomato sauce</span></div>
<div class="item-grid-card"><a href="/free-stock-video/wet-red-tomatoes-on-a-board-9457/">Wet red tomatoes</a>
  <span class="item-grid-video-player__overlay-video-title">Wet red tomatoes on a board</span></div>
</body></html>"""

FREE_DETAIL = """<div class="download-video-options__download" data-test-id="video-download-mixkit">
 <p><span class="download-video-options__download-title">Free Download</span> Download this free stock video clip for
 commercial or personal use, under the <a href="/license/#videoFree" data-license="videoFree">Mixkit Stock Video Free License</a>.</p>
 <div data-controller="download--video-options">
  <input type="radio" name="download-option" data-label="HD Ready" value="/free-stock-video/download/3804/?context=sidebar&amp;type=720p" checked />
  <input type="radio" name="download-option" data-label="Full HD" value="/free-stock-video/download/3804/?context=sidebar&amp;type=1080p" />
 </div></div>"""

RESTRICTED_DETAIL = """<div class="download-video-options__download download-video-options__download--elements-free">
 <p><span class="download-video-options__download-title">Free Download - 720p Version for Personal Use only</span>
 Download this free stock video clip for personal use only, under the
 <a href="/license/#videoRestricted" data-license="videoRestricted">Mixkit Restricted License</a>.</p>
 <button class="download-button--plain-text" data-download--button-modal-url-value="/free-stock-video/download/9457/?context=sidebar">
 Download low resolution for free</button></div>"""


def _modal(url):
    return f'<div data-controller="download--modal" data-download--modal-url-value="{url}"></div>'


class _Resp:
    def __init__(self, text="", status=200, body=b"x" * 4096):
        self.text, self.status_code, self._body = text, status, body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1):
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _install(monkeypatch, routes):
    """Route `requests.get(url)` to canned responses; record every URL requested."""
    calls = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        for prefix, resp in routes.items():
            if url.startswith(prefix):
                return resp(url) if callable(resp) else resp
        raise AssertionError(f"unexpected request: {url}")

    stub = types.ModuleType("requests")
    stub.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", stub)
    return calls


FILE_1080 = "https://assets.mixkit.co/videos/3804/3804-1080.mp4"
FILE_720 = "https://assets.mixkit.co/videos/3804/3804-720.mp4"
FREE_ROUTES = {
    FREE_URL: _Resp(FREE_DETAIL),
    "https://mixkit.co/free-stock-video/download/3804/?context=sidebar&type=1080p": _Resp(_modal(FILE_1080)),
    "https://mixkit.co/free-stock-video/download/3804/?context=sidebar&type=720p": _Resp(_modal(FILE_720)),
}


def _candidate(url, require_commercial=True):
    return types.SimpleNamespace(
        source="mixkit", source_url=url, download_url=url, license="", width=0, height=0,
        extra={"detail_url": url, "require_commercial_use": require_commercial},
    )


# ---- parsing --------------------------------------------------------------

def test_listing_licenses_read_from_nested_schema_org():
    assert listing_licenses(LISTING) == {FREE_URL: LICENSE_FREE, RESTRICTED_URL: LICENSE_RESTRICTED}


def test_detail_offer_free_lists_published_renditions_best_first():
    offer = parse_detail_offer(FREE_DETAIL)
    assert offer["license_key"] == LICENSE_FREE
    assert [r["label"] for r in offer["renditions"]] == ["1080p", "720p"]


def test_detail_offer_restricted_is_personal_use_720p():
    offer = parse_detail_offer(RESTRICTED_DETAIL)
    assert offer["license_key"] == LICENSE_RESTRICTED
    assert "personal" in offer["license_label"].lower()
    assert [r["label"] for r in offer["renditions"]] == ["720p"]


def test_detail_offer_without_licence_is_rejected():
    with pytest.raises(ValueError):
        parse_detail_offer("<div class='download-video-options__download'><button>Download</button></div>")


# ---- search ---------------------------------------------------------------

def test_search_excludes_restricted_clips_by_default(monkeypatch):
    _install(monkeypatch, {"https://mixkit.co/free-stock-video/tomato/": _Resp(LISTING)})
    results = MixkitSource().search("tomato", SearchFilters(per_page=10))
    assert [c.source_url for c in results] == [FREE_URL]
    assert "Free License" in results[0].license
    assert results[0].download_url == FREE_URL  # never a guessed file URL


def test_search_labels_restricted_clips_when_commercial_use_not_required(monkeypatch):
    _install(monkeypatch, {"https://mixkit.co/free-stock-video/tomato/": _Resp(LISTING)})
    results = MixkitSource().search("tomato", SearchFilters(per_page=10, require_commercial_use=False))
    by_url = {c.source_url: c for c in results}
    assert "Restricted" in by_url[RESTRICTED_URL].license
    assert "commercial" in by_url[FREE_URL].license.lower()


# ---- download -------------------------------------------------------------

def test_download_free_clip_uses_published_1080p_and_records_evidence(monkeypatch, tmp_path):
    calls = _install(monkeypatch, dict(FREE_ROUTES, **{FILE_1080: _Resp(), FILE_720: _Resp()}))
    cand = _candidate(FREE_URL)
    out = MixkitSource().download(cand, tmp_path / "clip.mp4")
    assert out.exists()
    assert cand.download_url == FILE_1080
    ev = cand.extra["license_evidence"]
    assert ev["license_key"] == LICENSE_FREE and ev["rendition"] == "1080p" and ev["file_url"] == FILE_1080
    assert FILE_720 not in calls


def test_download_failed_1080p_falls_back_to_published_720p_not_a_guess(monkeypatch, tmp_path):
    calls = _install(monkeypatch, dict(FREE_ROUTES, **{FILE_1080: _Resp(status=404), FILE_720: _Resp()}))
    cand = _candidate(FREE_URL)
    MixkitSource().download(cand, tmp_path / "clip.mp4")
    assert cand.download_url == FILE_720
    assert cand.extra["license_evidence"]["rendition"] == "720p"
    assert cand.extra["license_evidence"]["license_key"] == LICENSE_FREE
    # The 720p file was reached through the page's own 720p rendition link.
    assert "https://mixkit.co/free-stock-video/download/3804/?context=sidebar&type=720p" in calls


def test_download_refuses_restricted_clip_when_commercial_use_required(monkeypatch, tmp_path):
    calls = _install(monkeypatch, {RESTRICTED_URL: _Resp(RESTRICTED_DETAIL)})
    with pytest.raises(MixkitLicenseError):
        MixkitSource().download(_candidate(RESTRICTED_URL), tmp_path / "clip.mp4")
    assert calls == [RESTRICTED_URL]  # nothing downloaded
    assert not (tmp_path / "clip.mp4").exists()


def test_download_restricted_clip_allowed_for_personal_use_keeps_restricted_label(monkeypatch, tmp_path):
    file_720 = "https://assets.mixkit.co/videos/9457/9457-720.mp4"
    _install(monkeypatch, {
        RESTRICTED_URL: _Resp(RESTRICTED_DETAIL),
        "https://mixkit.co/free-stock-video/download/9457/": _Resp(_modal(file_720)),
        file_720: _Resp(),
    })
    cand = _candidate(RESTRICTED_URL, require_commercial=False)
    MixkitSource().download(cand, tmp_path / "clip.mp4")
    assert "Restricted" in cand.license and "personal" in cand.license.lower()
    assert cand.extra["license_evidence"]["license_key"] == LICENSE_RESTRICTED


def test_download_fails_when_every_published_rendition_fails(monkeypatch, tmp_path):
    _install(monkeypatch, dict(FREE_ROUTES, **{FILE_1080: _Resp(status=500), FILE_720: _Resp(status=500)}))
    cand = _candidate(FREE_URL)
    with pytest.raises(RuntimeError, match="1080p.*720p"):
        MixkitSource().download(cand, tmp_path / "clip.mp4")
    assert "license_evidence" not in cand.extra


def test_json_ld_search_fallback_also_excludes_restricted(monkeypatch):
    # Listing with no result cards: only schema.org entries, one per licence.
    html = "<html><head>" + _ld([
        {"@type": "VideoObject", "@id": FREE_URL + "#video", "name": "Stewing", "copyrightNotice": "Free",
         "contentUrl": "https://assets.mixkit.co/videos/3804/3804-720.mp4"},
        {"@type": "VideoObject", "@id": RESTRICTED_URL + "#video", "name": "Wet", "copyrightNotice": "Mixkit Restricted License",
         "contentUrl": "https://assets.mixkit.co/videos/9457/9457-720.mp4"},
    ]) + "</head><body></body></html>"
    _install(monkeypatch, {"https://mixkit.co/free-stock-video/tomato/": _Resp(html)})
    results = MixkitSource().search("tomato", SearchFilters(per_page=10))
    assert [c.source_url for c in results] == [FREE_URL]
    assert "Free License" in results[0].license
