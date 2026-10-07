"""freesound_music returns each sound's own Creative Commons license and author."""

import io
import json
import urllib.parse

from tools.audio.freesound_music import FreesoundMusic

SOUND = {
    "id": 42,
    "name": "dark drone",
    "duration": 60,
    "previews": {"preview-hq-mp3": "https://cdn.freesound.org/42.mp3"},
    "tags": ["drone"],
    "avg_rating": 4.5,
    "username": "someone",
    "license": "http://creativecommons.org/licenses/by/4.0/",
}


def test_search_requests_license_and_result_returns_it(monkeypatch, tmp_path):
    monkeypatch.setenv("FREESOUND_API_KEY", "k")
    urls = []

    def fake_urlopen(request, timeout=None):
        urls.append(request.full_url)
        if "/search/text/" in request.full_url:
            body = json.dumps({"results": [SOUND]}).encode()
        else:
            body = b"mp3"
        return io.BytesIO(body)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = FreesoundMusic().execute({"query": "drone", "output_path": str(tmp_path / "m.mp3")})

    assert result.success, result.error
    fields = urllib.parse.parse_qs(urllib.parse.urlparse(urls[0]).query)["fields"][0].split(",")
    assert "license" in fields
    assert result.data["license"] == SOUND["license"]
    assert result.data["author"] == SOUND["username"]
