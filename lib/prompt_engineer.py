"""Prompt Engineer — builds per-scene generation prompts for Google Flow.

All prompts are text-only: no generation, no credits, no secrets.  Output is
a structured prompt packet (main prompt, negative prompt, composition,
style, character, environment, references, format) that Flow Job Manager can
store as a job and hold at READY_FOR_APPROVAL.

Visual foundation (applied to every scene unless overridden):
  - bold ink illustration
  - crisp black outlines
  - flat expressive flat colour fills
  - scientific-documentary composition
  - expressive lighting
  - varied surrounding environments
  - no visual AI-template repetition
  - NO text, captions, watermarks or logos inside the image
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Visual foundation (the "look" applied to every scene)
# ---------------------------------------------------------------------------

# Positive visual descriptors go in the main prompt.
VISUAL_FOUNDATION_POSITIVE = (
    "bold ink illustration, crisp black outlines, flat expressive colour fills, "
    "scientific-documentary composition, expressive lighting, varied surrounding "
    "environments"
)

# Prohibitions go only in the negative prompt — never in the main prompt.
VISUAL_FOUNDATION_NEGATIVE = (
    "text, caption, watermark, logo, signature, title, subtitle, lettering, "
    "typography, AI-generated gibberish text, distorted text, blurry text, "
    "template repetition, generic stock look, airbrushed, 3d render, plastic, "
    "gradient mesh, photorealistic photograph"
)

NEGATIVE_FOUNDATION = VISUAL_FOUNDATION_NEGATIVE

_FORMAT = "1920x1080, ink illustration"


@dataclass
class ScenePromptPacket:
    """Complete prompt packet for one scene."""

    scene_id: str
    main_prompt: str
    negative_prompt: str
    composition_description: str
    style: str
    character_description: str
    environment_description: str
    references: list[str]
    image_format: str
    aspect_ratio: str
    generation_params: dict[str, Any]


@dataclass
class PromptEngineerOutput:
    """All prompt packets for a video."""

    version: str = "1.0"
    run_id: str = ""
    created_at: str = ""
    visual_style: str = "bold ink illustration"
    packets: list[ScenePromptPacket] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class PromptEngineer:
    """Build per-scene prompt packets grounded in scene plans and characters."""

    def __init__(self, visual_style: str = "bold ink illustration") -> None:
        self.visual_style = visual_style

    def build_packet(
        self,
        *,
        scene_id: str,
        scene_plan: dict[str, Any],
        visual_directive: dict[str, Any] | None = None,
        character_anatomy: dict[str, Any] | None = None,
        references: list[str] | None = None,
        generation_params: dict[str, Any] | None = None,
    ) -> ScenePromptPacket:
        """Build one :class:`ScenePromptPacket` from a scene plan.

        Args:
            scene_id: Scene identifier.
            scene_plan: Output of ScenePlanner (as dict).
            visual_directive: Output of VisualDirector (as dict, optional).
            character_anatomy: Character design for any character in scene
                (optional).
            references: Reference image ids / descriptions (optional).
            generation_params: Model-specific params (optional).
        """
        references = references or []
        generation_params = generation_params or {}
        visual_directive = visual_directive or {}

        # --- Composition description ---------------------------------------
        shot_size = scene_plan.get("shot_size", "medium")
        movement = scene_plan.get("camera_movement", "static")
        composition = scene_plan.get("composition", "balanced")
        lens = scene_plan.get("lens_mm", 35)
        lighting = scene_plan.get("lighting_key", "natural")
        dof = scene_plan.get("depth_of_field", "deep")

        composition_description = (
            f"{shot_size}, {lens}mm lens, {movement} camera, "
            f"{composition}, {lighting} lighting, {dof} depth of field"
        )
        if visual_directive:
            composition_description += f"; {visual_directive.get('visual_idea_refinement', '')}"

        # --- Style ---------------------------------------------------------
        style = (
            f"{self.visual_style}; crisp black outlines; flat expressive colour fills; "
            f"scientific-documentary composition; expressive lighting"
        )

        # --- Character description ----------------------------------------
        character_description = ""
        if character_anatomy:
            parts = [
                character_anatomy.get("display_name", ""),
                character_anatomy.get("body_type", ""),
                character_anatomy.get("silhouette_notes", ""),
                ", ".join(character_anatomy.get("distinguishing_features", [])),
                character_anatomy.get("clothing_notes", ""),
            ]
            character_description = "; ".join(p for p in parts if p)
            placement = visual_directive.get("character_placement", "") if visual_directive else ""
            if placement:
                character_description += f"; {placement}"
        else:
            character_description = "no specific character; environment-focused scene"

        # --- Environment description --------------------------------------
        environment_notes = (
            visual_directive.get("environment_notes", "varied surrounding environment")
            if visual_directive
            else "varied surrounding environment"
        )
        environment_description = environment_notes

        # --- Main prompt --------------------------------------------------
        visual_idea = scene_plan.get("visual_idea", "")
        main_parts = [
            visual_idea,
            composition_description,
            style,
        ]
        if character_description:
            main_parts.append(f"character: {character_description}")
        main_parts.append(environment_description)
        if references:
            main_parts.append(f"references: {', '.join(references)}")
        main_parts.append(VISUAL_FOUNDATION_POSITIVE)

        main_prompt = ". ".join(p for p in main_parts if p)

        # --- Negative prompt ----------------------------------------------
        negative_prompt = VISUAL_FOUNDATION_NEGATIVE
        if character_anatomy and character_anatomy.get("constraints"):
            negative_prompt += "; " + "; ".join(
                f"no {c}" for c in character_anatomy["constraints"]
            )

        # --- Format -------------------------------------------------------
        image_format = _FORMAT
        aspect_ratio = scene_plan.get("aspect_ratio", "16:9") or "16:9"

        return ScenePromptPacket(
            scene_id=scene_id,
            main_prompt=main_prompt,
            negative_prompt=negative_prompt,
            composition_description=composition_description,
            style=style,
            character_description=character_description,
            environment_description=environment_description,
            references=list(references),
            image_format=image_format,
            aspect_ratio=aspect_ratio,
            generation_params=generation_params,
        )

    def build_all(
        self,
        *,
        scene_plans: list[dict[str, Any]],
        visual_directives: dict[str, dict[str, Any]] | None = None,
        character_anatomy: dict[str, dict[str, Any]] | None = None,
        references_by_scene: dict[str, list[str]] | None = None,
        generation_params: dict[str, Any] | None = None,
    ) -> PromptEngineerOutput:
        """Build prompt packets for every scene."""
        visual_directives = visual_directives or {}
        character_anatomy = character_anatomy or {}
        references_by_scene = references_by_scene or {}
        generation_params = generation_params or {}

        packets: list[ScenePromptPacket] = []
        for scene in scene_plans:
            sid = scene.get("scene_id", "unknown")
            # Determine which character (if any) is associated with this scene.
            char_id = scene.get("character_id")
            anat = character_anatomy.get(char_id, {}) if char_id else {}
            packets.append(
                self.build_packet(
                    scene_id=sid,
                    scene_plan=scene,
                    visual_directive=visual_directives.get(sid, {}),
                    character_anatomy=anat,
                    references=references_by_scene.get(sid, []),
                    generation_params=generation_params,
                )
            )

        return PromptEngineerOutput(
            visual_style=self.visual_style,
            packets=packets,
            metadata={
                "total_packets": len(packets),
                "visual_style": self.visual_style,
                "format": _FORMAT,
            },
        )

    def to_dict(self, output: PromptEngineerOutput) -> dict[str, Any]:
        return {
            "version": output.version,
            "run_id": output.run_id,
            "created_at": output.created_at,
            "visual_style": output.visual_style,
            "packets": [asdict(p) for p in output.packets],
            "metadata": output.metadata,
        }
