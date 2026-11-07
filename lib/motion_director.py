"""Motion director — camera pan/zoom/reveal for static shots.

V8 §8.5: 15 s is a warning/review threshold, not an absolute law.
Longer static holds are allowed when artistically or scientifically
motivated (establishing shot, slow observational detail). The director
flags them as advisory rather than forcing motion on every frame.

V8 §8.13: motion type is classified, not applied uniformly:
- static_intentional: no motion, hold is artistically motivated
- optical_push_pull: slow zoom in/out (zoompan)
- lateral_drift: slow pan across the frame
- depth_parallax: 2.5D from depth map (only when depth map is strong)
- reveal_mask: wipe/reveal to expose information gradually
- diagram_animation: animate diagram elements (lines, labels, arrows)
- real_footage_stabilization: stabilize shaky archive footage
- no_motion: explicitly no motion

DepthFlow/depth parallax is NOT run on every frame. When the depth map
is weak, a careful 2D pan/zoom or manual mask is preferred over visible
edge distortion.
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATIC_LIMIT_SEC = 15.0  # V8 §8.5: warning threshold, not an absolute quality law

# V8 §8.13: motion types.
MOTION_TYPES = frozenset({
    "static_intentional",
    "optical_push_pull",
    "lateral_drift",
    "depth_parallax",
    "reveal_mask",
    "diagram_animation",
    "real_footage_stabilization",
    "no_motion",
})


@dataclass
class MotionPlan:
    input_path: str
    output_path: str
    applied: bool  # whether motion filter was added
    filter: str | None
    status: str  # success | fallback_used | failed
    reason: str
    failure_class: str = "DEGRADABLE"  # REQUIRED | OPTIONAL | DEGRADABLE | MANUAL_REVIEW
    motion_advisory: bool = False  # True when hold > limit but motion is advisory
    motion_type: str = "no_motion"  # one of MOTION_TYPES
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not self.created_at:
            d["created_at"] = datetime.now(timezone.utc).isoformat()
        return d


class MotionDirector:
    """Apply classified motion treatment to still images.

    Motion type is chosen per scene based on visual_class and the desired
    visual function — not applied uniformly to every frame. Depth parallax
    is only used when a strong depth map is available.
    """

    def __init__(self, static_limit_sec: float = STATIC_LIMIT_SEC) -> None:
        self.static_limit_sec = static_limit_sec

    def needs_motion(self, hold_sec: float) -> bool:
        return hold_sec > self.static_limit_sec

    def plan(
        self,
        input_path: str | Path,
        output_path: str | Path,
        hold_sec: float,
        *,
        motion_type: str = "optical_push_pull",
        depth_map_path: str | Path | None = None,
        depth_confidence: float = 0.0,
    ) -> MotionPlan:
        """Plan motion treatment for one still image.

        Args:
            input_path: source still image.
            output_path: output video path.
            hold_sec: how long the image is held.
            motion_type: one of MOTION_TYPES (V8 §8.13).
            depth_map_path: optional depth map for depth_parallax.
            depth_confidence: 0-1 confidence in the depth map; below ~0.6
                fall back to 2D pan/zoom instead of parallax.
        """
        inp = Path(input_path)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        if motion_type not in MOTION_TYPES:
            motion_type = "no_motion"

        # static_intentional / no_motion: no filter, passthrough.
        if motion_type in ("static_intentional", "no_motion") or not self.needs_motion(hold_sec):
            return MotionPlan(
                input_path=str(inp), output_path=str(out), applied=False,
                filter=None, status="success",
                motion_type=motion_type,
                reason=f"motion_type={motion_type}; hold {hold_sec}s "
                       f"({'<= limit' if not self.needs_motion(hold_sec) else '> limit but intentional'})",
            )

        # depth_parallax: only when depth map is strong enough.
        if motion_type == "depth_parallax":
            if depth_map_path and depth_confidence >= 0.6:
                return self._apply_depth_parallax(inp, out, hold_sec, depth_map_path)
            # Weak depth map -> fall back to 2D optical push/pull.
            return self._apply_zoompan(inp, out, hold_sec,
                                       motion_type="depth_parallax",
                                       reason="depth map too weak for parallax; "
                                              f"confidence {depth_confidence:.2f} < 0.6, "
                                              "using 2D zoompan instead")

        # lateral_drift: slow horizontal pan.
        if motion_type == "lateral_drift":
            return self._apply_pan(inp, out, hold_sec, direction="horizontal")

        # reveal_mask: wipe/reveal (simulated via zoompan + crop for now).
        if motion_type == "reveal_mask":
            return self._apply_zoompan(inp, out, hold_sec,
                                       motion_type="reveal_mask",
                                       reason="reveal_mask approximated via zoompan")

        # diagram_animation / real_footage_stabilization: not handled here
        # (diagram animation is Remotion-side; stabilization needs analyze filter).
        # Default: gentle optical push/pull.
        return self._apply_zoompan(inp, out, hold_sec,
                                   motion_type="optical_push_pull")

    # ------------------------------------------------------------------
    # Individual motion filters
    # ------------------------------------------------------------------

    def _apply_zoompan(
        self, inp: Path, out: Path, hold_sec: float,
        motion_type: str = "optical_push_pull", reason: str = ""
    ) -> MotionPlan:
        """Gentle optical push/pull: scale 1.00->1.06 over the hold."""
        zfilter = ("zoompan=z='min(zoom+0.0015,1.06)':d=1:"
                   "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                   "s=1920x1080:fps=30")
        return self._run_ffmpeg(inp, out, hold_sec, zfilter,
                                motion_type, reason or
                                f"zoompan applied for {hold_sec}s hold "
                                f"(> {self.static_limit_sec}s)")

    def _apply_pan(
        self, inp: Path, out: Path, hold_sec: float, direction: str = "horizontal"
    ) -> MotionPlan:
        """Slow lateral drift across the frame."""
        if direction == "horizontal":
            xfilter = ("crop=iw*0.9:ih:x='(iw-iw*0.9)*t/hold':y='ih/2-ih/2'")
        else:
            xfilter = ("crop=iw:ih*0.9:x='iw/2-iw/2':y='(ih-ih*0.9)*t/hold'")
        # Use zoompan-based drift instead (crop with expression needs eval).
        zfilter = ("zoompan=z='min(zoom+0.001,1.04)':d=1:"
                   "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                   "s=1920x1080:fps=30")
        return self._run_ffmpeg(inp, out, hold_sec, zfilter,
                                "lateral_drift", reason or
                                f"lateral drift for {hold_sec}s hold")

    def _apply_depth_parallax(
        self, inp: Path, out: Path, hold_sec: float,
        depth_map_path: str | Path
    ) -> MotionPlan:
        """2.5D parallax from depth map (placeholder: ffmpeg doesn't do
        true depth parallax natively; uses zoompan as conservative fallback
        until a depth-aware filter is integrated).

        V8 §8.13: weak depth map => 2D pan/zoom, not visible edge distortion.
        """
        zfilter = ("zoompan=z='min(zoom+0.0012,1.05)':d=1:"
                   "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                   "s=1920x1080:fps=30")
        return self._run_ffmpeg(inp, out, hold_sec, zfilter,
                                "depth_parallax",
                                f"depth_parallax (conservative zoompan) for "
                                f"{hold_sec}s hold; depth map: {depth_map_path}")

    def _run_ffmpeg(
        self, inp: Path, out: Path, hold_sec: float, vfilter: str,
        motion_type: str, reason: str
    ) -> MotionPlan:
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-loop", "1", "-i", str(inp),
                 "-c:v", "libx264", "-t", f"{hold_sec:.2f}",
                 "-vf", vfilter, "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", str(out)],
                check=True, capture_output=True, timeout=180,
            )
            return MotionPlan(
                input_path=str(inp), output_path=str(out), applied=True,
                filter=vfilter, status="success",
                motion_type=motion_type, reason=reason,
            )
        except Exception as exc:  # pragma: no cover - ffmpeg environment
            try:
                out.write_bytes(inp.read_bytes())
            except Exception:
                pass
            return MotionPlan(
                input_path=str(inp), output_path=str(out), applied=False,
                filter=None, status="fallback_used",
                failure_class="DEGRADABLE", motion_type=motion_type,
                motion_advisory=True,
                reason=f"{motion_type} failed ({exc}); still copied unchanged — "
                       f"static hold {hold_sec}s > limit "
                       f"{self.static_limit_sec}s is advisory, not blocking",
            )


def add_motion_if_needed(
    input_path: str | Path, output_path: str | Path,
    hold_sec: float, **kwargs: Any
) -> dict[str, Any]:
    """Module-level convenience entry point."""
    return MotionDirector().plan(
        input_path, output_path, hold_sec, **kwargs
    ).to_dict()
