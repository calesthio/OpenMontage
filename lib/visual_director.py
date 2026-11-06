"""Visual Director — enforces shot variety, composition rules, and
readability constraints across a planned scene list.

All checks are structural and local: no generation, no credits spent.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VisualDirective:
    """Per-scene visual direction produced by the director."""

    scene_id: str
    shot_size: str
    camera_movement: str
    lens_mm: int
    lighting_key: str
    color_temperature: str
    depth_of_field: str
    composition_notes: str
    hero_space_reserved: bool  # space left for editor-added captions
    character_placement: str  # where character sits in frame
    environment_notes: str
    visual_idea_refinement: str
    # Stickman rig hints (optional, populated when stickman_aware=True)
    rig_pose_hint: str | None = None
    rig_expression_hint: str | None = None
    prop_continuity_note: str | None = None


@dataclass
class VisualDirectionReport:
    """Summary of visual direction across all scenes."""

    version: str = "1.0"
    total_scenes: int = 0
    shot_size_distribution: dict[str, int] = field(default_factory=dict)
    movement_distribution: dict[str, int] = field(default_factory=dict)
    lighting_distribution: dict[str, int] = field(default_factory=dict)
    variety_score: float = 0.0  # 0-5, lower = more repetitive
    directives: list[VisualDirective] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    passed: bool = False


# ---------------------------------------------------------------------------
# Shot variety rules
# ---------------------------------------------------------------------------

_SHOT_SEQUENCE_VARIETY = {
    "wide": ["medium", "medium_close", "close_up", "extreme_close_up"],
    "medium": ["wide", "close_up", "extreme_close_up", "medium_close"],
    "medium_close": ["wide", "medium", "close_up", "extreme_close_up"],
    "close_up": ["wide", "medium", "medium_close", "extreme_wide"],
    "extreme_close_up": ["wide", "medium", "medium_close"],
}

_ENVIRONMENT_VARIETY = (
    "interior laboratory",
    "exterior landscape",
    "abstract data space",
    "close detail surface",
    "wide establishing vista",
    "macro texture field",
)


def _captains_log_variety(directives: list[VisualDirective]) -> float:
    """Return a repetition score (0-5, lower = more varied)."""
    issues = 0
    sizes = [d.shot_size for d in directives]
    if sizes:
        most_common = Counter(sizes).most_common(1)[0]
        if most_common[1] / len(sizes) > 0.5:
            issues += 1
    # Consecutive same size
    run = 1
    longest = 1
    for i in range(1, len(sizes)):
        if sizes[i] == sizes[i - 1]:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    if longest >= 3:
        issues += 1
    # Movement variety
    movements = [d.camera_movement for d in directives]
    static_pct = sum(1 for m in movements if m == "static") / len(movements) if movements else 0
    if static_pct > 0.6:
        issues += 1
    return min(5.0, issues * 1.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class VisualDirector:
    """Apply visual direction rules to every scene in a plan."""

    def __init__(self, visual_style: str = "bold ink illustration", stickman_aware: bool = False) -> None:
        self.visual_style = visual_style
        self.stickman_aware = stickman_aware

    def direct(
        self,
        scenes: list[dict[str, Any]],
        characters: list[str] | None = None,
    ) -> VisualDirectionReport:
        """Produce per-scene visual directives and a variety report."""
        characters = characters or []
        directives: list[VisualDirective] = []

        prev_size: str | None = None
        for idx, scene in enumerate(scenes):
            scene_id = scene.get("scene_id", f"scene-{idx:03d}")
            shot_size = scene.get("shot_size", "medium")
            movement = scene.get("camera_movement", "static")
            lens = scene.get("lens_mm", 35)
            lighting = scene.get("lighting_key", "natural")
            color_temp = scene.get("color_temperature", "neutral")
            dof = scene.get("depth_of_field", "deep")
            composition = scene.get("composition", "balanced")

            # Ensure shot size variety: avoid 3+ identical consecutive sizes.
            if prev_size is not None and shot_size == prev_size:
                # Force a different size from the allowed next set.
                allowed = _SHOT_SEQUENCE_VARIETY.get(shot_size, ["wide", "close_up"])
                shot_size = allowed[idx % len(allowed)]

            # Hero space: reserve bottom third for editor-added captions.
            hero_space = True

            # Character placement depends on shot size.
            if shot_size in ("close_up", "extreme_close_up"):
                placement = "face centered, eyes at upper third line"
            elif shot_size in ("medium", "medium_close"):
                placement = "waist-up centered, headroom for captions"
            else:
                placement = "small figure in environment, rule of thirds"

            env = _ENVIRONMENT_VARIETY[idx % len(_ENVIRONMENT_VARIETY)]

            # Stickman rig hints (only when enabled).
            rig_pose_hint = None
            rig_expression_hint = None
            prop_continuity_note = None
            if self.stickman_aware:
                poses = ["idle", "explaining", "pointing", "examining", "thinking", "interacting"]
                rig_pose_hint = poses[idx % len(poses)]
                rig_expression_hint = "curious" if idx % 2 == 0 else "focused"
                prop_continuity_note = "maintain prop ownership across cuts"

            refinement = (
                f"{self.visual_style}; {composition}; "
                f"{lighting} lighting; {dof} depth; "
                f"bottom third clear for captions"
            )

            directives.append(
                VisualDirective(
                    scene_id=scene_id,
                    shot_size=shot_size,
                    camera_movement=movement,
                    lens_mm=lens,
                    lighting_key=lighting,
                    color_temperature=color_temp,
                    depth_of_field=dof,
                    composition_notes=composition,
                    hero_space_reserved=hero_space,
                    character_placement=placement,
                    environment_notes=env,
                    visual_idea_refinement=refinement,
                    rig_pose_hint=rig_pose_hint,
                    rig_expression_hint=rig_expression_hint,
                    prop_continuity_note=prop_continuity_note,
                )
            )
            prev_size = shot_size

        report = VisualDirectionReport(
            total_scenes=len(directives),
            shot_size_distribution=dict(Counter(d.shot_size for d in directives)),
            movement_distribution=dict(Counter(d.camera_movement for d in directives)),
            lighting_distribution=dict(Counter(d.lighting_key for d in directives)),
            variety_score=_captains_log_variety(directives),
            directives=directives,
        )

        # Decide pass/fail
        issues: list[str] = []
        if report.variety_score > 2.0:
            issues.append("Shot variety below threshold — scenes feel repetitive")
        if report.total_scenes > 0:
            most_common_size = Counter(d.shot_size for d in directives).most_common(1)[0]
            if most_common_size[1] / report.total_scenes > 0.6:
                issues.append(f"Shot size '{most_common_size[0]}' dominates plan")
        # Distant-section repetition: same (shot_size, placement, environment) with only text swapped.
        seen_triples: set[tuple[str, str, str]] = set()
        distant_repeats = 0
        for d in directives:
            key = (d.shot_size, d.character_placement, d.environment_notes)
            if key in seen_triples:
                distant_repeats += 1
            seen_triples.add(key)
        if distant_repeats > max(1, report.total_scenes // 4):
            issues.append("Distant-section composition repetition detected")
        report.issues = issues
        report.passed = len(issues) == 0
        return report

    def to_dict(self, report: VisualDirectionReport) -> dict[str, Any]:
        return {
            "version": report.version,
            "total_scenes": report.total_scenes,
            "shot_size_distribution": report.shot_size_distribution,
            "movement_distribution": report.movement_distribution,
            "lighting_distribution": report.lighting_distribution,
            "variety_score": report.variety_score,
            "directives": [
                {
                    "scene_id": d.scene_id,
                    "shot_size": d.shot_size,
                    "camera_movement": d.camera_movement,
                    "lens_mm": d.lens_mm,
                    "lighting_key": d.lighting_key,
                    "color_temperature": d.color_temperature,
                    "depth_of_field": d.depth_of_field,
                    "composition_notes": d.composition_notes,
                    "hero_space_reserved": d.hero_space_reserved,
                    "character_placement": d.character_placement,
                    "environment_notes": d.environment_notes,
                    "visual_idea_refinement": d.visual_idea_refinement,
                    "rig_pose_hint": d.rig_pose_hint,
                    "rig_expression_hint": d.rig_expression_hint,
                    "prop_continuity_note": d.prop_continuity_note,
                }
                for d in report.directives
            ],
            "issues": report.issues,
            "passed": report.passed,
        }
