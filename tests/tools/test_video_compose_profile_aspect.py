"""Regression coverage for display aspect ratio in profile encoding."""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from tools.video.video_compose import VideoCompose


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available")
@pytest.mark.parametrize("sar,picture_height", [(1, 608), (2, 304)])
def test_encode_shorts_profile_preserves_display_aspect(tmp_path, sar, picture_height):
    source = tmp_path / "landscape.mp4"
    output = tmp_path / "shorts.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=white:s=160x90:r=1:d=1",
            "-vf", f"setsar={sar}",
            "-frames:v", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(source),
        ],
        check=True, capture_output=True,
    )

    result = VideoCompose().execute({
        "operation": "encode",
        "input_path": str(source),
        "output_path": str(output),
        "profile": "youtube_shorts",
        "preset": "ultrafast",
    })
    assert result.success, result.error

    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(output),
         "-frames:v", "1", "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    )
    stream = next(line for line in probe.stderr.splitlines() if "Video: h264" in line)
    assert re.search(r"1080x1920\s+\[SAR 1:1 DAR 9:16\]", stream)

    frame = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(output), "-frames:v", "1",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        check=True, capture_output=True,
    ).stdout
    assert len(frame) == 1080 * 1920
    active_rows = sum(frame[row * 1080 + 540] > 128 for row in range(1920))
    assert abs(active_rows - picture_height) <= 2
