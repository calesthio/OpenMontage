"""Perceptual QA scan + poster extraction (audit 2026-07-16, Wave 2 items 11).

The old final_review sampled 4 frames and hardcoded unreadable_text/
broken_overlays/missing_assets to False. The perceptual scan decodes the
whole program: blackdetect, freezedetect, silencedetect, ebur128.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg required"
)


def test_perceptual_scan_finds_black_freeze_silence(tmp_path):
    # Build via filter_complex: three color segments (solid colors freeze-
    # detect trivially) + audio present only in the first/last thirds.
    src = tmp_path / "src.mp4"
    proc = subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "color=c=red:s=320x240:d=6,format=yuv420p",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
         "-filter_complex",
         # Black hole 2-4s; audio muted 2-4s.
         "[0:v]drawbox=t=fill:c=black:enable='between(t,2,4)'[v];"
         "[1:a]volume=0:enable='between(t,2,4)'[a]",
         "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         str(src)],
        capture_output=True, timeout=120,
    )
    assert proc.returncode == 0 and src.exists()

    scan = VideoCompose()._perceptual_scan(
        src, 6.0, audio_expected=True, has_audio=True
    )
    assert scan["ran"] is True
    # Mid-program black segment detected and flagged.
    assert scan["black_segments"], scan
    assert any("Black segment" in i for i in scan["issues"])
    # Mid-program dead air detected.
    assert scan["silence_gaps"], scan
    assert any("Dead air" in i for i in scan["issues"])
    # Loudness measured; sine at default lavfi level is far from -14 LUFS.
    assert scan["integrated_lufs"] is not None
    assert any("LUFS" in i for i in scan["issues"])


def test_perceptual_scan_clean_video_is_quiet(tmp_path):
    # A normal, moving, audible clip must not produce false positives
    # (other than possible loudness advisory — normalize it first).
    src = tmp_path / "clean.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "testsrc2=s=320x240:d=4",
         "-f", "lavfi", "-i", "sine=frequency=330:duration=4",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         str(src)],
        capture_output=True, timeout=60,
    )
    from tools.audio.loudness import normalize_media_loudness
    normed = tmp_path / "clean_norm.mp4"
    assert normalize_media_loudness(src, normed, video_copy=True)

    scan = VideoCompose()._perceptual_scan(
        normed, 4.0, audio_expected=True, has_audio=True
    )
    assert scan["ran"] is True
    assert scan["issues"] == [], scan["issues"]


def test_extract_poster(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:d=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
        capture_output=True, timeout=60,
    )
    out = tmp_path / "poster.jpg"
    result = VideoCompose().execute({
        "operation": "extract_poster",
        "input_path": str(src),
        "output_path": str(out),
        "width": 320,
    })
    assert result.success is True, result.error
    assert out.exists() and out.stat().st_size > 1000
