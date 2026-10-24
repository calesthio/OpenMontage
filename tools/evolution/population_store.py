"""Population store for the Hermes Creative Flywheel.

Persists evolutionary generations of content artifacts so the
Script -> Render -> Score -> Breed loop has durable memory. Each "individual"
is one rendered video concept (a generation's artifact payload), scored by
``breed_scorer`` and crossed/mutated by ``breed_mutator``.

Storage is a single JSONL file under ``projects/<project>/flywheel/population.jsonl``
so it shows up on the Backlot board (one project per flywheel run). The file is
append-only per generation; the store also maintains a small ``state.json`` with
the current generation number and best score so a run can resume.

This tool is intentionally pure-local and free (no network, no API keys).
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

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

# Population lives inside a Backlot project so the board renders it.
_POP_FILENAME = "population.jsonl"
_STATE_FILENAME = "flywheel_state.json"


class PopulationStore(BaseTool):
    name = "population_store"
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
        "flywheel_persist",
        "flywheel_load_generation",
        "flywheel_load_population",
        "flywheel_state",
    ]
    input_schema = {
        "type": "object",
        "required": ["action", "project_dir"],
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "record",
                    "load_generation",
                    "load_population",
                    "load_best",
                    "state",
                ],
                "description": (
                    "record: append one individual to a generation. "
                    "load_generation: return all individuals of a generation. "
                    "load_population: return every individual across generations. "
                    "load_best: return the highest-scoring individual so far. "
                    "state: return {generation, best_score, count}."
                ),
            },
            "project_dir": {
                "type": "string",
                "description": "Backlot project directory (projects/<name>).",
            },
            "individual": {
                "type": "object",
                "description": (
                    "Required for action=record. One scored individual: "
                    "{id, generation, parent_ids, pipeline, topic, artifact, "
                    "score, created_at, notes}."
                ),
            },
            "generation": {
                "type": "integer",
                "description": "Generation number (required for load_generation).",
            },
            "top_k": {
                "type": "integer",
                "description": "For load_population/load_best: return top-K by score.",
            },
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "count": {"type": "integer"},
            "generation": {"type": "integer"},
            "best_score": {"type": "number"},
            "individuals": {"type": "array"},
            "best": {"type": "object"},
            "state": {"type": "object"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=32, vram_mb=0, disk_mb=1, network_required=False
    )
    side_effects = ["writes population.jsonl + flywheel_state.json under project_dir"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    # ----- helpers -----------------------------------------------------

    def _flywheel_dir(self, project_dir: str) -> Path:
        p = Path(project_dir)
        # tolerate being passed a sub-path; normalize to project root
        return p / "flywheel"

    def _read_all(self, flywheel_dir: Path) -> list[dict[str, Any]]:
        pop = flywheel_dir / _POP_FILENAME
        if not pop.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in pop.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def _read_state(self, flywheel_dir: Path) -> dict[str, Any]:
        state_path = flywheel_dir / _STATE_FILENAME
        if state_path.exists():
            try:
                return json.loads(state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"generation": 0, "best_score": 0.0, "count": 0}

    def _write_state(self, flywheel_dir: Path, state: dict[str, Any]) -> None:
        flywheel_dir.mkdir(parents=True, exist_ok=True)
        (flywheel_dir / _STATE_FILENAME).write_text(
            json.dumps(state, indent=2, default=str), encoding="utf-8"
        )

    # ----- execute -----------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        action = inputs.get("action")
        project_dir = inputs.get("project_dir")
        if not action or not project_dir:
            return ToolResult(
                success=False, error="action and project_dir are required"
            )
        flywheel_dir = self._flywheel_dir(project_dir)
        started = time.monotonic()
        try:
            if action == "record":
                return self._record(flywheel_dir, inputs)
            if action == "load_generation":
                gen = inputs.get("generation")
                if gen is None:
                    return ToolResult(
                        success=False, error="generation required for load_generation"
                    )
                individuals = [
                    i for i in self._read_all(flywheel_dir) if i.get("generation") == gen
                ]
                return ToolResult(
                    success=True,
                    data={"action": action, "generation": gen, "individuals": individuals},
                )
            if action == "load_population":
                top_k = inputs.get("top_k")
                individuals = self._read_all(flywheel_dir)
                individuals.sort(key=lambda i: float(i.get("score", 0.0)), reverse=True)
                if top_k:
                    individuals = individuals[:top_k]
                return ToolResult(
                    success=True,
                    data={"action": action, "individuals": individuals},
                )
            if action == "load_best":
                top_k = inputs.get("top_k", 1)
                individuals = self._read_all(flywheel_dir)
                individuals.sort(key=lambda i: float(i.get("score", 0.0)), reverse=True)
                best = individuals[:top_k]
                return ToolResult(
                    success=True,
                    data={
                        "action": action,
                        "best": best[0] if best else None,
                        "individuals": best,
                    },
                )
            if action == "state":
                state = self._read_state(flywheel_dir)
                return ToolResult(
                    success=True, data={"action": action, "state": state}
                )
            return ToolResult(success=False, error=f"unknown action: {action}")
        except Exception as exc:  # never crash the loop on storage issues
            return ToolResult(
                success=False,
                error=f"population_store error: {exc}",
                duration_seconds=round(time.monotonic() - started, 3),
            )

    def _record(self, flywheel_dir: Path, inputs: dict[str, Any]) -> ToolResult:
        individual = inputs.get("individual")
        if not isinstance(individual, dict):
            return ToolResult(success=False, error="individual object required for record")
        individual.setdefault("id", uuid.uuid4().hex[:12])
        individual.setdefault("created_at", time.time())
        # score must be numeric for ranking
        try:
            score = float(individual.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        individual["score"] = score

        flywheel_dir.mkdir(parents=True, exist_ok=True)
        pop = flywheel_dir / _POP_FILENAME
        with pop.open("a", encoding="utf-8") as f:
            f.write(json.dumps(individual, default=str) + "\n")

        # update state: best generation number seen + best score
        state = self._read_state(flywheel_dir)
        gen = int(individual.get("generation", 0))
        state["generation"] = max(int(state.get("generation", 0)), gen)
        state["best_score"] = max(float(state.get("best_score", 0.0)), score)
        state["count"] = state.get("count", 0) + 1
        self._write_state(flywheel_dir, state)

        return ToolResult(
            success=True,
            data={
                "action": "record",
                "id": individual["id"],
                "generation": gen,
                "score": score,
                "state": state,
            },
            artifacts=[str(pop)],
        )
