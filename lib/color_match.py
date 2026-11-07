"""Color matching helpers for blending archival and AI footage.

Uses FFmpeg filters only (no paid tools). Provides a common grade so
archival clips and AI frames share a similar tone.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# A mild common grade: cool teal shadows, warm highlights, slight contrast.
COMMON_GRADE = (
    "eq=contrast=1.06:saturation=1.05,"
    "colorbalance=rs=-0.08:gs=-0.02:bs=0.10:"
    "rm=0.05:gm=0.00:bm=-0.05:"
    "rh=0.10:gh=0.02:bh=-0.08"
)


def grade(input_path: str | Path, output_path: str | Path, grade_filter: str = COMMON_GRADE) -> None:
    inp = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(inp), "-vf", grade_filter, "-frames:v", "1", str(out)],
        check=True, capture_output=True,
    )
