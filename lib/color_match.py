"""Color matching helpers for blending archival and AI footage.

Uses FFmpeg filters only (no paid tools). Scene-aware grading: archival
and AI sources get *different* profiles so hybrid cuts don't clash, and
the grade accounts for scene content (deep-space dark vs bright ocean
surface) instead of one LUT for everything.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

# Common documentary base: slight contrast/lift, photographic look.
BASE = "eq=contrast=1.04:saturation=1.02"

# Archival (NASA/undersea stock): often flat, low contrast, green/gray cast.
ARCH_DEFAULT = BASE + ",colorbalance=rs=-0.04:gs=0.00:bs=0.06:rm=0.03:gm=-0.01:bm=-0.02:rh=0.06:gh=0.00:bh=-0.04"
ARCH_DEEP = ARCH_DEFAULT + ",eq=brightness=-0.03:saturation=1.08"   # dark space/vent shots
ARCH_BRIGHT = ARCH_DEFAULT + ",eq=brightness=0.04:saturation=0.95"  # bright ice/ocean surface

# AI (Nano Banana photographic): already saturated, needs gentle alignment to archival.
AI_DEFAULT = BASE + ",colorbalance=rs=-0.02:gs=0.01:bs=-0.04:rm=-0.02:gm=0.00:bm=0.02:rh=0.04:gh=-0.01:bh=0.03"
AI_COOL = AI_DEFAULT + ",eq=brightness=-0.02:saturation=0.97"  # icy ocean planet

# Transitions between archival <-> AI at key junctions (~00:21-00:27, ~00:51-01:03, ~01:42-01:54).
TRANSITION_BRIDGE = BASE + ",colorbalance=rs=-0.03:gs=0.00:bs=0.02:rm=0.01:gm=0.00:bm=0.00:rh=0.05:gh=0.00:bh=-0.03"


def profile_for(source_type: str, scene_id: str, motion_type: str | None = None) -> str:
    """Pick a grade profile by source type and scene content."""
    dark_space = {"S002", "S008", "S015", "S027", "S028", "S029", "S038", "S040", "S041"}
    bright_ice = {"S003", "S005", "S006", "S016", "S017", "S018", "S019", "S034", "S035", "S036"}
    deep_sea = {"S007", "S010", "S011", "S031", "S033"}

    if source_type == "archival":
        if scene_id in deep_sea:
            return ARCH_DEFAULT
        if scene_id in dark_space:
            return ARCH_DEEP
        if scene_id in bright_ice:
            return ARCH_BRIGHT
        return ARCH_DEFAULT
    # ai_generated
    if scene_id in bright_ice or scene_id in {"S001", "S017", "S034", "S035", "S036"}:
        return AI_COOL
    return AI_DEFAULT


def grade(input_path: str | Path, output_path: str | Path, grade_filter: str) -> None:
    inp = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(inp), "-vf", grade_filter, "-frames:v", "1", str(out)],
        check=True, capture_output=True,
    )
