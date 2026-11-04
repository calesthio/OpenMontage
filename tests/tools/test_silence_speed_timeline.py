"""Native source-region and PCM controls for documented silence speed-up."""
from __future__ import annotations

import array
import itertools
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.video.silence_cutter import SilenceCutter

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="native FFmpeg and FFprobe required",
)


def command(args: list[str]) -> bytes:
    return subprocess.check_output(args, stderr=subprocess.PIPE)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "regions.mp4"
    command([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
        "color=red:s=64x64:r=50:d=3", "-f", "lavfi", "-i",
        "aevalsrc=if(between(t\\,1\\,2)\\,0\\,0.3*sin(2*PI*440*t)):s=48000:d=3",
        "-vf", ("drawbox=x=0:y=0:w=iw:h=ih:color=green:t=fill:enable='between(t,1,1.999)',"
        "drawbox=x=0:y=0:w=iw:h=ih:color=blue:t=fill:enable='gte(t,2)'"),
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path),
    ])
    return path


def regions(path: Path) -> list[tuple[str, int]]:
    raw = command([
        "ffmpeg", "-v", "error", "-i", str(path), "-vf", "scale=1:1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ])
    names = ["RGB"[max(range(3), key=lambda j: raw[i + j])]
             for i in range(0, len(raw), 3)]
    return [(name, len(list(group))) for name, group in itertools.groupby(names)]


def rms(path: Path, start: float) -> float:
    raw = command([
        "ffmpeg", "-v", "error", "-ss", str(start), "-i", str(path),
        "-t", "0.04", "-f", "s16le", "-acodec", "pcm_s16le", "-",
    ])
    samples = array.array("h", raw)
    return math.sqrt(sum(x * x for x in samples) / len(samples))


@pytest.mark.parametrize("factor,padding", [(2, 0), (2, .08), (2, .2), (1.5, .08), (6, .08)])
def test_speed_up_keeps_ordered_source_regions_once(
    tmp_path: Path, source: Path, factor: float, padding: float,
) -> None:
    out = tmp_path / "speed.mp4"
    result = SilenceCutter().execute({
        "input_path": str(source), "output_path": str(out), "mode": "speed_up",
        "silence_speed_factor": factor, "padding_seconds": padding,
        "min_silence_duration": .3,
    })
    assert result.success, result.error
    runs = regions(out)
    assert [name for name, _ in runs] == ["R", "G", "B"], runs
    assert abs(runs[0][1] - 50) <= 3
    assert abs(runs[2][1] - 50) <= 3
    expected_silence = 2 * padding + (1 - 2 * padding) / factor
    assert abs(runs[1][1] / 50 - expected_silence) <= .07
    assert rms(out, .3) > 1000
    assert rms(out, 1.1) < 100
    assert rms(out, 2 + expected_silence - .3) > 1000


def test_remove_mode_retains_only_speech(tmp_path: Path, source: Path) -> None:
    out = tmp_path / "cut.mp4"
    result = SilenceCutter().execute({
        "input_path": str(source), "output_path": str(out), "mode": "remove",
        "padding_seconds": 0, "min_silence_duration": .3,
    })
    assert result.success, result.error
    assert [name for name, _ in regions(out)] == ["R", "B"]


def test_mark_mode_retains_source_coordinates(tmp_path: Path, source: Path) -> None:
    out = tmp_path / "marks.json"
    result = SilenceCutter().execute({
        "input_path": str(source), "output_path": str(out), "mode": "mark",
        "padding_seconds": .08, "min_silence_duration": .3,
    })
    assert result.success, result.error
    data = json.loads(out.read_text())
    assert data["silences"][0]["start"] == pytest.approx(1, abs=.03)
    assert data["silences"][0]["end"] == pytest.approx(2, abs=.03)
    assert data["speech_segments"][0]["end"] == pytest.approx(1.08, abs=.03)
    assert data["speech_segments"][1]["start"] == pytest.approx(1.92, abs=.03)


def test_no_silence_returns_original_source(tmp_path: Path) -> None:
    path = tmp_path / "tone.mp4"
    command([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
        "color=red:s=64x64:r=20:d=1", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=1", "-c:v", "libx264", "-c:a", "aac",
        "-shortest", str(path),
    ])
    original = path.read_bytes()
    result = SilenceCutter().execute({"input_path": str(path), "mode": "speed_up"})
    assert result.success, result.error
    assert result.artifacts == [str(path)]
    assert path.read_bytes() == original
