"""Pixabay rejects per_page outside 3-200 with HTTP 400, so every
Pixabay caller must clamp before building the request."""

import requests

from tools.graphics.pixabay_image import PixabayImage
from tools.video.pixabay_video import PixabayVideo
from tools.video.stock_sources.base import SearchFilters
from tools.video.stock_sources.pixabay_video import PixabayVideoSource


class _FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"hits": [], "total": 0}


def _capture_get(captured):
    def fake_get(url, params=None, timeout=None, **kwargs):
        captured["params"] = params
        return _FakeResponse()

    return fake_get


def test_pixabay_video_tool_clamps_per_page(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "test-key")
    captured = {}
    monkeypatch.setattr(requests, "get", _capture_get(captured))

    PixabayVideo().execute({"query": "sky", "per_page": 1})
    assert captured["params"]["per_page"] == 3

    PixabayVideo().execute({"query": "sky", "per_page": 500})
    assert captured["params"]["per_page"] == 200


def test_pixabay_image_tool_clamps_per_page(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "test-key")
    captured = {}
    monkeypatch.setattr(requests, "get", _capture_get(captured))

    PixabayImage().execute({"query": "sky", "per_page": 1})
    assert captured["params"]["per_page"] == 3

    PixabayImage().execute({"query": "sky", "per_page": 500})
    assert captured["params"]["per_page"] == 200


def test_pixabay_stock_source_clamps_per_page(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "test-key")
    captured = {}
    monkeypatch.setattr(requests, "get", _capture_get(captured))

    source = PixabayVideoSource()
    source.search("sky", SearchFilters(per_page=1))
    assert captured["params"]["per_page"] == 3

    source.search("sky", SearchFilters(per_page=500))
    assert captured["params"]["per_page"] == 200
