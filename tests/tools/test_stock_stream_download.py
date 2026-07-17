"""The shared stock-source downloader (audit 2026-07-15, structural item 4).

Five adapters each carried a byte-identical private _stream_download, and the
copies had already drifted (mixkit said timeout=120 where the rest said 180,
for no recorded reason). Adapters are "dumb by design" — API shape in,
Candidate out; chunked downloading is not API shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests  # noqa: E402

from tools.video.stock_sources import base  # noqa: E402


class _FakeResponse:
    def __init__(self, chunks, status_ok=True):
        self._chunks = chunks
        self._ok = status_ok
        self.raised = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if not self._ok:
            raise requests.HTTPError("404")

    def iter_content(self, chunk_size=None):
        yield from self._chunks


def test_streams_chunks_to_disk(monkeypatch, tmp_path):
    captured = {}

    def fake_get(url, **kwargs):
        captured.update(kwargs)
        captured["url"] = url
        return _FakeResponse([b"abc", b"def"])

    monkeypatch.setattr(requests, "get", fake_get)
    out = tmp_path / "nested" / "clip.mp4"
    result = base.stream_download("http://x/clip.mp4", out)

    assert result == out
    assert out.read_bytes() == b"abcdef"
    assert captured["stream"] is True, "must stream, not buffer the whole clip"
    assert captured["timeout"] == base.DOWNLOAD_TIMEOUT_SECONDS


def test_creates_parent_directories(monkeypatch, tmp_path):
    monkeypatch.setattr(requests, "get", lambda url, **kw: _FakeResponse([b"x"]))
    out = tmp_path / "a" / "b" / "c.mp4"
    base.stream_download("http://x/c.mp4", out)
    assert out.exists()


def test_always_sends_a_user_agent(monkeypatch, tmp_path):
    # Some sources 403 without one.
    seen = {}
    monkeypatch.setattr(
        requests, "get",
        lambda url, **kw: seen.update(kw) or _FakeResponse([b"x"]),
    )
    base.stream_download("http://x/a.mp4", tmp_path / "a.mp4")
    assert seen["headers"]["User-Agent"] == base.DEFAULT_USER_AGENT


def test_caller_headers_merge_without_dropping_the_user_agent(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(
        requests, "get",
        lambda url, **kw: seen.update(kw) or _FakeResponse([b"x"]),
    )
    base.stream_download("http://x/a.mp4", tmp_path / "a.mp4", headers={"Referer": "http://r"})
    assert seen["headers"]["Referer"] == "http://r"
    assert seen["headers"]["User-Agent"] == base.DEFAULT_USER_AGENT


def test_http_errors_propagate(monkeypatch, tmp_path):
    monkeypatch.setattr(requests, "get", lambda url, **kw: _FakeResponse([], status_ok=False))
    with pytest.raises(requests.HTTPError):
        base.stream_download("http://x/missing.mp4", tmp_path / "m.mp4")


def test_every_deduped_adapter_delegates_to_the_shared_helper(monkeypatch, tmp_path):
    # Pins the dedup: each adapter's _stream_download must route here, so a
    # future fix lands once rather than in five places.
    from tools.video.stock_sources import dareful, esa, jaxa, mixkit, noaa

    calls = []
    monkeypatch.setattr(
        base, "stream_download",
        lambda url, out_path, **kw: calls.append(url) or Path(out_path),
    )
    for mod in (dareful, esa, jaxa, mixkit, noaa):
        monkeypatch.setattr(mod, "stream_download", base.stream_download, raising=False)

    adapters = [
        dareful.DarefulSource(), esa.ESASource(), jaxa.JAXASource(),
        mixkit.MixkitSource(), noaa.NOAASource(),
    ]
    for a in adapters:
        a._stream_download("http://x/v.mp4", tmp_path / "v.mp4")
    assert len(calls) == len(adapters)
