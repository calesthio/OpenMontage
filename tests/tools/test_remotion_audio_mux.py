import shutil
import subprocess
from pathlib import Path

import pytest

from tools.video.video_compose import VideoCompose


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required",
)


def _run(command: list[str]) -> None:
    subprocess.run(command, capture_output=True, check=True, timeout=30)


def test_external_audio_mux_adds_audible_stream_without_changing_video_length(tmp_path) -> None:
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.wav"
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "color=c=red:s=320x180:d=2:r=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
    ])
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=1", str(audio),
    ])

    result = VideoCompose()._mux_external_audio(video, audio)

    assert result.success, result.error
    streams = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type", "-of", "csv=p=0", str(video),
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout.splitlines()
    duration = float(subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(video),
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout.strip())

    assert "video" in streams
    assert "audio" in streams
    assert duration == pytest.approx(2.0, abs=0.15)
