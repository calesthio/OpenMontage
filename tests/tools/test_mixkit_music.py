"""mixkit_music: listing, download, failure handling and registry wiring. No network."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from tools.audio import mixkit_music as mm
from tools.audio.mixkit_music import MixkitMusic

TRACK_URL = "https://assets.mixkit.co/music/595/595.mp3"
PAGE = ('<script type="application/ld+json" data-test-id="schema_org_data-0">' + json.dumps({"@graph": [{
    "@type": "ItemList",
    "itemListElement": [
        {"@type": "MusicRecording", "name": "Secret Garden", "byArtist": "Eugenio Mininni", "genre": "Film Score",
         "duration": "PT2M33S", "url": TRACK_URL, "license": "https://mixkit.co/license/#musicFree"},
        {"@type": "MusicRecording", "name": "Short Sting", "duration": "PT0M12S",
         "url": "https://assets.mixkit.co/music/1/1.mp3"},
    ],
}]}) + "</script>")


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _route(monkeypatch, track_error=None):
    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if "/free-stock-music/tag/" in url:
            return _Resp(PAGE.encode())
        if url == TRACK_URL:
            if track_error:
                raise track_error
            return _Resp(b"ID3" + b"\0" * 2048)
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)

    monkeypatch.setattr(mm.urllib.request, "urlopen", fake_urlopen)


def test_list_filters_by_duration_and_carries_licence(monkeypatch):
    _route(monkeypatch)
    r = MixkitMusic().execute({"query": "cartoons", "min_duration": 30})
    assert r.success
    tracks = r.data["tracks"]
    assert [t["title"] for t in tracks] == ["Secret Garden"]
    assert tracks[0]["duration_seconds"] == 153
    assert tracks[0]["license"].endswith("#musicFree")
    assert "broadcast" in tracks[0]["license_limits"]
    assert r.artifacts == []


def test_download_writes_selected_track(monkeypatch, tmp_path):
    _route(monkeypatch)
    out = tmp_path / "bed.mp3"
    r = MixkitMusic().execute({"query": "cartoons", "pick": 0, "output_path": str(out)})
    assert r.success and out.exists() and r.artifacts == [str(out)]
    assert r.data["selected"]["output"] == str(out)


def test_download_network_failure_returns_failed_result(monkeypatch, tmp_path):
    _route(monkeypatch, track_error=urllib.error.URLError("connection reset"))
    out = tmp_path / "bed.mp3"
    r = MixkitMusic().execute({"query": "cartoons", "pick": 0, "output_path": str(out)})
    assert not r.success
    assert "download failed" in r.error
    assert not out.exists()


def test_search_failure_returns_failed_result(monkeypatch):
    def boom(*_a, **_k):
        raise urllib.error.URLError("dns")

    monkeypatch.setattr(mm.urllib.request, "urlopen", boom)
    r = MixkitMusic().execute({"query": "cartoons"})
    assert not r.success and "search failed" in r.error


def test_pick_out_of_range_is_a_failed_result(monkeypatch):
    _route(monkeypatch)
    r = MixkitMusic().execute({"query": "cartoons", "pick": 5})
    assert not r.success and "out of range" in r.error


def test_registry_discovers_mixkit_music():
    from tools.tool_registry import ToolRegistry

    reg = ToolRegistry()
    reg.discover()
    tool = reg.get("mixkit_music") if hasattr(reg, "get") else reg._tools["mixkit_music"]
    assert tool.capability == "music_search"
    assert "musicFree" in tool.install_instructions
