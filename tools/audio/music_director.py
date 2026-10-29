"""Story-driven music direction for micro-story renders.

Selects and schedules music beds based on the STORY itself: each beat carries a
narrative role (need, obstacle, escalation, turn, payoff, lesson...) and the
director derives a tension curve, finds the emotional turning point, and lays
out bed segments (with optional mood change + crossfade) accordingly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
)

TENSE_ROLES = {"obstacle", "danger", "escalation", "peak", "stakes"}
RELIEF_ROLES = {"turn", "payoff", "lesson", "resolution"}


class MusicDirector(BaseTool):
    name = "music_director"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "music_selection"
    provider = "local"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = []
    install_instructions = "No external dependencies."

    capabilities = ["story_music_planning", "mood_classification", "segment_scheduling"]

    input_schema = {
        "type": "object",
        "required": ["beats", "total_duration", "bed_paths"],
        "properties": {
            "beats": {
                "type": "array",
                "description": (
                    "Ordered story beats with narrative metadata. Each item: "
                    "{id, role, start_seconds, end_seconds, line(optional)}. "
                    "Roles follow the documentary-shorts playbook arc."
                ),
                "items": {"type": "object"},
            },
            "total_duration": {"type": "number"},
            "bed_paths": {
                "type": "object",
                "description": "Mood -> audio file path, e.g. {'tense': '...', 'uplifting': '...'}",
            },
            "volume": {"type": "number", "default": 0.06},
            "crossfade_seconds": {"type": "number", "default": 1.5},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            plan = self.plan(inputs)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(success=False, error=f"music_director failed: {exc}")
        return ToolResult(
            success=True,
            data=plan,
            artifacts=[s["path"] for s in plan.get("segments", [])],
        )

    # ------------------------------------------------------------------
    def plan(self, inputs: dict[str, Any]) -> dict[str, Any]:
        beats = inputs["beats"]
        total = float(inputs["total_duration"])
        beds = {k: str(v) for k, v in inputs["bed_paths"].items()}
        volume = float(inputs.get("volume", 0.06))
        xfade = float(inputs.get("crossfade_seconds", 1.5))

        for key, path in beds.items():
            if not Path(path).exists():
                raise FileNotFoundError(f"Bed '{key}' not found: {path}")

        tension = self._tension_curve(beats)
        mood = self._classify_story(tension)
        segments = self._schedule(beats, tension, mood, beds, volume, xfade, total)

        return {
            "story_mood": mood,
            "tension_curve": tension,
            "segments": segments,
            "rationale": self._rationale(mood, tension),
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _beat_score(role: str) -> float:
        r = (role or "").lower()
        if r in TENSE_ROLES:
            return 1.0
        if r in RELIEF_ROLES:
            return -1.0
        if r in {"hook", "crisis"}:
            return 0.8
        if r in {"micro_relief", "relief"}:
            return -0.5
        return 0.0

    def _tension_curve(self, beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for b in beats:
            out.append(
                {
                    "id": b.get("id"),
                    "role": b.get("role", ""),
                    "start": float(b.get("start_seconds", 0.0)),
                    "score": self._beat_score(b.get("role", "")),
                }
            )
        return out

    def _classify_story(self, curve: list[dict[str, Any]]) -> str:
        scores = [c["score"] for c in curve]
        n_pos = sum(1 for s in scores if s >= 0.8)
        n_neg = sum(1 for s in scores if s <= -0.5)
        ends_relief = bool(scores) and scores[-1] < 0
        has_peak = any(s >= 0.8 for s in scores)

        if has_peak and ends_relief and n_neg >= 2:
            return "peril_to_relief"
        if has_peak and not ends_relief:
            return "sustained_tension"
        if n_neg and not has_peak:
            return "warm_reflection"
        return "ambient_neutral"

    def _schedule(
        self,
        beats: list[dict[str, Any]],
        curve: list[dict[str, Any]],
        mood: str,
        beds: dict[str, str],
        volume: float,
        xfade: float,
        total: float,
    ) -> list[dict[str, Any]]:
        """Lay bed segments along the timeline.

        peril_to_relief / warm_reflection switch beds at the first relief-role
        beat (the story's turn); sustained_tension holds one bed throughout;
        ambient_neutral uses whichever single bed exists.
        """
        fallback = next(iter(beds.values()))
        tense_bed = beds.get("tense", fallback)
        relief_bed = beds.get("uplifting", fallback)

        turn_start = None
        for c in curve:
            if c["score"] <= -1.0:
                turn_start = c["start"]
                break

        if turn_start is not None and 0 < turn_start < total:
            # Story turns partway: tense bed up to the turn, relief bed after,
            # crossfaded so the score follows the emotional curve.
            return [
                {"path": tense_bed, "start": 0.0, "end": round(turn_start + xfade, 3),
                 "volume": volume, "fade_in": 1.0, "fade_out": round(xfade, 3)},
                {"path": relief_bed, "start": round(turn_start, 3), "end": total,
                 "volume": volume, "fade_in": round(xfade, 3), "fade_out": 2.0},
            ]
        single = tense_bed if mood == "sustained_tension" else relief_bed
        return [
            {"path": single, "start": 0.0, "end": total, "volume": volume,
             "fade_in": 1.0, "fade_out": 2.0}
        ]

    @staticmethod
    def _rationale(mood: str, curve: list[dict[str, Any]]) -> str:
        peak_roles = [c["role"] for c in curve if c["score"] >= 1.0]
        relief_roles = [c["role"] for c in curve if c["score"] <= -1.0]
        return (
            f"Classified '{mood}': tension peaks at {peak_roles[:3]}, "
            f"release points at {relief_roles[:3]}. Beds scheduled to follow "
            f"that curve rather than run one flat track."
        )
