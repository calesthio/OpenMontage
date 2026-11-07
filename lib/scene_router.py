"""Scene router — visual class assignment per scene.

V8 §8.9: replaces the binary archival vs ai_generated split with six visual
classes: REAL_ARCHIVE, DATA_VISUALIZATION, SCIENTIFIC_DIAGRAM,
SCIENTIFIC_RECONSTRUCTION, HYPOTHETICAL_RECONSTRUCTION, ARTISTIC_METAPHOR.
The legacy ``source_type`` (archival | ai_generated) is retained for
backward compatibility and derived from the visual class.

Routes each scene to a source type and returns an explicit status
(success / fallback_used / failed). Reuses
lib.footage_sourcing provenance conventions and lib.color_match profiles.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.budget_guard import guard
from lib.storyboard import VISUAL_CLASSES

# Legacy binary split -> visual class mapping (backward compatible).
_SOURCE_TYPE_TO_CLASS = {
    "archival": "REAL_ARCHIVE",
    "ai_generated": "SCIENTIFIC_RECONSTRUCTION",
}

_CLASS_TO_SOURCE_TYPE = {
    "REAL_ARCHIVE": "archival",
    "DATA_VISUALIZATION": "ai_generated",
    "SCIENTIFIC_DIAGRAM": "ai_generated",
    "SCIENTIFIC_RECONSTRUCTION": "ai_generated",
    "HYPOTHETICAL_RECONSTRUCTION": "ai_generated",
    "ARTISTIC_METAPHOR": "ai_generated",
}


@dataclass
class RouteDecision:
    scene_id: str
    source_type: str  # "archival" | "ai_generated" (legacy, backward-compat)
    visual_class: str  # one of VISUAL_CLASSES (V8 §8.9)
    reason: str
    status: str  # success | fallback_used | failed
    failure_class: str = "OPTIONAL"  # REQUIRED | OPTIONAL | DEGRADABLE | MANUAL_REVIEW
    evidence: dict[str, Any] | None = None
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not self.checked_at:
            d["checked_at"] = datetime.now(timezone.utc).isoformat()
        return d


class SceneRouter:
    """Assign a visual class (+ legacy source type) to each scene id.

    Preferring licensed archival (REAL_ARCHIVE) when available, otherwise
    falling back to the designated visual class (default: SCIENTIFIC_RECONSTRUCTION
    for AI-designated scenes).
    """

    def __init__(
        self,
        archival_scenes: set[str] | None = None,
        ai_scenes: set[str] | None = None,
        visual_classes: dict[str, str] | None = None,
    ) -> None:
        # Defaults mirror the pilot first_video S-ID split (overridable per
        # episode — see lib.color_match profile_for parameterisation).
        self.archival_scenes = set(archival_scenes or {
            "S002", "S003", "S005", "S006", "S008", "S009", "S015", "S016",
            "S017", "S018", "S019", "S027", "S028", "S029", "S034", "S035",
            "S036", "S038", "S040", "S041",
        })
        self.ai_scenes = set(ai_scenes or {
            "S001", "S004", "S007", "S010", "S011", "S012", "S013", "S014",
            "S020", "S021", "S022", "S023", "S024", "S025", "S026", "S030",
            "S031", "S032", "S033", "S037", "S039",
        })
        # Per-scene visual class overrides (V8 §8.9).
        self.visual_classes = dict(visual_classes or {})

    def _visual_class_for(self, scene_id: str, source_type: str) -> str:
        """Resolve the visual class for a scene.

        Explicit override wins, then archival -> REAL_ARCHIVE, else the
        legacy source_type mapping.
        """
        if scene_id in self.visual_classes:
            vc = self.visual_classes[scene_id]
            if vc in VISUAL_CLASSES:
                return vc
        if source_type == "archival":
            return "REAL_ARCHIVE"
        return _SOURCE_TYPE_TO_CLASS.get(source_type, "SCIENTIFIC_RECONSTRUCTION")

    def route(self, scene_id: str, archival_available: bool = False) -> RouteDecision:
        """Return the source type and visual class for ``scene_id``.

        If the preferred source is archival but nothing is available locally
        or via the free archive, fall back to ai_generated (and record the
        fallback). Budget guard is consulted before any paid lookup.
        """
        budget = guard("footage_lookup", 0.0)
        if budget["status"] == "failed":
            vc = self._visual_class_for(scene_id, "ai_generated")
            return RouteDecision(
                scene_id=scene_id, source_type="ai_generated", visual_class=vc,
                status="failed", reason="budget guard refused lookup",
                failure_class="REQUIRED",
                evidence={"budget": budget},
            )

        if scene_id in self.archival_scenes:
            if archival_available:
                vc = self._visual_class_for(scene_id, "archival")
                return RouteDecision(
                    scene_id=scene_id, source_type="archival", visual_class=vc,
                    status="success",
                    reason="archival source available for scene",
                    evidence={"budget": budget},
                )
            # Preferred archival missing -> fall back to AI.
            vc = self._visual_class_for(scene_id, "ai_generated")
            return RouteDecision(
                scene_id=scene_id, source_type="ai_generated", visual_class=vc,
                status="fallback_used",
                reason="archival not available for scene; falling back to ai_generated",
                failure_class="OPTIONAL",
                evidence={"budget": budget},
            )
        if scene_id in self.ai_scenes:
            vc = self._visual_class_for(scene_id, "ai_generated")
            return RouteDecision(
                scene_id=scene_id, source_type="ai_generated", visual_class=vc,
                status="success",
                reason="scene designated ai_generated",
                evidence={"budget": budget},
            )
        # Unknown scene -> default to archival if available else ai_generated.
        if archival_available:
            vc = self._visual_class_for(scene_id, "archival")
            return RouteDecision(
                scene_id=scene_id, source_type="archival", visual_class=vc,
                status="fallback_used",
                reason="unknown scene; defaulting to archival if available",
                failure_class="OPTIONAL",
                evidence={"budget": budget},
            )
        vc = self._visual_class_for(scene_id, "ai_generated")
        return RouteDecision(
            scene_id=scene_id, source_type="ai_generated", visual_class=vc,
            status="fallback_used",
            reason="unknown scene; no archival, defaulting to ai_generated",
            failure_class="OPTIONAL",
            evidence={"budget": budget},
        )


def route_scene(scene_id: str, archival_available: bool = False) -> dict[str, Any]:
    """Module-level convenience route."""
    return SceneRouter().route(scene_id, archival_available).to_dict()
