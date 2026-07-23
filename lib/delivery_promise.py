"""Delivery promise classifier.

Before provider selection, classify what the production is actually promising
to deliver. This prevents the most damaging failure mode: silently downgrading
from motion-led to still-led without the user knowing.

The delivery promise is set at the proposal stage and locked. If the compose
stage can't honor it, the system must stop and ask — not silently substitute.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any


class PromiseType(Enum):
    MOTION_LED = "motion_led"
    SOURCE_LED = "source_led"
    DATA_EXPLAINER = "data_explainer"
    TEACHER_EXPLAINER = "teacher_explainer"
    SCREEN_DEMO = "screen_demo"
    AVATAR_PRESENTER = "avatar_presenter"
    HYBRID = "hybrid"
    LOCALIZATION = "localization"


# Rules per promise type — what is and isn't acceptable
PROMISE_RULES: dict[str, dict[str, Any]] = {
    "motion_led": {
        "still_fallback_allowed": False,
        "requires_video_generation": True,
        "min_motion_ratio": 0.7,  # At least 70% of cuts must be real motion (video/animation, not Remotion slides)
        "description": "Video's quality depends on real motion — generated video clips, footage, or animation.",
    },
    "source_led": {
        "still_fallback_allowed": True,
        "requires_video_generation": False,
        "min_motion_ratio": 0.3,
        "description": "User-provided footage is the primary medium. Generated assets fill gaps only.",
    },
    "data_explainer": {
        "still_fallback_allowed": True,
        "requires_video_generation": False,
        "min_motion_ratio": 0.0,
        "description": "Data visualization and explanation. Motion graphics preferred but images acceptable.",
    },
    "teacher_explainer": {
        "still_fallback_allowed": True,
        "requires_video_generation": False,
        "min_motion_ratio": 0.0,
        "description": "Educational content. Clarity and comprehension over spectacle.",
    },
    "screen_demo": {
        "still_fallback_allowed": True,
        "requires_video_generation": False,
        "min_motion_ratio": 0.0,
        "description": "Screen recording or product demo. Legibility over cinematic dressing.",
    },
    "avatar_presenter": {
        "still_fallback_allowed": False,
        "requires_video_generation": True,
        "min_motion_ratio": 0.3,
        "description": "AI avatar or talking head presentation. Requires video generation for presenter.",
    },
    "hybrid": {
        "still_fallback_allowed": True,
        "requires_video_generation": False,
        "min_motion_ratio": 0.2,
        "description": "Mix of source footage, generated content, and graphics.",
    },
    "localization": {
        "still_fallback_allowed": True,
        "requires_video_generation": False,
        "min_motion_ratio": 0.0,
        "description": "Translation/dubbing of existing video. Preserving source timing and clarity.",
    },
}


@dataclass
class DeliveryPromise:
    """Classifies what the production promises to deliver."""

    promise_type: PromiseType
    motion_required: bool
    source_required: bool
    tone_mode: str          # "cinematic", "educational", "corporate", "playful", "raw"
    quality_floor: str      # "draft", "presentable", "broadcast"
    approved_fallback: str | None = None  # "animatic", "still_led", or None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["promise_type"] = self.promise_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeliveryPromise":
        return cls(
            promise_type=PromiseType(data["promise_type"]),
            motion_required=data.get("motion_required", False),
            source_required=data.get("source_required", False),
            tone_mode=data.get("tone_mode", "corporate"),
            quality_floor=data.get("quality_floor", "presentable"),
            approved_fallback=data.get("approved_fallback"),
        )

    def get_rules(self) -> dict[str, Any]:
        """Get the enforcement rules for this promise type."""
        return PROMISE_RULES.get(self.promise_type.value, {})

    def validate_cuts(self, cuts: list[dict]) -> dict[str, Any]:
        """Validate a list of edit cuts against this delivery promise.

        Returns a dict with 'valid', 'violations', and 'motion_ratio'.
        """
        rules = self.get_rules()
        violations = []

        if not cuts:
            return {"valid": False, "violations": ["No cuts provided"], "motion_ratio": 0.0}

        # Count motion vs slide-grammar vs still cuts.
        # Only real video/animation/avatar footage counts as motion.
        # Remotion component scenes (text_card, chart, kpi_grid, etc.) are
        # "animated slides" — they have transitions but are NOT real motion.
        _SLIDE_GRAMMAR_TYPES = frozenset({
            "text_card", "stat_card", "chart", "bar_chart",
            "line_chart", "pie_chart", "kpi_grid", "comparison",
            "progress", "callout",
        })
        _REAL_MOTION_TYPES = frozenset({"video", "animation", "avatar"})

        motion_cuts = 0
        slide_cuts = 0
        still_cuts = 0
        for cut in cuts:
            source = cut.get("source", "")
            cut_type = cut.get("type", "")

            # Determine category for this cut
            is_motion = False
            is_slide = False

            if source:
                ext = source.rsplit(".", 1)[-1].lower() if "." in source else ""
                if ext in ("mp4", "mov", "webm", "avi", "mkv"):
                    is_motion = True
            if cut_type in _REAL_MOTION_TYPES:
                is_motion = True
            elif cut_type in _SLIDE_GRAMMAR_TYPES:
                is_slide = True

            if is_motion:
                motion_cuts += 1
            elif is_slide:
                slide_cuts += 1
            else:
                still_cuts += 1

        total = motion_cuts + slide_cuts + still_cuts
        # Motion ratio is real motion vs everything — slide grammar does NOT count
        motion_ratio = motion_cuts / total if total > 0 else 0.0

        # Check motion requirement
        min_ratio = rules.get("min_motion_ratio", 0.0)
        if self.motion_required and motion_ratio < min_ratio:
            violations.append(
                f"Motion ratio {motion_ratio:.0%} is below minimum {min_ratio:.0%} "
                f"for {self.promise_type.value}. "
                f"{motion_cuts}/{total} cuts have real motion "
                f"({slide_cuts} are animated slides which do not count as motion)."
            )

        # Check still fallback (slides + stills both count as non-motion)
        non_motion = slide_cuts + still_cuts
        if not rules.get("still_fallback_allowed", True) and non_motion > total * 0.5:
            if self.approved_fallback != "still_led":
                violations.append(
                    f"{self.promise_type.value} does not allow still-led fallback, "
                    f"but {non_motion}/{total} cuts are non-motion (stills + animated slides). "
                    f"User must approve 'still_led' fallback or provide motion content."
                )

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "motion_ratio": motion_ratio,
            "motion_cuts": motion_cuts,
            "slide_cuts": slide_cuts,
            "still_cuts": still_cuts,
        }


def classify_from_brief(
    pipeline_type: str,
    user_intent: dict[str, Any],
) -> DeliveryPromise:
    """Classify delivery promise from pipeline type and user intent.

    This provides a sensible default. The proposal-director should refine
    it based on research and capability checks.

    Args:
        pipeline_type: Pipeline manifest name.
        user_intent: Dict with keys like 'motion_required', 'has_footage',
                     'tone', 'quality', 'platform'.
    """
    # Pipeline → default promise type mapping
    pipeline_defaults: dict[str, PromiseType] = {
        "cinematic": PromiseType.MOTION_LED,
        "animated-explainer": PromiseType.DATA_EXPLAINER,
        "animation": PromiseType.MOTION_LED,
        "talking-head": PromiseType.AVATAR_PRESENTER,
        "avatar-spokesperson": PromiseType.AVATAR_PRESENTER,
        "screen-demo": PromiseType.SCREEN_DEMO,
        "hybrid": PromiseType.HYBRID,
        "localization-dub": PromiseType.LOCALIZATION,
        "podcast-repurpose": PromiseType.SOURCE_LED,
        "clip-factory": PromiseType.SOURCE_LED,
    }

    promise_type = pipeline_defaults.get(pipeline_type, PromiseType.HYBRID)

    # Override with explicit user intent
    if user_intent.get("motion_required") is False and promise_type == PromiseType.MOTION_LED:
        promise_type = PromiseType.HYBRID

    source_required = user_intent.get("has_footage", False)
    if source_required and promise_type not in (PromiseType.SOURCE_LED, PromiseType.LOCALIZATION):
        promise_type = PromiseType.SOURCE_LED

    motion_required = user_intent.get("motion_required", promise_type in (
        PromiseType.MOTION_LED, PromiseType.AVATAR_PRESENTER,
    ))

    tone_mode = user_intent.get("tone", "corporate")
    quality_floor = user_intent.get("quality", "presentable")

    return DeliveryPromise(
        promise_type=promise_type,
        motion_required=motion_required,
        source_required=source_required,
        tone_mode=tone_mode,
        quality_floor=quality_floor,
    )
