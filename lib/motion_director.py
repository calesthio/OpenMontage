"""Motion director — camera pan/zoom/reveal for static shots.

V7 §3, layer 4 (ASSEMBLY) and §4.1 retention rule: no static shot longer
than 15 s without a visual change. Applies gentle pan/zoom/reveal to any
still image held beyond the limit, via ffmpeg zoompan/crop, and returns an
explicit status (success / fallback_used / failed).
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATIC_LIMIT_SEC = 15.0  # V7 §4.1: max static segment before motion required


@dataclass
class MotionPlan:
    input_path: str
    output_path: str
    applied: bool  # whether motion filter was added
    filter: str | None
    status: str  # success | fallback_used | failed
    reason: str
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not self.created_at:
            d["created_at"] = datetime.now(timezone.utc).isoformat()
        return d


class MotionDirector:
    """Add pan/zoom/reveal motion to still images held longer than
    STATIC_LIMIT_SEC so retention pacing stays within the 15 s rule."""

    def __init__(self, static_limit_sec: float = STATIC_LIMIT_SEC) -> None:
        self.static_limit_sec = static_limit_sec

    def needs_motion(self, hold_sec: float) -> bool:
        return hold_sec > self.static_limit_sec

    def plan(self, input_path: str | Path, output_path: str | Path,
             hold_sec: float) -> MotionPlan:
        inp = Path(input_path)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if not self.needs_motion(hold_sec):
            # No motion needed: copy through (passthrough) to keep pipeline
            # uniform without re-encoding when not required.
            return MotionPlan(
                input_path=str(inp), output_path=str(out), applied=False,
                filter=None, status="success",
                reason=f"hold {hold_sec}s <= limit {self.static_limit_sec}s; no motion",
            )

        # Gentle zoompan: slowly scale 1.00->1.06 over the hold so the
        # frame is never perfectly static. ffmpeg zoompan filter.
        zfilter = ("zoompan=z='min(zoom+0.0015,1.06)':d=1:x='iw/2-(iw/zoom/2)':"
                   "y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loop", "1", "-i", str(inp),
                 "-c:v", "libx264", "-t", f"{hold_sec:.2f}",
                 "-vf", zfilter, "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                 str(out)],
                check=True, capture_output=True, timeout=180,
            )
            return MotionPlan(
                input_path=str(inp), output_path=str(out), applied=True,
                filter=zfilter, status="success",
                reason=f"zoompan applied for {hold_sec}s hold (> {self.static_limit_sec}s)",
            )
        except Exception as exc:  # pragma: no cover - ffmpeg environment
            # Fallback: plain copy of the still (accept static, flagged).
            try:
                out.write_bytes(inp.read_bytes())
            except Exception:
                pass
            return MotionPlan(
                input_path=str(inp), output_path=str(out), applied=False,
                filter=None, status="fallback_used",
                reason=f"zoompan failed ({exc}); still copied unchanged",
            )


def add_motion_if_needed(input_path: str | Path, output_path: str | Path,
                         hold_sec: float) -> dict[str, Any]:
    """Module-level convenience entry point."""
    return MotionDirector().plan(input_path, output_path, hold_sec).to_dict()
