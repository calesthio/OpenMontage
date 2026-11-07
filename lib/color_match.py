"""Color matching helpers for blending archival and AI footage.

Uses FFmpeg filters only (no paid tools). Scene-aware grading: archival
and AI sources get *different* profiles so hybrid cuts don't clash, and
the grade accounts for scene content instead of one LUT for everything.

Scene category sets (dark_space / bright_ice / deep_sea) are parameters
with pilot defaults, so the helper is not tied to the first_video S-IDs.
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

# Transitions between archival <-> AI at key junctions.
TRANSITION_BRIDGE = BASE + ",colorbalance=rs=-0.03:gs=0.00:bs=0.02:rm=0.01:gm=0.00:bm=0.00:rh=0.05:gh=0.00:bh=-0.03"

# ---- Pilot-first_video defaults (overridable per episode) ----
DARK_SPACE_DEFAULT = {"S002", "S008", "S015", "S027", "S028", "S029", "S038", "S040", "S041"}
BRIGHT_ICE_DEFAULT = {"S003", "S005", "S006", "S016", "S017", "S018", "S019", "S034", "S035", "S036"}
DEEP_SEA_DEFAULT = {"S007", "S010", "S011", "S031", "S033"}

ARCH_PROFILES = {
    "default": ARCH_DEFAULT,
    "deep": ARCH_DEEP,
    "bright": ARCH_BRIGHT,
}
AI_PROFILES = {
    "default": AI_DEFAULT,
    "cool": AI_COOL,
}


def profile_for(
    source_type: str,
    scene_id: str,
    motion_type: str | None = None,
    *,
    dark_space: set[str] | None = None,
    bright_ice: set[str] | None = None,
    deep_sea: set[str] | None = None,
) -> str:
    """Pick a grade profile by source type and scene content.

    ``dark_space``/``bright_ice``/``deep_sea`` default to the pilot
    first_video scene sets; pass custom sets for a new episode.
    """
    ds = DARK_SPACE_DEFAULT if dark_space is None else dark_space
    bi = BRIGHT_ICE_DEFAULT if bright_ice is None else bright_ice
    de = DEEP_SEA_DEFAULT if deep_sea is None else deep_sea

    if source_type == "archival":
        if scene_id in de:
            return ARCH_PROFILES["default"]
        if scene_id in ds:
            return ARCH_PROFILES["deep"]
        if scene_id in bi:
            return ARCH_PROFILES["bright"]
        return ARCH_PROFILES["default"]
    # ai_generated
    if scene_id in bi or scene_id in {"S001", "S017", "S034", "S035", "S036"}:
        return AI_PROFILES["cool"]
    return AI_PROFILES["default"]


def grade(input_path: str | Path, output_path: str | Path, grade_filter: str) -> None:
    inp = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(inp), "-vf", grade_filter, "-frames:v", "1", str(out)],
        check=True, capture_output=True,
    )
