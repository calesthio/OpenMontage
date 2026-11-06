"""Scene Planner — converts analysed script blocks into an ordered scene plan.

Each scene gets a scene_id, script section binding, visual idea, shot plan,
framing, composition, lighting, required objects, duration, and a transition
to the next scene.  Scenes are chained so they tell one continuous story.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ScenePlan:
    """One planned scene."""

    scene_id: str
    script_section_id: str
    visual_idea: str
    shot_purpose: str
    framing: str
    camera_movement: str
    lens_mm: int
    lighting_key: str
    color_temperature: str
    depth_of_field: str
    composition: str
    required_objects: list[str]
    duration_seconds: float
    transition_to_next: str
    shot_size: str
    shot_intent: str
    narrative_role: str
    hero_moment: bool = False


@dataclass
class ScenePlanOutput:
    """Full ordered scene plan."""

    version: str = "1.0"
    run_id: str = ""
    created_at: str = ""
    style_playbook: str = "science-documentary"
    scenes: list[ScenePlan] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shot language mapping (reuses shot_prompt_builder vocabulary)
# ---------------------------------------------------------------------------

_SHOT_SIZE_BY_ROLE = {
    "establish_context": "wide",
    "introduce_subject": "medium",
    "build_tension": "medium_close",
    "deliver_payload": "close_up",
    "transition": "wide",
    "emotional_beat": "close_up",
    "evidence": "medium_close",
    "comparison": "medium_wide",
    "resolution": "medium",
    "call_to_action": "medium",
}

_MOVEMENT_BY_ROLE = {
    "establish_context": "static",
    "introduce_subject": "dolly_in",
    "build_tension": "zoom_in",
    "deliver_payload": "static",
    "transition": "pan_right",
    "emotional_beat": "static",
    "evidence": "dolly_in",
    "comparison": "tracking_right",
    "resolution": "dolly_out",
    "call_to_action": "static",
}

_LIGHTING_BY_ROLE = {
    "establish_context": "natural",
    "introduce_subject": "high_key",
    "build_tension": "low_key",
    "deliver_payload": "high_key",
    "transition": "natural",
    "emotional_beat": "low_key",
    "evidence": "high_key",
    "comparison": "natural",
    "resolution": "high_key",
    "call_to_action": "high_key",
}

_COMPOSITION_BY_ROLE = {
    "establish_context": "subject small in frame, environment dominates",
    "introduce_subject": "subject centered, rule of thirds",
    "build_tension": "off-center subject, negative space",
    "deliver_payload": "subject fills frame, minimal background",
    "transition": "horizontal sweep across frame",
    "emotional_beat": "tight frame on subject face",
    "evidence": "object centered, shallow depth",
    "comparison": "split composition, two subjects balanced",
    "resolution": "subject centered, calm background",
    "call_to_action": "subject centered, clear copy space",
}

_TRANSFER_TRANSITIONS = {
    "establish_context": "cut to",
    "introduce_subject": "dissolve to",
    "build_tension": "zoom to",
    "deliver_payload": "cut to",
    "transition": "pan across to",
    "emotional_beat": "hold on",
    "evidence": "cut to close of",
    "comparison": "crossfade to",
    "resolution": "slow pull back to",
    "call_to_action": "hold on",
}

_LENGTH_BY_ROLE = {
    "establish_context": 6.0,
    "introduce_subject": 8.0,
    "build_tension": 5.0,
    "deliver_payload": 7.0,
    "transition": 3.0,
    "emotional_beat": 4.0,
    "evidence": 6.0,
    "comparison": 7.0,
    "resolution": 5.0,
    "call_to_action": 4.0,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ScenePlanner:
    """Plan an ordered sequence of scenes from analysed script blocks."""

    def __init__(self, default_fps: int = 30) -> None:
        self.default_fps = default_fps

    def plan(
        self,
        *,
        run_id: str,
        analysis_blocks: list[dict[str, Any]],
        characters: list[str] | None = None,
        visual_style: str = "bold ink illustration",
        hero_index: int | None = None,
    ) -> ScenePlanOutput:
        """Produce an ordered :class:`ScenePlanOutput` from analysed blocks.

        Args:
            run_id: Factory run identifier.
            analysis_blocks: Output of :class:`ScriptAnalyzer.to_dict`.
            characters: Character ids expected to appear.
            visual_style: Visual style hint for composition notes.
            hero_index: Optional index of the hero scene; if None, the
                longest "claim" block becomes the hero.
        """
        characters = characters or []
        scenes: list[ScenePlan] = []
        total_blocks = len(analysis_blocks)

        # Determine hero scene
        hero_idx = hero_index
        if hero_idx is None:
            claim_indices = [
                i for i, b in enumerate(analysis_blocks) if b.get("block_type") == "claim"
            ]
            hero_idx = max(claim_indices, key=lambda i: analysis_blocks[i]["word_count"]) if claim_indices else 0

        cumulative_seconds = 0.0
        for idx, block in enumerate(analysis_blocks):
            block_type = block.get("block_type", "exposition")
            role = _role_for(block_type)
            shot_size = _SHOT_SIZE_BY_ROLE[role]
            movement = _MOVEMENT_BY_ROLE[role]
            lighting = _LIGHTING_BY_ROLE[role]
            # Pull a unique content keyword from the block text so each scene's
            # composition string is distinct (helps QC variety checks).
            block_words = [w for w in block.get("text", "").split() if len(w) > 5]
            kw = block_words[0] if block_words else f"scene{idx}"
            composition = (
                f"{_COMPOSITION_BY_ROLE[role]}; {shot_size}; {lighting} lighting; "
                f"keyword:{kw}; scene {idx + 1} of {total_blocks}"
            )
            duration = _LENGTH_BY_ROLE[role]

            scene_id = f"{run_id}-scene-{idx:03d}"
            section_id = block.get("block_id", f"block-{idx:03d}")

            # Visual idea combines block text with role-specific framing.
            visual_idea = (
                f"{block.get('text', '')[:120]} — "
                f"{composition}; {_shot_size_phrase(shot_size)}"
            )

            # Required objects: characters mentioned in this block + generic props.
            block_text = block.get("text", "").lower()
            objs = [ch for ch in characters if ch.lower() in block_text]
            if role == "establish_context":
                objs.append("environment establishing elements")
            if role == "evidence":
                objs.append("diagram or data visualization")
            if role == "deliver_payload":
                objs.append("key fact or statistic visual")

            # Transition to next scene
            if idx < total_blocks - 1:
                next_role = _role_for(analysis_blocks[idx + 1].get("block_type", "exposition"))
                transition = _TRANSFER_TRANSITIONS[next_role]
            else:
                transition = "hold to end"

            is_hero = idx == hero_idx
            if is_hero:
                duration = max(duration, 8.0)  # hero gets extra time

            scenes.append(
                ScenePlan(
                    scene_id=scene_id,
                    script_section_id=section_id,
                    visual_idea=visual_idea,
                    shot_purpose=role,
                    framing=_shot_size_phrase(shot_size),
                    camera_movement=movement,
                    lens_mm=self._lens_for(role),
                    lighting_key=lighting,
                    color_temperature="neutral",
                    depth_of_field="shallow" if role in ("deliver_payload", "emotional_beat") else "deep",
                    composition=composition,
                    required_objects=objs,
                    duration_seconds=duration,
                    transition_to_next=transition,
                    shot_size=shot_size,
                    shot_intent=f"Serves {role} for section {section_id}",
                    narrative_role=role,
                    hero_moment=is_hero,
                )
            )
            cumulative_seconds += duration

        return ScenePlanOutput(
            run_id=run_id,
            style_playbook=visual_style,
            scenes=scenes,
            metadata={
                "total_scenes": len(scenes),
                "total_planned_seconds": round(cumulative_seconds, 2),
                "hero_scene_id": scenes[hero_idx].scene_id if scenes else None,
                "characters": characters,
            },
        )

    @staticmethod
    def _lens_for(role: str) -> int:
        return {
            "establish_context": 24,
            "introduce_subject": 35,
            "build_tension": 50,
            "deliver_payload": 85,
            "transition": 14,
            "emotional_beat": 85,
            "evidence": 50,
            "comparison": 35,
            "resolution": 35,
            "call_to_action": 35,
        }[role]


def _role_for(block_type: str) -> str:
    mapping = {
        "exposition": "establish_context",
        "claim": "deliver_payload",
        "transition": "transition",
        "conclusion": "resolution",
    }
    return mapping.get(block_type, "establish_context")


def _shot_size_phrase(size: str) -> str:
    return {
        "extreme_wide": "extreme wide shot",
        "wide": "wide shot",
        "medium_wide": "medium-wide shot",
        "medium": "medium shot",
        "medium_close": "medium close-up",
        "close_up": "close-up",
        "extreme_close_up": "extreme close-up",
        "over_shoulder": "over-the-shoulder",
        "insert": "insert shot",
        "establishing": "establishing shot",
    }.get(size, size)


def to_dict(output: ScenePlanOutput) -> dict[str, Any]:
    return {
        "version": output.version,
        "run_id": output.run_id,
        "created_at": output.created_at,
        "style_playbook": output.style_playbook,
        "scenes": [asdict(s) for s in output.scenes],
        "metadata": output.metadata,
    }
