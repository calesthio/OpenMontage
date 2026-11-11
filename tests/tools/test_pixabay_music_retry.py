"""pixabay_music scrapes pixabay.com, which answers 403 intermittently.

Retry 403/429/5xx with a wait; other errors (404) fail immediately.
"""

import io
import urllib.error

import pytest

from tools.audio import pixabay_music
from tools.audio.pixabay_music import PixabayMusic

PAGE = b'<html><a href="https://cdn.pixabay.com/audio/2024/01/01/track.mp3">x</a></html>'


def _http_error(url, code):
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(b""))


class _FakeOpener:
    def __init__(self, failures):
        self.failures = list(failures)
        self.calls = 0

    def open(self, request, timeout=None):
        self.calls += 1
        if self.failures:
            raise _http_error(request.full_url, self.failures.pop(0))
        return io.BytesIO(PAGE)


@pytest.fixture
def sleeps(monkeypatch):
    waited = []
    monkeypatch.setattr(pixabay_music.time, "sleep", waited.append)
    return waited


def test_403_on_search_and_download_is_retried(monkeypatch, tmp_path, sleeps):
    opener = _FakeOpener([403, 403])
    monkeypatch.setattr(PixabayMusic, "_build_opener", lambda self: opener)
    downloads = []

    def fake_urlopen(request, timeout=None):
        downloads.append(request.full_url)
        if len(downloads) == 1:
            raise _http_error(request.full_url, 403)
        return io.BytesIO(b"mp3")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = PixabayMusic().execute({"query": "dark", "output_path": str(tmp_path / "m.mp3")})

    assert result.success, result.error
    assert opener.calls == 3 and len(downloads) == 2
    assert len(sleeps) == 3 and all(s > 0 for s in sleeps)


def test_404_is_not_retried(monkeypatch, tmp_path, sleeps):
    opener = _FakeOpener([404])
    monkeypatch.setattr(PixabayMusic, "_build_opener", lambda self: opener)
    result = PixabayMusic().execute({"query": "dark", "output_path": str(tmp_path / "m.mp3")})

    assert not result.success and "404" in result.error
    assert opener.calls == 1 and sleeps == []


def test_gives_up_after_retries(monkeypatch, tmp_path, sleeps):
    opener = _FakeOpener([403] * 10)
    monkeypatch.setattr(PixabayMusic, "_build_opener", lambda self: opener)
    result = PixabayMusic().execute({"query": "dark", "output_path": str(tmp_path / "m.mp3")})

    assert not result.success and "403" in result.error
    assert opener.calls == len(PixabayMusic._RETRY_DELAYS) + 1
