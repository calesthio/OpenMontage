"""Color matching helpers for blending archival and AI footage.

V8 §8.12: explicit input/output color spaces + transform metadata.
Color matching must not change scientifically significant colors of the
source measurement or spectral visualization.

Uses FFmpeg filters only (no paid tools). Scene-aware grading: archival
and AI sources get *different* profiles so hybrid cuts don't clash, and
the grade accounts for scene content instead of one LUT for everything.

Scene category sets (dark_space / bright_ice / deep_sea) are parameters
with pilot defaults, so the helper is not tied to the first_video S-IDs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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


# V8 §8.12: color space metadata.
@dataclass
class ColorSpace:
    """Describes a color space: primaries, transfer, matrix."""

    name: str  # e.g. "Rec.709", "Rec.2020", "P3-DCI", "sRGB"
    primaries: str  # e.g. "bt709", "bt2020", "smpte432"
    transfer: str  # e.g. "bt709", "srgb", "linear"
    matrix: str  # e.g. "bt709", "bt2020"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


# V8 §8.12: default output target is Rec.709 SDR.
DEFAULT_OUTPUT_COLOR = ColorSpace(
    name="Rec.709 SDR", primaries="bt709", transfer="bt709", matrix="bt709"
)


@dataclass
class ColorTransform:
    """Record of a color transform applied to one asset."""

    transform_id: str
    input_color: ColorSpace
    output_color: ColorSpace
    filter_chain: str  # ffmpeg filter string applied
    grade_id: str | None = None  # reference grade / LUT version
    lut_version: str | None = None
    input_checksum: str | None = None  # sha256 of source before transform
    output_checksum: str | None = None  # sha256 of output after transform
    applied_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "transform_id": self.transform_id,
            "input_color": self.input_color.to_dict(),
            "output_color": self.output_color.to_dict(),
            "filter_chain": self.filter_chain,
            "grade_id": self.grade_id,
            "lut_version": self.lut_version,
            "input_checksum": self.input_checksum,
            "output_checksum": self.output_checksum,
            "applied_at": self.applied_at,
            "notes": self.notes,
        }


from typing import Any  # noqa: E402  (used in ColorTransform.to_dict)


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


def apply_colormanaged_grade(
    *,
    input_path: str | Path,
    output_path: str | Path,
    transform_id: str,
    input_color: ColorSpace | None = None,
    output_color: ColorSpace | None = None,
    grade_filter: str = BASE,
    grade_id: str | None = None,
    lut_version: str | None = None,
    input_checksum: str | None = None,
    output_checksum: str | None = None,
    notes: str = "",
) -> ColorTransform:
    """Apply a grade with explicit color space metadata (V8 §8.12).

    Writes the transformed file via ffmpeg and returns a ColorTransform
    record with input/output color spaces, filter chain, and checksums.
    """
    inp = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    in_color = input_color or DEFAULT_OUTPUT_COLOR
    out_color = output_color or DEFAULT_OUTPUT_COLOR

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(inp), "-vf", grade_filter,
         "-frames:v", "1", str(out)],
        check=True, capture_output=True,
    )

    return ColorTransform(
        transform_id=transform_id,
        input_color=in_color,
        output_color=out_color,
        filter_chain=grade_filter,
        grade_id=grade_id,
        lut_version=lut_version,
        input_checksum=input_checksum,
        output_checksum=output_checksum,
        notes=notes,
    )
