"""``freesound_music`` must report the actual license of the chosen sound (#736).

Every Freesound sound carries its own license (CC0, CC BY, CC BY-NC...) and the
agent reading the result needs to know it: whether attribution is required, and
whether the track may be used commercially, both depend on it. Returning the
generic string "Creative Commons (check individual sound license)" forced the
agent to guess, and left the author reachable only by parsing ``freesound_url``.

Two things have to hold, and they are separate failure modes:

1. ``_search`` must *ask* the API for ``license``. Without it the field is
   absent from the payload and every downstream fix is dead code.
2. ``execute`` must *surface* it, falling back to the generic string when the
   API omits it, so partial responses keep the previous behaviour rather than
   handing the agent a bare ``None``.

The registry is not exercised here; the tool is instantiated directly because
the assertion is about this tool's contract, not about discovery.
"""

from __future__ import annotations

import json
import urllib.parse

import pytest

from tools.audio.freesound_music import FreesoundMusic

GENERIC = "Creative Commons (check individual sound license)"
LICENSE = "http://creativecommons.org/licenses/by/4.0/"


def _sound(**overrides):
    sound = {
        "id": 424242,
        "name": "ambient drone",
        "duration": 72.5,
        "avg_rating": 4.2,
        "tags": ["ambient", "drone"],
        "username": "soundauthor",
        "license": LICENSE,
        "previews": {"preview-hq-mp3": "https://example.invalid/preview.mp3"},
    }
    sound.update(overrides)
    return sound


class _FakeResponse:
    """Minimal stand-in for the object returned by ``urlopen``."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


@pytest.fixture()
def tool(monkeypatch, tmp_path):
    monkeypatch.setenv("FREESOUND_API_KEY", "test-key")
    instance = FreesoundMusic()
    monkeypatch.setattr(
        instance, "_download", lambda sound, inputs, api_key: tmp_path / "out.mp3"
    )
    return instance


def _run(monkeypatch, tool, sound, query="ambient"):
    """A distinct query per test keeps calls independent of the asset cache."""
    monkeypatch.setattr(
        FreesoundMusic, "_search", lambda self, inputs, api_key: [sound]
    )
    return tool.execute({"query": query})


def test_search_requests_the_license_field(monkeypatch, tool):
    """Regression: `fields` omitted `license`, so it never came back."""
    captured: dict[str, str] = {}

    def fake_urlopen(request, *args, **kwargs):
        captured["url"] = request.full_url
        return _FakeResponse(json.dumps({"results": []}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    tool._search({"query": "ambient", "min_duration": 30, "max_duration": 120}, "k")

    query = urllib.parse.urlparse(captured["url"]).query
    fields = urllib.parse.parse_qs(query)["fields"][0]
    assert "license" in fields.split(",")


def test_result_carries_the_sound_license(monkeypatch, tool):
    result = _run(monkeypatch, tool, _sound(), query="with-license")
    assert result.success is True
    assert result.data["license"] == LICENSE


def test_falls_back_to_generic_when_license_is_absent(monkeypatch, tool):
    """A payload without `license` must not regress to a bare None."""
    sound = _sound()
    del sound["license"]
    result = _run(monkeypatch, tool, sound, query="no-license")
    assert result.success is True
    assert result.data["license"] == GENERIC


def test_author_is_surfaced_even_without_a_license(monkeypatch, tool):
    sound = _sound()
    del sound["license"]
    result = _run(monkeypatch, tool, sound, query="author-only")
    assert result.data["author"] == "soundauthor"
