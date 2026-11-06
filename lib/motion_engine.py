"""Motion Engine — camera motion and transition specifications for still
images in the production pipeline.

Builds per-scene motion specs (pan/zoom/parallax) and transition specs that
the render stage consumes.  Integrates with tools/motion/motion_variety.py
for FFmpeg filter generation.  Ensures variety: no two consecutive scenes
use the identical move/easing/direction combination.

Zero-cost: pure data + ffmpeg filter strings.  No generation, no credits.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any

from tools.motion.motion_variety import (  # noqa: E402
    build_chapter_card,
    build_detail_crop,
    build_parallax,
    build_pan_zoom,
    build_subtitle_style,
    ease_curve,
    lint_variation,
)


@dataclass
class MotionSpec:
    """Motion specification for one scene."""

    scene_id: str
    move_type: str  # "pan_zoom", "detail_crop", "parallax", "static", "chapter_card"
    duration_seconds: float
    ffmpeg_filter: str | None = None
    easing: str = "easeinout"
    direction: str = "in"
    start_scale: float = 1.0
    end_scale: float = 1.12
    pan_x: float = 0.0
    pan_y: float = 0.0
    crop_box: tuple[float, float, float, float] | None = None
    parallax_layers: int = 1
    parallax_drift: float = 0.04
    chapter_title: str | None = None
    chapter_subtitle: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.crop_box is not None:
            d["crop_box"] = list(self.crop_box)
        return d


@dataclass
class TransitionSpec:
    """Transition specification between two scenes."""

    from_scene_id: str
    to_scene_id: str
    transition_type: str  # "cut", "dissolve", "fade", "wipe"
    duration_seconds: float
    ffmpeg_filter: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MotionPlan:
    """Complete motion plan for a manifest's scenes."""

    version: str = "1.0"
    run_id: str = ""
    fps: int = 30
    width: int = 1920
    height: int = 1080
    specs: list[MotionSpec] = field(default_factory=list)
    transitions: list[TransitionSpec] = field(default_factory=list)
    variety_issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "specs": [s.to_dict() for s in self.specs],
            "transitions": [t.to_dict() for t in self.transitions],
            "variety_issues": self.variety_issues,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class MotionEngine:
    """Generate motion specs and transitions for production manifest scenes.

    Ensures shot variety by rotating through move types and easing
    combinations so no two consecutive scenes are identical.
    """

    _MOVE_TYPES = ("pan_zoom", "detail_crop", "parallax", "static")
    _DIRECTIONS = ("in", "out")
    _EASINGS = ("linear", "easein", "easeout", "easeinout")
    _TRANSITIONS = ("cut", "dissolve", "fade", "wipe")

    def __init__(
        self,
        *,
        fps: int = 30,
        width: int = 1920,
        height: int = 1080,
        seed: int | None = None,
        force_variety: bool = True,
    ) -> None:
        self.fps = fps
        self.width = width
        self.height = height
        self._rng = random.Random(seed)
        self.force_variety = force_variety
        self._prev_move_key: tuple[str, str, str] | None = None

    # ------------------------------------------------------------------
    # Motion spec generation
    # ------------------------------------------------------------------

    def spec_for_scene(
        self,
        *,
        scene_id: str,
        duration_seconds: float,
        camera_move_hint: str | None = None,
        hero_moment: bool = False,
        narrative_role: str = "establish_context",
        preferred_move: str | None = None,
    ) -> MotionSpec:
        """Produce a MotionSpec for one scene.

        Args:
            scene_id: Scene identifier.
            duration_seconds: Planned on-screen duration.
            camera_move_hint: Hint from visual_director (e.g. "medium_close").
            hero_moment: If True, use a slower, more deliberate move.
            narrative_role: Scene's narrative role.
            preferred_move: Override the auto-selected move type.

        Returns:
            MotionSpec with an ffmpeg_filter string ready for the render
            stage.
        """
        move_type = preferred_move or self._select_move_type(narrative_role, hero_moment)
        easing, direction, start_scale, end_scale = self._select_params(
            move_type, hero_moment
        )

        # Build the ffmpeg filter string via motion_variety.
        ffmpeg_filter: str | None = None
        crop_box: tuple[float, float, float, float] | None = None
        parallax_layers = 1
        parallax_drift = 0.04
        chapter_title = None
        chapter_subtitle = None

        if move_type == "pan_zoom":
            ffmpeg_filter = build_pan_zoom(
                duration_s=duration_seconds,
                easing=easing,
                direction=direction,
                start_scale=start_scale,
                end_scale=end_scale,
                fps=self.fps,
            )
        elif move_type == "detail_crop":
            crop_box = self._detail_crop_box(narrative_role)
            ffmpeg_filter = build_detail_crop(
                duration_s=duration_seconds,
                crop_box=crop_box,
                fps=self.fps,
            )
        elif move_type == "parallax":
            parallax_layers = 2 if hero_moment else 1
            parallax_drift = 0.06 if hero_moment else 0.04
            ffmpeg_filter = build_parallax(
                duration_s=duration_seconds,
                layers=parallax_layers,
                drift=parallax_drift,
                fps=self.fps,
            )
        elif move_type == "static":
            ffmpeg_filter = None  # no motion filter; render uses static image
        elif move_type == "chapter_card":
            chapter_title = narrative_role.replace("_", " ").title()
            chapter_subtitle = "Scene " + scene_id.split("-")[-1]
            ffmpeg_filter = None  # chapter cards rendered by composer

        # Record the move key for variety enforcement.
        move_key = (move_type, easing, direction)
        self._prev_move_key = move_key

        return MotionSpec(
            scene_id=scene_id,
            move_type=move_type,
            duration_seconds=duration_seconds,
            ffmpeg_filter=ffmpeg_filter,
            easing=easing,
            direction=direction,
            start_scale=start_scale,
            end_scale=end_scale,
            crop_box=crop_box,
            parallax_layers=parallax_layers,
            parallax_drift=parallax_drift,
            chapter_title=chapter_title,
            chapter_subtitle=chapter_subtitle,
            metadata={
                "fps": self.fps,
                "resolution": f"{self.width}x{self.height}",
                "hero_moment": hero_moment,
                "narrative_role": narrative_role,
            },
        )

    def plan_motion(
        self,
        *,
        run_id: str,
        scenes: list[dict[str, Any]],
    ) -> MotionPlan:
        """Build a complete MotionPlan from a list of scene dicts.

        Each scene dict should contain scene_id, duration_seconds, and
        optionally camera_move_hint, hero_moment, narrative_role.
        """
        specs: list[MotionSpec] = []
        transitions: list[TransitionSpec] = []

        for i, scene in enumerate(scenes):
            sid = scene.get("scene_id", f"scene-{i:03d}")
            dur = float(scene.get("duration_seconds", 5.0))
            spec = self.spec_for_scene(
                scene_id=sid,
                duration_seconds=dur,
                camera_move_hint=scene.get("camera_move_hint"),
                hero_moment=scene.get("hero_moment", False),
                narrative_role=scene.get("narrative_role", "establish_context"),
                preferred_move=scene.get("preferred_move"),
            )
            specs.append(spec)

            # Transition to next scene.
            if i < len(scenes) - 1:
                next_scene = scenes[i + 1]
                ttype = self._select_transition(scene, next_scene)
                transitions.append(
                    TransitionSpec(
                        from_scene_id=sid,
                        to_scene_id=next_scene.get("scene_id", f"scene-{i+1:03d}"),
                        transition_type=ttype,
                        duration_seconds=scene.get("transition_duration", 0.5),
                    )
                )

        # Lint for variety issues.
        seg_dicts = [
            {
                "move": s.move_type,
                "easing": s.easing,
                "direction": s.direction,
            }
            for s in specs
        ]
        variety_issues = lint_variation(seg_dicts)

        return MotionPlan(
            version="1.0",
            run_id=run_id,
            fps=self.fps,
            width=self.width,
            height=self.height,
            specs=specs,
            transitions=transitions,
            variety_issues=variety_issues,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_move_type(
        self, narrative_role: str, hero_moment: bool
    ) -> str:
        """Choose a move type appropriate to the narrative role.

        Hero moments get slower, more deliberate moves (pan_zoom or static).
        Context-setting scenes get parallax or detail_crop for visual
        interest.  The choice is pseudo-random but seeded for reproducibility.
        """
        if self.force_variety and self._prev_move_key is not None:
            # Avoid repeating the exact same move/easing/direction.
            candidates = list(self._MOVE_TYPES)
            prev_move = self._prev_move_key[0]
            # If the previous move was pan_zoom, lean toward a different type
            # for this scene to preserve variety.
            if prev_move == "pan_zoom":
                candidates = [c for c in candidates if c != "pan_zoom"] or candidates
            return self._rng.choice(candidates)

        # Role-based defaults with randomization.
        if narrative_role in ("establish_context", "resolution"):
            return self._rng.choice(("parallax", "pan_zoom", "static"))
        if narrative_role in ("deliver_payload", "emotional_beat"):
            return "pan_zoom" if hero_moment else self._rng.choice(("pan_zoom", "detail_crop"))
        if narrative_role == "transition":
            return "static"
        return self._rng.choice(self._MOVE_TYPES)

    def _select_params(
        self, move_type: str, hero_moment: bool
    ) -> tuple[str, str, float, float]:
        """Return (easing, direction, start_scale, end_scale)."""
        easing = self._rng.choice(self._EASINGS)
        direction = self._rng.choice(self._DIRECTIONS)

        if hero_moment:
            # Slower, subtler zoom for hero moments.
            start_scale = 1.0
            end_scale = 1.06
        else:
            start_scale = 1.0
            end_scale = self._rng.uniform(1.08, 1.18)

        return easing, direction, start_scale, end_scale

    def _detail_crop_box(
        self, narrative_role: str
    ) -> tuple[float, float, float, float]:
        """Choose a detail-crop sub-box (x0, y0, x1, y1) in 0..1."""
        if narrative_role == "deliver_payload":
            # Center crop — focus on the key subject.
            return (0.35, 0.30, 0.65, 0.70)
        if narrative_role == "establish_context":
            # Upper-left detail.
            return (0.05, 0.05, 0.45, 0.45)
        return (0.25, 0.25, 0.75, 0.75)

    def _select_transition(
        self, from_scene: dict[str, Any], to_scene: dict[str, Any]
    ) -> str:
        """Choose a transition type between two scenes."""
        # Hero-to-hero or payload-to-payload gets a dissolve; routine cuts
        # get a hard cut.  Randomized but seeded.
        if from_scene.get("hero_moment") and to_scene.get("hero_moment"):
            return "dissolve"
        if self._rng.random() < 0.25:
            return self._rng.choice(("dissolve", "fade", "wipe"))
        return "cut"
