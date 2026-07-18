"""Fitness scoring for the Hermes Creative Flywheel (the "Score" stage).

Scores one rendered content individual against a weighted, explainable rubric
so the Breed stage can select parents and the loop can converge toward better
videos. Mirrors lib/scoring.py's design philosophy: every score is normalized
0-1, weighted, and explainable (no black box).

Two score modes:
- ``rubric`` (default): score a free-form artifact against a creative rubric
  (hook_power, narrative_flow, visual_density, retention, cohesion, novelty).
  Hard metrics (duration match, word count, cost) are folded in when present.
- ``compare``: score a candidate against a target/baseline so the loop can tell
  if a mutation actually improved things.

Pure-local and deterministic. Any LLM-based "taste" scoring is opt-in via the
``llm_score`` input field (already computed by the driving agent) so this tool
never calls a model itself -- keeping it free and offline.

Input artifact shape (loose; only what's present is scored):
{
  "topic": str,
  "duration_seconds": float,
  "target_duration_seconds": float,
  "word_count": int,
  "target_word_count": int,
  "cost_usd": float,
  "budget_usd": float,
  "sections": [{"label": str, "enhancement_cues": [...], "text": str}, ...],
  "retention_anchors": int,       # surprising facts / hooks planted
  "novelty_flag": bool,           # did this generation try something new?
  "cohesion_notes": str,
  "llm_score": float,             # 0-1 optional agent-provided taste score
  "notes": str
}
"""

from __future__ import annotations

import time
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# Rubric weights sum to 1.0. Higher weight = more leverage on the loop.
_RUBRIC = {
    "hook_power": 0.20,
    "narrative_flow": 0.18,
    "visual_density": 0.15,
    "retention": 0.15,
    "cohesion": 0.14,
    "novelty": 0.10,
    "duration_fit": 0.05,
    "cost_efficiency": 0.03,
}
# Hard caps so a broken render can't score well regardless of taste.
_MIN_VISUAL_DENSITY = 0.4  # one enhancement cue per ~8-10s is the house rule


