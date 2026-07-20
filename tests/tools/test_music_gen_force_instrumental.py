"""Regression for the force_instrumental mandate (REVIEW §8 #8).

``skills/creative/music-gen-usage.md`` mandates that video background music
ALWAYS be generated instrumental-only (vocals collide with narration).
``music_gen`` historically never sent the kwarg, so ElevenLabs could return
vocal tracks. This test pins the payload to include ``force_instrumental=True``
by default and to honor an explicit opt-out.
"""

from __future__ import annotations

import sys
import types

import pytest

from tools.audio.music_gen import MusicGen


class _FakeResponse:
    def __init__(self, content: bytes = b"audio") -> None:
        self.content = content

    def raise_for_status(self) -> None:  # noqa: D401 - stub
        return None


def _install_fake_requests(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict,
) -> types.ModuleType:
    """Install a stub ``requests`` module that records the JSON payload."""
    fake = types.ModuleType("requests")

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = json
        return _FakeResponse()

    fake.post = fake_post
    monkeypatch.setitem(sys.modules, "requests", fake)
    return fake


def test_force_instrumental_is_sent_true_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    captured: dict = {}
    _install_fake_requests(monkeypatch, captured)
    # Route the output to tmp_path so the test never writes music_output.mp3
    # into the repo root (the default output_path).
    out = tmp_path / "bg.mp3"
    MusicGen()._generate(
        {
            "prompt": "gentle ambient",
            "duration_seconds": 10,
            "output_path": str(out),
        },
        "test-key",
    )

    assert "force_instrumental" in captured["payload"], "force_instrumental kwarg was never sent"
    assert captured["payload"]["force_instrumental"] is True
    assert captured["payload"]["music_length_ms"] == 10_000


def test_explicit_vocal_opt_out_is_respected(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    captured: dict = {}
    _install_fake_requests(monkeypatch, captured)
    out = tmp_path / "vocals.mp3"
    MusicGen()._generate(
        {
            "prompt": "lead vocal pop",
            "duration_seconds": 10,
            "force_instrumental": False,
            "output_path": str(out),
        },
        "test-key",
    )

    assert captured["payload"]["force_instrumental"] is False


def test_schema_defaults_force_instrumental_to_true():
    props = MusicGen().input_schema["properties"]["force_instrumental"]
    assert props["type"] == "boolean"
    assert props["default"] is True
