"""Pixabay's bot protection answers the first request with HTTP 403 and sets
the cookie that lets the next one through, so the music search must retry once
on the same opener instead of failing the whole search."""

import io
import json
import urllib.error

import pytest

from tools.audio.pixabay_music import PixabayMusic

_SEARCH_HTML = (
    b'<script>window.__BOOTSTRAP_URL__ = "/music/search/epic-orchestral/boot.json"'
    b"</script>"
)

_BOOTSTRAP = {
    "page": {
        "results": [
            {
                "id": 1,
                "name": "Epic Orchestral",
                "duration": 95,
                "rating": 4,
                "downloadCount": 10,
                "sources": {"src": "https://cdn.pixabay.com/audio/track.mp3"},
                "user": {"username": "composer"},
            }
        ]
    }
}


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _ForbiddenOnceOpener:
    """Rejects the first request the way Pixabay's bot protection does."""

    def __init__(self):
        self.calls: list[str] = []

    def open(self, request, timeout=None):
        url = request.full_url
        self.calls.append(url)
        if len(self.calls) == 1:
            raise _http_error(url, 403)
        if url.endswith("boot.json"):
            return _FakeResponse(json.dumps(_BOOTSTRAP).encode())
        return _FakeResponse(_SEARCH_HTML)


class _ForbiddenAlwaysOpener(_ForbiddenOnceOpener):
    def open(self, request, timeout=None):
        url = request.full_url
        self.calls.append(url)
        raise _http_error(url, 403)


class _ServerErrorOpener(_ForbiddenOnceOpener):
    def open(self, request, timeout=None):
        url = request.full_url
        self.calls.append(url)
        raise _http_error(url, 500)


def _http_error(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url, code, "error", {}, io.BytesIO(b"")
    )


def _patch_opener(monkeypatch, opener):
    monkeypatch.setattr(PixabayMusic, "_build_opener", lambda self: opener)


def test_search_retries_once_after_a_403_and_returns_tracks(monkeypatch):
    opener = _ForbiddenOnceOpener()
    _patch_opener(monkeypatch, opener)

    tracks = PixabayMusic()._search({"query": "epic orchestral"})

    assert len(tracks) == 1
    assert tracks[0]["title"] == "Epic Orchestral"
    assert tracks[0]["duration"] == 95
    assert opener.calls == [
        "https://pixabay.com/music/search/epic-orchestral/",
        "https://pixabay.com/music/search/epic-orchestral/",
        "https://pixabay.com/music/search/epic-orchestral/boot.json",
    ]


def test_search_gives_up_when_the_retry_is_refused_too(monkeypatch):
    opener = _ForbiddenAlwaysOpener()
    _patch_opener(monkeypatch, opener)

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        PixabayMusic()._search({"query": "epic orchestral"})

    assert excinfo.value.code == 403
    assert len(opener.calls) == 2


def test_search_does_not_retry_other_statuses(monkeypatch):
    opener = _ServerErrorOpener()
    _patch_opener(monkeypatch, opener)

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        PixabayMusic()._search({"query": "epic orchestral"})

    assert excinfo.value.code == 500
    assert len(opener.calls) == 1