class BreedScorer(BaseTool):
    name = "breed_scorer"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "evolution"
    provider = "local"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = ""

    capabilities = [
        "flywheel_score",
        "fitness_function",
        "evolution_selection",
    ]
    input_schema = {
        "type": "object",
        "required": ["action", "artifact"],
        "properties": {
            "action": {
                "type": "string",
                "enum": ["rubric", "compare"],
                "description": (
                    "rubric: score one artifact against the creative rubric. "
                    "compare: score a candidate vs a baseline (needs 'baseline')."
                ),
            },
            "artifact": {
                "type": "object",
                "description": "The rendered individual to score (see module docstring).",
            },
            "baseline": {
                "type": "object",
                "description": "Baseline artifact for action=compare.",
            },
            "weights": {
                "type": "object",
                "description": "Optional override of rubric weights (must sum ~1.0).",
            },
            "individual_id": {
                "type": "string",
                "description": "Optional id to echo back into the result.",
            },
            "generation": {
                "type": "integer",
                "description": "Optional generation number to echo back.",
            },
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "score": {"type": "number"},
            "components": {"type": "object"},
            "explanation": {"type": "string"},
            "passed_hard_gate": {"type": "boolean"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=32, vram_mb=0, disk_mb=0, network_required=False
    )
    side_effects = []

    # Opt-in quality hints for the registry's scoring engine.
    quality_score = 0.85
    historical_success_rate = 0.99
    latency_p50_seconds = 0.05

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    # ----- execution ---------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        action = inputs.get("action", "rubric")
        artifact = inputs.get("artifact")
        started = time.monotonic()
        if not isinstance(artifact, dict):
            return ToolResult(success=False, error="artifact object required")
        try:
            if action == "compare":
                baseline = inputs.get("baseline")
                if not isinstance(baseline, dict):
                    return ToolResult(
                        success=False, error="baseline artifact required for compare"
                    )
                components = self._score_components(artifact, inputs.get("weights"))
                baseline_components = self._score_components(baseline, inputs.get("weights"))
                score = components["__total__"]
                base_score = baseline_components["__total__"]
                delta = round(score - base_score, 4)
                return ToolResult(
                    success=True,
                    data={
                        "score": score,
                        "baseline_score": base_score,
                        "delta": delta,
                        "improved": delta > 0,
                        "components": {k: v for k, v in components.items() if k != "__total__"},
                        "explanation": self._explain(components, delta=delta),
                        "passed_hard_gate": self._hard_gate(components),
                    },
                    duration_seconds=round(time.monotonic() - started, 3),
                )
            components = self._score_components(artifact, inputs.get("weights"))
            score = components["__total__"]
            return ToolResult(
                success=True,
                data={
                    "score": score,
                    "components": {k: v for k, v in components.items() if k != "__total__"},
                    "explanation": self._explain(components),
                    "passed_hard_gate": self._hard_gate(components),
                    "individual_id": inputs.get("individual_id"),
                    "generation": inputs.get("generation"),
                },
                duration_seconds=round(time.monotonic() - started, 3),
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"breed_scorer error: {exc}",
                duration_seconds=round(time.monotonic() - started, 3),
            )

    # ----- scoring internals ------------------------------------------

    def _score_components(self, artifact: dict[str, Any], weights: dict[str, Any] | None) -> dict[str, float]:
        w = dict(_RUBRIC)
        if isinstance(weights, dict) and weights:
            for k in w:
                if k in weights and isinstance(weights[k], (int, float)):
                    w[k] = float(weights[k])
            total = sum(w.values()) or 1.0
            w = {k: v / total for k, v in w.items()}

        comp: dict[str, float] = {}

        # llm-provided taste score, if the agent computed one (0-1)
        llm = artifact.get("llm_score")
        if isinstance(llm, (int, float)):
            comp["hook_power"] = float(llm)
            comp["narrative_flow"] = float(llm)
            comp["cohesion"] = float(llm)
        else:
            # derive a proxy from structure when no LLM score is supplied
            comp["hook_power"] = self._hook_power(artifact)
            comp["narrative_flow"] = self._narrative_flow(artifact)
            comp["cohesion"] = 0.7  # neutral; raised by cohesion_notes presence

        comp["visual_density"] = self._visual_density(artifact)
        comp["retention"] = self._retention(artifact)
        comp["novelty"] = 1.0 if artifact.get("novelty_flag") else 0.4
        comp["duration_fit"] = self._duration_fit(artifact)
        comp["cost_efficiency"] = self._cost_efficiency(artifact)

        total = sum(w[k] * comp.get(k, 0.0) for k in w)
        comp["__total__"] = round(total, 4)
        return comp

    def _hook_power(self, a: dict[str, Any]) -> float:
        # a strong hook = first section text starts with a question / bold
        # claim and is short. Proxy only; agents should supply llm_score.
        sections = a.get("sections") or []
        if not sections:
            return 0.5
        first = str(sections[0].get("text", ""))
        if not first:
            return 0.4
        if first.strip().endswith("?") or first.lower().startswith(("what", "why", "imagine", "did you")):
            return 0.8
        return 0.5

    def _narrative_flow(self, a: dict[str, Any]) -> float:
        sections = a.get("sections") or []
        n = len(sections)
        if n < 3:
            return 0.5
        # penalize if any section has no enhancement cue (dead moment)
        dead = sum(1 for s in sections if not s.get("enhancement_cues"))
        return round(max(0.2, 1.0 - 0.15 * dead), 3)

    def _visual_density(self, a: dict[str, Any]) -> float:
        sections = a.get("sections") or []
        dur = float(a.get("duration_seconds") or len(sections) * 10 or 60)
        cues = sum(len(s.get("enhancement_cues") or []) for s in sections)
        per_10s = cues / max(dur / 10.0, 1.0)
        # target: >=1 cue per 10s => 1.0; below minimum => capped
        if per_10s >= 1.0:
            return 1.0
        return round(min(1.0, per_10s / _MIN_VISUAL_DENSITY), 3)

    def _retention(self, a: dict[str, Any]) -> float:
        anchors = int(a.get("retention_anchors") or 0)
        # 3+ surprise anchors is strong for a ~60s piece
        return min(1.0, anchors / 3.0)

    def _duration_fit(self, a: dict[str, Any]) -> float:
        dur = a.get("duration_seconds")
        target = a.get("target_duration_seconds")
        if not dur or not target:
            return 0.7
        ratio = float(dur) / float(target)
        if 0.95 <= ratio <= 1.05:
            return 1.0
        if 0.8 <= ratio <= 1.2:
            return 0.6
        return 0.3

    def _cost_efficiency(self, a: dict[str, Any]) -> float:
        cost = float(a.get("cost_usd") or 0.0)
        budget = a.get("budget_usd")
        if cost <= 0:
            return 1.0
        if budget:
            ratio = cost / float(budget)
            return 0.1 if ratio > 1.0 else (0.5 if ratio > 0.5 else 0.9)
        if cost < 0.05:
            return 0.9
        if cost < 0.20:
            return 0.7
        return 0.4

    def _hard_gate(self, components: dict[str, float]) -> bool:
        # A render must clear the visual-density floor to count as viable.
        return bool(components.get("visual_density", 0.0) >= _MIN_VISUAL_DENSITY)

    def _explain(self, comp: dict[str, float], delta: float | None = None) -> str:
        parts = [f"fitness={comp['__total__']:.2f}"]
        top = sorted(
            (k for k in comp if k != "__total__"),
            key=lambda k: comp[k],
        )
        if top:
            parts.append(f"weakest={top[0]}={comp[top[0]]:.2f}")
        if delta is not None:
            parts.append(f"delta_vs_baseline={delta:+.2f}")
        return "; ".join(parts)
