"""Fractional video durations must produce nonempty, fitting audio windows."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tools.analysis.audio_energy import AudioEnergy


def analyze(tmp_path, video_duration, loudness, audio_duration):
    source = tmp_path / "audio.wav"
    source.touch()
    probe = SimpleNamespace(stdout=json.dumps({"format": {"duration": str(audio_duration)}}))
    meter = SimpleNamespace(stderr="\n".join(f"t: {i + 0.1} M: {value}" for i, value in enumerate(loudness)))
    with patch("tools.analysis.audio_energy.shutil.which", return_value="ffmpeg"), patch("tools.analysis.audio_energy.subprocess.run", side_effect=[probe, meter]):
        return AudioEnergy().execute({"input_path": str(source), "video_duration_seconds": video_duration})


def test_subsecond_video_uses_one_analysis_bucket(tmp_path):
    result = analyze(tmp_path, 0.5, [-30, -10, -20], 3)
    assert result.success, result.error
    assert result.data["recommended_offset_seconds"] == 1


def test_fractional_window_covers_the_full_video(tmp_path):
    result = analyze(tmp_path, 1.5, [-10, -50, -20, -20], 4)
    assert result.success, result.error
    assert result.data["recommended_offset_seconds"] == 2
    assert not result.data["needs_loop"]


def test_partial_final_bucket_cannot_force_unnecessary_loop(tmp_path):
    result = analyze(tmp_path, 0.5, [-30, -20, -10], 2.2)
    assert result.success, result.error
    assert result.data["recommended_offset_seconds"] == 1
    assert not result.data["needs_loop"]


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf")])
def test_invalid_duration_returns_tool_error(tmp_path, duration):
    result = analyze(tmp_path, duration, [-30, -20], 2)
    assert not result.success
    assert "duration" in result.error.lower()
