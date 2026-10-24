"""Crossover + mutation for the Hermes Creative Flywheel (the "Breed" stage).

Takes the scored population (from population_store) for a generation, selects
the fittest parents (tournament/elitism), and produces SEED VARIANTS for the
next generation. Each variant is a compact "seed" the Script stage can re-run
to produce a new individual -- so the loop closes: Script -> Render -> Score
-> Breed -> (new) Script.

Two operations:
- ``select_parents``: given individuals + a target count, return the top-K
  (elitism) plus a couple of random lower-ranked ones (exploration).
- ``breed``: given selected parents, emit ``population_size`` seed variants by
  crossing the two best parents' traits and applying mutation operators
  (angle_flip, constraint_relax, retention_boost, novel_concept).

The mutator is trait-level and provider-agnostic: it operates on the portable
fields of an individual (topic, angle, tone, structure, retention_anchors,
novelty_flag, style_hints) -- never on rendered bytes. This keeps the flywheel
cheap and lets any underlying OpenMontage pipeline consume the seeds.

Pure-local, deterministic given a seed (uses random with a seed for repeatable
runs; pass ``seed`` to reproduce a generation).
"""

from __future__ import annotations

import copy
import json
import random
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


class BreedMutator(BaseTool):
    name = "breed_mutator"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "evolution"
    provider = "local"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = ""

    capabilities = [
        "flywheel_breed",
        "crossover",
        "mutation",
        "next_generation_seeds",
    ]
    input_schema = {
        "type": "object",
        "required": ["action"],
        "properties": {
            "action": {
                "type": "string",
                "enum": ["select_parents", "breed"],
                "description": (
                    "select_parents: pick fittest parents from individuals. "
                    "breed: cross selected parents and emit next-gen seeds."
                ),
            },
            "individuals": {
                "type": "array",
                "description": "Scored individuals (each must carry 'score').",
            },
            "generation": {
                "type": "integer",
                "description": "Generation number these parents came from.",
            },
            "population_size": {
                "type": "integer",
                "default": 4,
                "description": "Number of seed variants to produce (action=breed).",
            },
            "elite_fraction": {
                "type": "number",
                "default": 0.5,
                "description": "Fraction of top individuals kept as elite parents.",
            },
            "exploration": {
                "type": "number",
                "default": 0.2,
                "description": "Fraction of lower-ranked individuals kept for diversity.",
            },
            "mutation_rate": {
                "type": "number",
                "default": 0.6,
                "description": "Probability a variant gets a mutation operator applied.",
            },
            "parents": {
                "type": "array",
                "description": "Pre-selected parents (action=breed, skips selection).",
            },
            "seed": {
                "type": "integer",
                "description": "RNG seed for reproducible breeding.",
            },
            "mutators": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Subset of mutators to apply. Default: all.",
            },
            "next_generation": {
                "type": "integer",
                "description": "Explicit next-generation number (else generation+1).",
            },
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "parents": {"type": "array"},
            "seeds": {
                "type": "array",
                "description": "Next-gen seed variants for the Script stage.",
            },
            "next_generation": {"type": "integer"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=32, vram_mb=0, disk_mb=0, network_required=False
    )
    side_effects = []

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    # ----- mutation operators -----------------------------------------

    _MUTATORS = ["angle_flip", "constraint_relax", "retention_boost", "novel_concept"]

    @staticmethod
    def _trait_cross(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        """Blend two individuals' portable traits for a seed."""
        seed: dict[str, Any] = {}
        for key in ("topic", "tone", "structure", "angle", "style_hints"):
            va, vb = a.get(key), b.get(key)
            # prefer the higher-scoring parent's value, fall back to either
            seed[key] = va if va is not None else vb
        # numeric traits: average
        for key in ("retention_anchors", "target_duration_seconds", "target_word_count"):
            na, nb = a.get(key), b.get(key)
            if isinstance(na, (int, float)) and isinstance(nb, (int, float)):
                seed[key] = round((na + nb) / 2)
            elif na is not None:
                seed[key] = na
        seed["parent_ids"] = [a.get("id"), b.get("id")]
        return seed

    def _mutate(self, seed: dict[str, Any], rng: random.Random, mutators: list[str]) -> dict[str, Any]:
        s = copy.deepcopy(seed)
        applied: list[str] = []
        if "angle_flip" in mutators:
            angle = s.get("angle", "")
            s["angle"] = f"counter-angle: challenge '{angle}'" if angle else "inverted premise"
            applied.append("angle_flip")
        if "constraint_relax" in mutators:
            s["constraint_relax"] = True
            applied.append("constraint_relax")
        if "retention_boost" in mutators:
            s["retention_anchors"] = int(s.get("retention_anchors", 1)) + 1
            applied.append("retention_boost")
        if "novel_concept" in mutators:
            s["novelty_flag"] = True
            applied.append("novel_concept")
        s["mutations"] = applied
        return s

    # ----- execution ---------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        action = inputs.get("action")
        started = time.monotonic()
        try:
            if action == "select_parents":
                return self._select(inputs)
            if action == "breed":
                return self._breed(inputs)
            return ToolResult(success=False, error=f"unknown action: {action}")
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"breed_mutator error: {exc}",
                duration_seconds=round(time.monotonic() - started, 3),
            )

    def _rank(self, individuals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            individuals,
            key=lambda i: float(i.get("score", 0.0)) if isinstance(i.get("score"), (int, float)) else 0.0,
            reverse=True,
        )

    def _select(self, inputs: dict[str, Any]) -> ToolResult:
        individuals = inputs.get("individuals") or []
        if not individuals:
            return ToolResult(success=False, error="individuals required for select_parents")
        ranked = self._rank(individuals)
        n = len(ranked)
        elite_n = max(1, int(round(n * float(inputs.get("elite_fraction", 0.5)))))
        explore_n = max(0, int(round(n * float(inputs.get("exploration", 0.2)))))
        elite = ranked[:elite_n]
        tail = ranked[elite_n:] or ranked[-1:]
        rng = random.Random(inputs.get("seed"))
        explorers = rng.sample(tail, min(explore_n, len(tail))) if explore_n else []
        parents = elite + explorers
        return ToolResult(
            success=True,
            data={
                "parents": parents,
                "elite": elite,
                "explorers": explorers,
                "best_score": float(ranked[0].get("score", 0.0)) if ranked else 0.0,
            },
        )

    def _breed(self, inputs: dict[str, Any]) -> ToolResult:
        generation = int(inputs.get("generation", 0))
        next_gen = int(inputs.get("next_generation", generation + 1))
        population_size = int(inputs.get("population_size", 4))
        mutation_rate = float(inputs.get("mutation_rate", 0.6))
        rng = random.Random(inputs.get("seed"))

        # parents: explicit or select from individuals
        parents = inputs.get("parents")
        if not parents:
            sel = self._select(inputs)
            if not sel.success:
                return sel
            parents = sel.data.get("parents", [])
        if not parents:
            return ToolResult(success=False, error="no parents available to breed")

        mutators = inputs.get("mutators") or self._MUTATORS
        seeds: list[dict[str, Any]] = []
        # pair the top parents round-robin to create variants
        for i in range(population_size):
            pa = parents[i % len(parents)]
            pb = parents[(i + 1) % len(parents)]
            seed = self._trait_cross(pa, pb)
            seed["generation"] = next_gen
            seed["variant"] = i
            if rng.random() < mutation_rate:
                seed = self._mutate(seed, rng, mutators)
            seeds.append(seed)

        return ToolResult(
            success=True,
            data={
                "parents": [p.get("id") for p in parents],
                "seeds": seeds,
                "next_generation": next_gen,
                "population_size": population_size,
            },
            artifacts=[],
        )
