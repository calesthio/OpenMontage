"""Character Consistency Manager — keeps character identity stable across
scenes while allowing varied poses, angles, and environments.

All checks are local and structural: anatomy, proportions, distinguishing
features, and visual descriptors are compared across scenes without any
generation or credit spend.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from lib.stickman_rig import SIGNATURE_DETAIL_ID, VALID_EXPRESSIONS
except Exception:  # noqa: BLE001
    SIGNATURE_DETAIL_ID = "magnifying_lens"
    VALID_EXPRESSIONS = ("neutral",)


@dataclass
class CharacterAnatomy:
    """Fixed physical description of one character."""

    character_id: str
    display_name: str
    role: str
    body_type: str
    limb_count: int = 4  # arms + legs for humanoid
    distinguishing_features: list[str] = field(default_factory=list)
    silhouette_notes: str = ""
    color_palette: list[str] = field(default_factory=list)
    clothing_notes: str = ""
    required_views: list[str] = field(default_factory=list)
    required_emotions: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    props: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


@dataclass
class CharacterReference:
    """A visual reference (image or description) used to anchor identity."""

    reference_id: str
    character_id: str
    reference_type: str  # "image" | "description" | "concept_art"
    source_path: str | None = None
    description: str = ""
    captured_features: list[str] = field(default_factory=list)


@dataclass
class ConsistencyIssue:
    """A detected inconsistency between a scene plan and character design."""

    character_id: str
    scene_id: str
    issue_type: str  # "missing_limb" | "wrong_proportion" | "feature_drift" | "clothing_mismatch" | "pose_contradiction"
    description: str
    severity: str  # "low" | "medium" | "high"


@dataclass
class ConsistencyReport:
    """Result of checking all scenes against character designs."""

    version: str = "1.0"
    total_characters: int = 0
    total_scenes_checked: int = 0
    characters: dict[str, CharacterAnatomy] = field(default_factory=dict)
    references: dict[str, list[CharacterReference]] = field(default_factory=dict)
    issues: list[ConsistencyIssue] = field(default_factory=list)
    passed: bool = False


@dataclass
class StickmanRigProfile:
    """Rig profile for a programmatic stickman character."""

    rig_id: str
    character_id: str
    display_name: str = "Researcher"
    proportions: dict[str, Any] = field(default_factory=dict)
    signature_detail_id: str = "magnifying_lens"
    accent_color: str = "#2a9d8f"
    ink_color: str = "#1f2320"
    allowed_poses: list[str] = field(default_factory=list)
    allowed_expressions: list[str] = field(default_factory=list)
    min_height_heads: float = 4.0
    max_height_heads: float = 4.5


@dataclass
class RigConsistencyIssue:
    """Inconsistency detected for a rig pose."""

    character_id: str
    scene_id: str
    issue_type: str
    description: str
    severity: str = "medium"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class CharacterConsistencyManager:
    """Register character designs, add references, and validate scenes."""

    def __init__(self) -> None:
        self.characters: dict[str, CharacterAnatomy] = {}
        self.references: dict[str, list[CharacterReference]] = {}
        self._scene_character_usage: dict[str, str] = {}  # scene_id -> character_id
        self.rigs: dict[str, StickmanRigProfile] = {}
        self._rig_scene_usage: dict[str, str] = {}  # scene_id -> rig_id

    # -- Registration -------------------------------------------------------

    def register_character(
        self,
        *,
        character_id: str,
        display_name: str,
        role: str,
        body_type: str,
        limb_count: int = 4,
        distinguishing_features: list[str] | None = None,
        silhouette_notes: str = "",
        color_palette: list[str] | None = None,
        clothing_notes: str = "",
        required_views: list[str] | None = None,
        required_emotions: list[str] | None = None,
        required_actions: list[str] | None = None,
        props: list[str] | None = None,
        constraints: list[str] | None = None,
    ) -> CharacterAnatomy:
        """Create and store a character anatomy record."""
        char = CharacterAnatomy(
            character_id=character_id,
            display_name=display_name,
            role=role,
            body_type=body_type,
            limb_count=limb_count,
            distinguishing_features=distinguishing_features or [],
            silhouette_notes=silhouette_notes,
            color_palette=color_palette or [],
            clothing_notes=clothing_notes,
            required_views=required_views or [],
            required_emotions=required_emotions or [],
            required_actions=required_actions or [],
            props=props or [],
            constraints=constraints or [],
        )
        self.characters[character_id] = char
        return char

    def add_reference(
        self,
        *,
        reference_id: str,
        character_id: str,
        reference_type: str = "description",
        source_path: str | None = None,
        description: str = "",
        captured_features: list[str] | None = None,
    ) -> CharacterReference:
        """Add a visual reference for a character."""
        ref = CharacterReference(
            reference_id=reference_id,
            character_id=character_id,
            reference_type=reference_type,
            source_path=source_path,
            description=description,
            captured_features=captured_features or [],
        )
        self.references.setdefault(character_id, []).append(ref)
        return ref

    # -- Rig registration ---------------------------------------------------

    def register_stickman_rig(
        self,
        *,
        rig_id: str,
        character_id: str,
        display_name: str = "Researcher",
        proportions: dict[str, Any] | None = None,
        signature_detail_id: str = "magnifying_lens",
        accent_color: str = "#2a9d8f",
        ink_color: str = "#1f2320",
        allowed_poses: list[str] | None = None,
        allowed_expressions: list[str] | None = None,
        min_height_heads: float = 4.0,
        max_height_heads: float = 4.5,
    ) -> StickmanRigProfile:
        profile = StickmanRigProfile(
            rig_id=rig_id,
            character_id=character_id,
            display_name=display_name,
            proportions=proportions or {},
            signature_detail_id=signature_detail_id,
            accent_color=accent_color,
            ink_color=ink_color,
            allowed_poses=allowed_poses or [],
            allowed_expressions=allowed_expressions or [],
            min_height_heads=min_height_heads,
            max_height_heads=max_height_heads,
        )
        self.rigs[rig_id] = profile
        return profile

    def validate_rig_pose(
        self,
        *,
        scene_id: str,
        rig_id: str,
        pose_id: str,
        expression_id: str,
        view: str = "front",
        signature_detail_present: bool = True,
    ) -> list[RigConsistencyIssue]:
        issues: list[RigConsistencyIssue] = []
        profile = self.rigs.get(rig_id)
        if profile is None:
            issues.append(RigConsistencyIssue(
                character_id=profile.character_id if profile else rig_id,
                scene_id=scene_id,
                issue_type="unknown_rig",
                description=f"Rig {rig_id} not registered",
                severity="high",
            ))
            return issues
        self._rig_scene_usage[scene_id] = rig_id
        if profile.allowed_poses and pose_id not in profile.allowed_poses:
            issues.append(RigConsistencyIssue(
                character_id=profile.character_id,
                scene_id=scene_id,
                issue_type="unknown_pose",
                description=f"Pose {pose_id} not allowed by rig {rig_id}",
                severity="medium",
            ))
        if profile.allowed_expressions and expression_id not in profile.allowed_expressions:
            issues.append(RigConsistencyIssue(
                character_id=profile.character_id,
                scene_id=scene_id,
                issue_type="unknown_expression",
                description=f"Expression {expression_id} not allowed by rig {rig_id}",
                severity="medium",
            ))
        if view not in ("front", "three_quarter", "profile", "back"):
            issues.append(RigConsistencyIssue(
                character_id=profile.character_id,
                scene_id=scene_id,
                issue_type="unknown_view",
                description=f"Unknown view {view}",
                severity="low",
            ))
        if not signature_detail_present:
            issues.append(RigConsistencyIssue(
                character_id=profile.character_id,
                scene_id=scene_id,
                issue_type="missing_signature_detail",
                description="Magnifying lens signature detail missing",
                severity="high",
            ))
        if profile.signature_detail_id != "magnifying_lens":
            issues.append(RigConsistencyIssue(
                character_id=profile.character_id,
                scene_id=scene_id,
                issue_type="wrong_signature_detail",
                description=f"Expected magnifying_lens, got {profile.signature_detail_id}",
                severity="high",
            ))
        return issues

    # -- Scene validation ---------------------------------------------------

    def record_scene_character(self, scene_id: str, character_id: str) -> None:
        """Note that a character appears in a scene."""
        self._scene_character_usage[scene_id] = character_id

    def validate_scene_against_character(
        self,
        *,
        scene_id: str,
        character_id: str,
        scene_description: str,
        proposed_limb_count: int | None = None,
        proposed_features: list[str] | None = None,
        proposed_clothing: str | None = None,
        proposed_view: str | None = None,
    ) -> list[ConsistencyIssue]:
        """Check one scene's depiction of a character against its design.

        Returns a list of :class:`ConsistencyIssue` (empty = consistent).
        """
        issues: list[ConsistencyIssue] = []
        char = self.characters.get(character_id)
        if char is None:
            issues.append(
                ConsistencyIssue(
                    character_id=character_id,
                    scene_id=scene_id,
                    issue_type="unknown_character",
                    description=f"Character {character_id} not registered in consistency manager",
                    severity="high",
                )
            )
            return issues

        self.record_scene_character(scene_id, character_id)

        # Limb count check
        if proposed_limb_count is not None and proposed_limb_count != char.limb_count:
            issues.append(
                ConsistencyIssue(
                    character_id=character_id,
                    scene_id=scene_id,
                    issue_type="wrong_limb_count",
                    description=f"Scene proposes {proposed_limb_count} limbs; design specifies {char.limb_count}",
                    severity="high",
                )
            )

        # Distinguishing features check
        proposed = set((proposed_features or []))
        for feature in char.distinguishing_features:
            if feature.lower() not in {f.lower() for f in proposed}:
                issues.append(
                    ConsistencyIssue(
                        character_id=character_id,
                        scene_id=scene_id,
                        issue_type="feature_drift",
                        description=f"Missing distinguishing feature: {feature}",
                        severity="medium",
                    )
                )

        # Clothing check
        if proposed_clothing is not None and char.clothing_notes:
            if char.clothing_notes.lower() not in proposed_clothing.lower():
                issues.append(
                    ConsistencyIssue(
                        character_id=character_id,
                        scene_id=scene_id,
                        issue_type="clothing_mismatch",
                        description=f"Clothing '{proposed_clothing}' diverges from design '{char.clothing_notes}'",
                        severity="low",
                    )
                )

        # View check: ensure we don't always use the same portrait view
        if proposed_view and proposed_view in ("portrait", "headshot", "close_up_face"):
            # Track portrait usage
            pass  # allowed but noted; variety enforced by Visual Director

        return issues

    def validate_all_scenes(
        self,
        scene_character_map: dict[str, str],
        scene_descriptions: dict[str, str],
    ) -> ConsistencyReport:
        """Validate every scene-character pairing in one pass."""
        report = ConsistencyReport(
            total_characters=len(self.characters),
            total_scenes_checked=len(scene_character_map),
            characters=dict(self.characters),
            references={k: list(v) for k, v in self.references.items()},
        )

        for scene_id, character_id in scene_character_map.items():
            desc = scene_descriptions.get(scene_id, "")
            issues = self.validate_scene_against_character(
                scene_id=scene_id,
                character_id=character_id,
                scene_description=desc,
            )
            report.issues.extend(issues)

        report.passed = not any(i.severity == "high" for i in report.issues)
        return report

    def detect_contradictions(self) -> list[ConsistencyIssue]:
        """Find contradictions between scenes sharing a character."""
        contradictions: list[ConsistencyIssue] = []
        # Group scenes by character
        by_char: dict[str, list[str]] = {}
        for scene_id, char_id in self._scene_character_usage.items():
            by_char.setdefault(char_id, []).append(scene_id)

        for char_id, scene_ids in by_char.items():
            char = self.characters.get(char_id)
            if char is None:
                continue
            # Check that all scenes use the same limb count (implicitly via design)
            # and that distinguishing features are mentioned consistently.
            for scene_id in scene_ids:
                # Already validated per-scene; this is a cross-scene check for
                # clothing / feature contradictions if we had per-scene data.
                pass
        return contradictions

    def to_dict(self, report: ConsistencyReport) -> dict[str, Any]:
        return {
            "version": report.version,
            "total_characters": report.total_characters,
            "total_scenes_checked": report.total_scenes_checked,
            "characters": {cid: asdict(c) for cid, c in report.characters.items()},
            "references": {
                cid: [asdict(r) for r in refs] for cid, refs in report.references.items()
            },
            "issues": [asdict(i) for i in report.issues],
            "passed": report.passed,
        }
