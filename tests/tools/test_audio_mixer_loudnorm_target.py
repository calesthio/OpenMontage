"""Regression for the loudnorm LUFS target parameterization (REVIEW §8 #1).

audio_mixer hard-coded loudnorm I=-16 (Apple Podcasts), but
sound-design.md targets -14 for YouTube/TikTok/IG and
edit_decisions.metadata.loudnorm_target is the declarative form. The
mismatch meant the executed loudness silently defaulted to podcast
levels regardless of the target platform. These tests pin the per-call
target resolution without invoking ffmpeg.
"""

from __future__ import annotations

import math

from tools.audio.audio_mixer import AudioMixer


def _filter(inputs: dict) -> str:
    return AudioMixer._loudnorm_filter(inputs, "premix", "out")


def test_default_target_is_podcast_minus_16():
    f = _filter({})
    assert "I=-16.0" in f or "I=-16" in f
    assert f.startswith("[premix]loudnorm=")
    assert f.endswith("[out]")


def test_youtube_target_minus_14_is_honored():
    f = _filter({"loudnorm_target": -14})
    assert "I=-14.0" in f or "I=-14" in f


def test_out_of_range_target_is_clamped():
    # A nonsense value must not produce a malformed ffmpeg arg.
    f = _filter({"loudnorm_target": 99})
    # Clamped to the 0 LUFS ceiling.
    assert "I=0.0" in f


def test_non_numeric_target_falls_back_to_default():
    f = _filter({"loudnorm_target": "not-a-number"})
    assert "I=-16.0" in f or "I=-16" in f


def test_schema_exposes_loudnorm_target_default():
    prop = AudioMixer().input_schema["properties"]["loudnorm_target"]
    assert prop["type"] == "number"
    assert math.isclose(prop["default"], -16)
