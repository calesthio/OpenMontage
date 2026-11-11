"""audio_mixer full_mix: per-track in-point (`offset_seconds`) and `loop`.

The 2026-11-11 audit found the compose skills had to tell agents to trim or
loop the music bed with a separate FFmpeg call before mixing, because
`audio_mixer` could only delay a track (`start_seconds`) and pad or trim the
whole mix (`target_duration`). These tests drive real FFmpeg.
"""

import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from tools.audio.audio_mixer import AudioMixer
from tools.base_tool import ToolResult

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required",
)


def _run(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], capture_output=True, check=True, timeout=60)


def _silence_then_tone(path: Path, silence: float, tone: float) -> None:
    _run([
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={silence}",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={tone}:sample_rate=44100",
        "-filter_complex", "[0][1]concat=n=2:v=0:a=1", str(path),
    ])


def _tone(path: Path, seconds: float) -> None:
    _run(["-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}:sample_rate=44100", str(path)])


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, check=True, text=True, timeout=30,
    )
    return float(out.stdout.strip())


def _rms(path: Path, start: float, end: float) -> float:
    with wave.open(str(path), "rb") as handle:
        assert handle.getsampwidth() == 2
        channels = handle.getnchannels()
        rate = handle.getframerate()
        handle.setpos(int(start * rate))
        raw = handle.readframes(int((end - start) * rate))
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)[::channels]
    return math.sqrt(sum(s * s for s in samples) / max(1, len(samples)))


def _mix(tmp_path: Path, track: dict, **extra) -> tuple[ToolResult, Path]:
    out = tmp_path / "mix.wav"
    result = AudioMixer().execute({
        "operation": "full_mix",
        "tracks": [track],
        "ducking": {"enabled": False},
        "normalize": False,
        "output_path": str(out),
        **extra,
    })
    return result, out


def test_offset_seconds_starts_the_track_at_its_in_point(tmp_path: Path) -> None:
    music = tmp_path / "music.wav"
    _silence_then_tone(music, 1.5, 1.5)

    result, out = _mix(tmp_path, {"path": str(music), "role": "music", "offset_seconds": 1.5})

    assert result.success, result.error
    assert _duration(out) == pytest.approx(1.5, abs=0.1)
    assert _rms(out, 0.05, 0.5) > 1000  # the tone, not the 1.5 s of leading silence


def test_loop_repeats_a_short_bed_to_the_target_duration(tmp_path: Path) -> None:
    music = tmp_path / "music.wav"
    _tone(music, 1.0)

    result, out = _mix(
        tmp_path, {"path": str(music), "role": "music", "loop": True}, target_duration=4.0
    )

    assert result.success, result.error
    assert _duration(out) == pytest.approx(4.0, abs=0.1)
    assert _rms(out, 3.2, 3.8) > 1000  # still playing after three repeats


def test_loop_fade_out_lands_at_the_end_of_the_mix(tmp_path: Path) -> None:
    music = tmp_path / "music.wav"
    _tone(music, 1.0)

    result, out = _mix(
        tmp_path,
        {"path": str(music), "role": "music", "loop": True, "fade_out_seconds": 1.0},
        target_duration=3.0,
    )

    assert result.success, result.error
    assert _rms(out, 2.9, 3.0) < _rms(out, 1.0, 1.5) * 0.3


def test_loop_without_target_duration_is_rejected(tmp_path: Path) -> None:
    music = tmp_path / "music.wav"
    _tone(music, 1.0)

    result, _ = _mix(tmp_path, {"path": str(music), "role": "music", "loop": True})

    assert not result.success
    assert "target_duration" in result.error


def test_offset_past_the_end_is_rejected(tmp_path: Path) -> None:
    music = tmp_path / "music.wav"
    _tone(music, 1.0)

    result, _ = _mix(tmp_path, {"path": str(music), "role": "music", "offset_seconds": 2.0})

    assert not result.success
    assert "offset_seconds" in result.error
