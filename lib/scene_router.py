"""Scene router — archival vs ai_generated source assignment per scene.

V7 §3, layer 3 (VISUALS). Routes each scene to a source type and returns
an explicit status (success / fallback_used / failed). Reuses
lib.footage_sourcing provenance conventions and lib.color_match profiles.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.budget_guard import guard


@dataclass
class RouteDecision:
    scene_id: str
    source_type: str  # "archival" | "ai_generated"
    reason: str
    status: str  # success | fallback_used | failed
    evidence: dict[str, Any] | None = None
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not self.checked_at:
            d["checked_at"] = datetime.now(timezone.utc).isoformat()
        return d


class SceneRouter:
    """Assign archival (NASA/Archive.org/Wikimedia) or AI-generated source
    to each scene id, preferring licensed archival when available."""

    def __init__(self, archival_scenes: set[str] | None = None,
                 ai_scenes: set[str] | None = None) -> None:
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

    def route(self, scene_id: str, archival_available: bool = False) -> RouteDecision:
        """Return the source type for ``scene_id``.

        If the preferred source is archival but nothing is available locally
        or via the free archive, fall back to ai_generated (and record the
        fallback). Budget guard is consulted before any paid lookup.
        """
        budget = guard("footage_lookup", 0.0)
        if budget["status"] == "failed":
            return RouteDecision(
                scene_id=scene_id, source_type="ai_generated",
                status="failed", reason="budget guard refused lookup",
                evidence={"budget": budget},
            )

        if scene_id in self.archival_scenes:
            if archival_available:
                return RouteDecision(
                    scene_id=scene_id, source_type="archival",
                    status="success",
                    reason="archival source available for scene",
                    evidence={"budget": budget},
                )
            # Preferred archival missing -> fall back to AI.
            return RouteDecision(
                scene_id=scene_id, source_type="ai_generated",
                status="fallback_used",
                reason="archival not available for scene; falling back to ai_generated",
                evidence={"budget": budget},
            )
        if scene_id in self.ai_scenes:
            return RouteDecision(
                scene_id=scene_id, source_type="ai_generated",
                status="success",
                reason="scene designated ai_generated",
                evidence={"budget": budget},
            )
        # Unknown scene -> default to archival if available else ai_generated.
        if archival_available:
            return RouteDecision(
                scene_id=scene_id, source_type="archival",
                status="fallback_used",
                reason="unknown scene; defaulting to archival if available",
                evidence={"budget": budget},
            )
        return RouteDecision(
            scene_id=scene_id, source_type="ai_generated",
            status="fallback_used",
            reason="unknown scene; no archival, defaulting to ai_generated",
            evidence={"budget": budget},
        )


def route_scene(scene_id: str, archival_available: bool = False) -> dict[str, Any]:
    """Module-level convenience route."""
    return SceneRouter().route(scene_id, archival_available).to_dict()
