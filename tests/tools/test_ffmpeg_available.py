"""Tests that FFmpeg / FFprobe are available in the project environment.

These are runtime prerequisites for video_compose, finish_audio, qc and
render_integration.  Zero-cost: only probes, no encoding.
"""

from __future__ import annotations

import subprocess

import pytest


def test_ffmpeg_available():
    try:
        out = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        pytest.fail("ffmpeg binary not found on PATH")
    assert out.returncode == 0, out.stderr
    assert "ffmpeg version" in out.stdout or "ffmpeg version" in out.stderr


def test_ffprobe_available():
    try:
        out = subprocess.run(
            ["ffprobe", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        pytest.fail("ffprobe binary not found on PATH")
    assert out.returncode == 0, out.stderr
    assert "ffprobe version" in out.stdout or "ffprobe version" in out.stderr


def test_ffprobe_decodes_a_wav(tmp_path):
    wav = tmp_path / "tone.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=0.5:sample_rate=22050",
            "-c:a", "pcm_s16le",
            str(wav),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=60,
    )
    assert wav.exists() and wav.stat().st_size > 0
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(wav)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    duration = float(out.stdout.strip())
    assert 0.4 < duration < 0.6
