"""Two-pass EBU R128 loudness normalization (ffmpeg loudnorm).

Shared by audio_mixer (final mix normalization) and video_compose (Remotion
renders, whose audio previously shipped completely unprocessed — audit
2026-07-16, Wave 1 ①).

Why two passes: single-pass loudnorm runs in *dynamic* mode — a time-varying
gain that audibly pumps on program material, and it resamples output to
192 kHz as a side effect. The correct form measures first, then applies a
linear (constant) gain with the measured values.

Target: -14 LUFS integrated / -1.5 dBTP — the YouTube normalization target
and the safest single default across platforms (TikTok/IG sit slightly
hotter; they turn tracks down, which is lossless, whereas quieter uploads
get no boost on YouTube).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

TARGET_I = -14.0
TARGET_TP = -1.5
TARGET_LRA = 11.0
OUTPUT_SAMPLE_RATE = 48000


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=True,
    )


def measure_loudness(input_path: Path | str, timeout: int = 600) -> Optional[dict[str, Any]]:
    """First pass: measure loudness. Returns loudnorm's JSON stats or None.

    ffmpeg prints the JSON block to stderr after the progress output; find it
    by scanning for the last {...} blob.
    """
    try:
        proc = _run([
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(input_path),
            "-af", f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
            "-f", "null", "-",
        ], timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    matches = re.findall(r"\{[^{}]*\}", proc.stderr or "")
    for blob in reversed(matches):
        if "input_i" in blob:
            try:
                return json.loads(blob)
            except json.JSONDecodeError:
                continue
    return None


def loudnorm_filter(measured: Optional[dict[str, Any]]) -> str:
    """The second-pass (or best-effort single-pass) loudnorm filter string."""
    base = f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}"
    if not measured:
        return base  # dynamic-mode fallback — still better than nothing
    return (
        f"{base}"
        f":measured_I={measured['input_i']}"
        f":measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}"
        f":measured_thresh={measured['input_thresh']}"
        f":offset={measured.get('target_offset', '0.0')}"
        f":linear=true"
    )


def normalize_media_loudness(
    input_path: Path | str,
    output_path: Path | str,
    *,
    video_copy: bool = False,
    timeout: int = 600,
) -> bool:
    """Two-pass normalize `input_path`'s audio into `output_path`.

    video_copy=True remuxes a video file with `-c:v copy` (audio-only
    re-encode — cheap even on a long render). Returns False when anything
    fails; callers treat normalization as best-effort polish, never as a
    reason to fail a render that already exists.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    measured = measure_loudness(input_path, timeout=timeout)
    af = f"{loudnorm_filter(measured)},aresample={OUTPUT_SAMPLE_RATE}"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", str(input_path), "-af", af]
    if video_copy:
        cmd += [
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            # Color metadata is writable even on a stream copy. Remotion tags
            # colorspace (via --color-space=bt709) but leaves primaries/trc
            # unset; every ffmpeg encode path in video_compose tags all three,
            # so complete them here rather than ship a half-tagged deliverable.
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        ]
    else:
        cmd += ["-ar", str(OUTPUT_SAMPLE_RATE)]
    cmd.append(str(output_path))
    try:
        _run(cmd, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    return output_path.exists()
