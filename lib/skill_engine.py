"""Skill execution engine (RFC #349 phase 2): interpolation, DAG scheduling,
and step planning gated by Rule Zero (AGENT_GUIDE.md).

This module never calls a tool. It resolves `${...}` references, orders a
skill's declared `steps` into dependency waves, and hands the agent the
next wave's *unresolved* steps (`pending_steps`) — including their
resolved inputs and each tool's declared `agent_skills`. The agent (or
whatever thin driver sits above the engine, itself still bound by Rule
Zero) decides how and whether to call each tool, in what order, and
whether to run any of them concurrently; it then reports results back via
`resume_skill`. The engine is a planner, not a second control plane —
`agent_skills == []` is informational (it tells the agent it can skip
Layer 3 reading for that tool), never a license for the engine itself to
auto-fire the tool.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

import jsonschema


class SkillEngineError(ValueError):
    """Raised on interpolation, DAG, or execution errors in the skill engine."""


_FULL_PLACEHOLDER_RE = re.compile(r"^\$\{([^}]+)\}$")
_EMBEDDED_PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")

_TYPE_MAP: dict[str, Any] = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
}

ARTIFACT_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas" / "artifacts"


def _walk_path(value: Any, path_parts: list[str], ref: str) -> Any:
    for part in path_parts:
        if not isinstance(value, dict) or part not in value:
            raise SkillEngineError(
                f"Unresolved reference '${{{ref}}}': path segment {part!r} not found"
            )
        value = value[part]
    return value


def _resolve_reference(ref: str, run_inputs: dict, completed_steps: dict) -> Any:
    parts = ref.split(".")
    if parts[0] == "inputs":
        if len(parts) < 2:
            raise SkillEngineError(f"Malformed reference '${{{ref}}}'")
        key = parts[1]
        if key not in run_inputs:
            raise SkillEngineError(
                f"Unresolved reference '${{{ref}}}': run input {key!r} not provided"
            )
        return _walk_path(run_inputs[key], parts[2:], ref)
    if parts[0] == "steps":
        if len(parts) < 3 or parts[2] != "output":
            raise SkillEngineError(
                f"Malformed reference '${{{ref}}}': expected steps.<id>.output[...]"
            )
        step_id = parts[1]
        if step_id not in completed_steps:
            raise SkillEngineError(
                f"Unresolved reference '${{{ref}}}': step {step_id!r} has not completed"
            )
        return _walk_path(completed_steps[step_id]["output"], parts[3:], ref)
    raise SkillEngineError(f"Unknown reference root '${{{ref}}}'")


def resolve_value(value: Any, run_inputs: dict, completed_steps: dict) -> Any:
    """Recursively resolve ${...} placeholders in value.

    A string that is exactly one placeholder preserves the referenced
    value's original type; an embedded placeholder is stringified in
    place. dicts/lists are walked recursively.
    """
    if isinstance(value, str):
        full_match = _FULL_PLACEHOLDER_RE.match(value)
        if full_match:
            return _resolve_reference(full_match.group(1), run_inputs, completed_steps)
        if "${" in value:
            return _EMBEDDED_PLACEHOLDER_RE.sub(
                lambda m: str(_resolve_reference(m.group(1), run_inputs, completed_steps)),
                value,
            )
        return value
    if isinstance(value, dict):
        return {k: resolve_value(v, run_inputs, completed_steps) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_value(v, run_inputs, completed_steps) for v in value]
    return value


def validate_run_inputs(frontmatter: dict, run_inputs: dict) -> dict:
    """Apply defaults and validate run_inputs against frontmatter['inputs'].

    Returns a new dict (defaults merged in). Raises SkillEngineError on a
    missing required input or a type/enum mismatch.
    """
    declared: dict = frontmatter.get("inputs", {}) or {}
    resolved = dict(run_inputs)
    for key, spec in declared.items():
        if key not in resolved:
            if "default" in spec:
                resolved[key] = spec["default"]
                continue
            if spec.get("required"):
                raise SkillEngineError(f"Missing required input {key!r}")
            continue

        expected_type = spec.get("type")
        if expected_type == "enum":
            values = spec.get("values", [])
            if resolved[key] not in values:
                raise SkillEngineError(
                    f"Input {key!r} value {resolved[key]!r} not in allowed values {values}"
                )
        elif expected_type in _TYPE_MAP and not isinstance(resolved[key], _TYPE_MAP[expected_type]):
            raise SkillEngineError(
                f"Input {key!r} expected type {expected_type!r}, "
                f"got {type(resolved[key]).__name__}"
            )
    return resolved


_STEP_REF_RE = re.compile(r"\$\{steps\.([a-zA-Z0-9_-]+)\.")


def _find_step_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, str):
        refs.update(_STEP_REF_RE.findall(value))
    elif isinstance(value, dict):
        for v in value.values():
            refs.update(_find_step_refs(v))
    elif isinstance(value, list):
        for v in value:
            refs.update(_find_step_refs(v))
    return refs


def build_dag(steps: list[dict]) -> dict[str, set[str]]:
    """Map step_id -> set of step_ids it depends on.

    Dependency edges come only from ${steps.<id>...} references in a
    step's raw `inputs` block — ${inputs.x} never creates a dependency.
    Insertion order matches `steps` declaration order; compute_waves
    relies on this to preserve declaration order within a wave.

    Raises SkillEngineError on a duplicate step id: without this check, a
    later step silently overwrites an earlier one of the same id in every
    id-keyed structure downstream (the DAG, the wave batching, the
    completed-steps ledger), so a malformed skill would execute a
    different step than its declaration suggests.
    """
    seen_ids: set[str] = set()
    for step in steps:
        step_id = step["id"]
        if step_id in seen_ids:
            raise SkillEngineError(f"Duplicate step id {step_id!r} in steps")
        seen_ids.add(step_id)

    dag: dict[str, set[str]] = {}
    for step in steps:
        deps = _find_step_refs(step.get("inputs", {}))
        unknown = deps - seen_ids
        if unknown:
            raise SkillEngineError(
                f"Step {step['id']!r} references unknown step(s): {sorted(unknown)}"
            )
        dag[step["id"]] = deps
    _check_cycles(dag)
    return dag


def _check_cycles(dag: dict[str, set[str]]) -> None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in dag}
    path: list[str] = []

    def visit(node: str) -> None:
        color[node] = GRAY
        path.append(node)
        for dep in dag[node]:
            if color[dep] == GRAY:
                cycle = path[path.index(dep):] + [dep]
                raise SkillEngineError(f"Cycle detected: {' -> '.join(cycle)}")
            if color[dep] == WHITE:
                visit(dep)
        path.pop()
        color[node] = BLACK

    for node in dag:
        if color[node] == WHITE:
            visit(node)


def compute_waves(dag: dict[str, set[str]]) -> list[list[str]]:
    """Topologically batch dag into waves. Each wave's steps have all
    dependencies satisfied by prior waves. Preserves dag's key insertion
    order (== frontmatter declaration order) within each wave rather than
    sorting alphabetically. Assumes build_dag already validated no cycles.
    """
    order = list(dag.keys())
    remaining = set(order)
    completed: set[str] = set()
    waves: list[list[str]] = []
    while remaining:
        ready = [s for s in order if s in remaining and dag[s] <= completed]
        if not ready:
            raise SkillEngineError("Unable to schedule remaining steps (unexpected cycle)")
        waves.append(ready)
        completed.update(ready)
        remaining -= set(ready)
    return waves


def _validate_declared_output(name: str, value: Any) -> None:
    """Best-effort validation of a finished skill output against its
    canonical artifact schema, when one exists under schemas/artifacts/.

    Not every declared output names a canonical artifact (e.g. a plain
    string summary has no schema file), so a missing schema is not an
    error — but when a schema does exist (rig_plan, pose_library, ...),
    the resolved value must satisfy it before the run is allowed to
    report `status: "completed"`.
    """
    schema_path = ARTIFACT_SCHEMA_DIR / f"{name}.schema.json"
    if not schema_path.exists():
        return
    with open(schema_path) as f:
        schema = json.load(f)
    try:
        jsonschema.validate(instance=value, schema=schema)
    except jsonschema.ValidationError as e:
        raise SkillEngineError(
            f"Output {name!r} does not satisfy schemas/artifacts/{name}.schema.json: {e.message}"
        ) from e


def _finalize_outputs(frontmatter: dict, completed_steps: dict) -> dict:
    declared: dict = frontmatter.get("outputs", {}) or {}
    outputs: dict = {}
    for name, spec in declared.items():
        value = resolve_value(spec["source"], {}, completed_steps)
        _validate_declared_output(name, value)
        outputs[name] = value
    return outputs


def _prepare(steps: list[dict]) -> tuple[dict[str, dict], list[list[str]]]:
    dag = build_dag(steps)
    steps_by_id = {step["id"]: step for step in steps}
    waves = compute_waves(dag)
    return steps_by_id, waves


def _advance(
    frontmatter: dict,
    steps_by_id: dict[str, dict],
    waves: list[list[str]],
    run_inputs: dict,
    state: dict,
    registry: Any,
) -> dict:
    """Find the first wave with unresolved steps and return it as
    `pending_steps` for the agent to execute. Never calls a tool."""
    completed_steps = state["completed_steps"]

    for wave in waves:
        pending_ids = [s for s in wave if s not in completed_steps]
        if not pending_ids:
            continue

        pending_steps = []
        for step_id in pending_ids:
            step = steps_by_id[step_id]
            tool = registry.get(step["tool"])
            if tool is None:
                state["status"] = "failed"
                state["pending_steps"] = []
                state["error"] = f"Step {step_id!r} references unknown tool {step['tool']!r}"
                return state
            resolved_inputs = resolve_value(step.get("inputs", {}), run_inputs, completed_steps)
            pending_steps.append(
                {
                    "step_id": step_id,
                    "tool": step["tool"],
                    "agent_skills": list(tool.agent_skills),
                    "parallel": bool(step.get("parallel", False)),
                    "resolved_inputs": resolved_inputs,
                }
            )

        state["status"] = "paused"
        state["pending_steps"] = pending_steps
        return state

    state["status"] = "completed"
    state["pending_steps"] = []
    state["outputs"] = _finalize_outputs(frontmatter, completed_steps)
    return state


def run_skill(frontmatter: dict, run_inputs: dict, registry: Optional[Any] = None) -> dict:
    """Validate run_inputs, build the DAG, and return the first wave's
    steps as `pending_steps` for the agent to execute. The engine never
    calls a tool itself."""
    if registry is None:
        from tools.tool_registry import registry as default_registry
        registry = default_registry

    resolved_run_inputs = validate_run_inputs(frontmatter, run_inputs)
    steps = frontmatter.get("steps", [])
    steps_by_id, waves = _prepare(steps)

    state: dict = {
        "status": "running",
        "completed_steps": {},
        "pending_steps": [],
        "outputs": None,
        "error": None,
    }
    return _advance(frontmatter, steps_by_id, waves, resolved_run_inputs, state, registry)


def resume_skill(
    frontmatter: dict,
    run_inputs: dict,
    state: dict,
    step_outputs: dict[str, Any],
    registry: Optional[Any] = None,
) -> dict:
    """Record agent-supplied outputs for one or more of state['pending_steps'],
    then advance. `step_outputs` maps step_id -> output; it may cover the
    whole current wave or just part of it (the rest stays pending).
    Raises SkillEngineError if state['status'] != 'paused' or if
    step_outputs names a step that isn't currently pending."""
    if state.get("status") != "paused":
        raise SkillEngineError("resume_skill called on a state that is not paused")

    pending_by_id = {p["step_id"]: p for p in state["pending_steps"]}
    unknown = set(step_outputs) - set(pending_by_id)
    if unknown:
        raise SkillEngineError(
            f"step_outputs references step(s) not currently pending: {sorted(unknown)}"
        )

    if registry is None:
        from tools.tool_registry import registry as default_registry
        registry = default_registry

    resolved_run_inputs = validate_run_inputs(frontmatter, run_inputs)
    completed_steps = dict(state["completed_steps"])
    for step_id, output in step_outputs.items():
        completed_steps[step_id] = {"tool": pending_by_id[step_id]["tool"], "output": output}

    steps = frontmatter.get("steps", [])
    steps_by_id, waves = _prepare(steps)

    new_state: dict = {
        "status": "running",
        "completed_steps": completed_steps,
        "pending_steps": [],
        "outputs": None,
        "error": None,
    }
    return _advance(frontmatter, steps_by_id, waves, resolved_run_inputs, new_state, registry)
