"""Regression tests for audio_mixer full_mix ducking filtergraph.

The ducking branch built an `acopy[speech_dup]` filter whose output pad was
never consumed, leaving the FFmpeg filtergraph with a dangling output. FFmpeg
rejects that, so `full_mix` with the most common shape — a single narration
track plus one music bed, with ducking enabled (the default) — always failed.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.audio.audio_mixer import AudioMixer  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg required for full_mix"
)


def _sine(path: Path, freq: int, dur: int) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}", str(path)],
        capture_output=True,
        check=True,
        timeout=30,
    )


def _has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    return "audio" in out.stdout


def test_full_mix_single_narration_plus_music_with_ducking(tmp_path):
    speech = tmp_path / "speech.wav"
    music = tmp_path / "music.wav"
    _sine(speech, 440, 2)
    _sine(music, 220, 3)
    out = tmp_path / "mixed.wav"

    result = AudioMixer().execute(
        {
            "operation": "full_mix",
            "tracks": [
                {"path": str(speech), "role": "speech"},
                {"path": str(music), "role": "music"},
            ],
            "ducking": {"enabled": True},
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    assert out.exists() and _has_audio(out)


def test_full_mix_multi_narration_plus_music_with_ducking(tmp_path):
    s1, s2 = tmp_path / "s1.wav", tmp_path / "s2.wav"
    music = tmp_path / "music.wav"
    _sine(s1, 440, 2)
    _sine(s2, 330, 2)
    _sine(music, 220, 3)
    out = tmp_path / "mixed_multi.wav"

    result = AudioMixer().execute(
        {
            "operation": "full_mix",
            "tracks": [
                {"path": str(s1), "role": "speech"},
                {"path": str(s2), "role": "speech"},
                {"path": str(music), "role": "music"},
            ],
            "ducking": {"enabled": True},
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    assert out.exists() and _has_audio(out)
