"""Skill execution engine (RFC #349 phase 2): interpolation, DAG scheduling,
and step execution gated by Rule Zero (AGENT_GUIDE.md).

A step whose tool declares no agent_skills is deterministic wiring the
engine executes directly. A step whose tool declares agent_skills needs
Layer 3 prompting guidance that only the agent can apply — the engine
pauses and hands control back rather than calling it.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional


class SkillEngineError(ValueError):
    """Raised on interpolation, DAG, or execution errors in the skill engine."""


_FULL_PLACEHOLDER_RE = re.compile(r"^\$\{([^}]+)\}$")
_EMBEDDED_PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")

_TYPE_MAP: dict[str, Any] = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
}


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
    """
    step_ids = {step["id"] for step in steps}
    dag: dict[str, set[str]] = {}
    for step in steps:
        deps = _find_step_refs(step.get("inputs", {}))
        unknown = deps - step_ids
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


class _StepFailure(Exception):
    def __init__(self, step_id: str, error: str):
        self.step_id = step_id
        self.error = error
        super().__init__(f"Step {step_id!r} failed: {error}")


def _execute_auto_step(step: dict, resolved_inputs: dict, registry: Any) -> dict:
    tool = registry.get(step["tool"])
    result = tool.execute(resolved_inputs)
    if not result.success:
        raise _StepFailure(step["id"], result.error or "unknown error")
    return {"tool": step["tool"], "output": result.data}


def run_skill(frontmatter: dict, run_inputs: dict, registry: Optional[Any] = None) -> dict:
    """Validate run_inputs, build the DAG, and execute waves until the DAG
    completes, a step needs the agent, or a tool call fails."""
    if registry is None:
        from tools.tool_registry import registry as default_registry
        registry = default_registry

    resolved_run_inputs = validate_run_inputs(frontmatter, run_inputs)
    steps = frontmatter.get("steps", [])
    steps_by_id = {step["id"]: step for step in steps}
    dag = build_dag(steps)
    waves = compute_waves(dag)

    state: dict = {
        "status": "running",
        "completed_steps": {},
        "pending_step": None,
        "error": None,
    }
    return _run_waves(steps_by_id, waves, resolved_run_inputs, state, registry)


def _run_waves(
    steps_by_id: dict, waves: list[list[str]], run_inputs: dict, state: dict, registry: Any
) -> dict:
    completed_steps = state["completed_steps"]

    for wave in waves:
        pending_in_wave = [s for s in wave if s not in completed_steps]
        if not pending_in_wave:
            continue

        auto_steps = []
        manual_step_id = None
        manual_pending = None
        for step_id in pending_in_wave:
            step = steps_by_id[step_id]
            tool = registry.get(step["tool"])
            if tool is None:
                state["status"] = "failed"
                state["error"] = f"Step {step_id!r} references unknown tool {step['tool']!r}"
                return state
            resolved_inputs = resolve_value(step.get("inputs", {}), run_inputs, completed_steps)
            if tool.agent_skills:
                if manual_step_id is None:
                    manual_step_id = step_id
                    manual_pending = {
                        "step_id": step_id,
                        "tool": step["tool"],
                        "agent_skills": list(tool.agent_skills),
                        "resolved_inputs": resolved_inputs,
                    }
                continue
            auto_steps.append((step_id, step, resolved_inputs))

        run_parallel = any(steps_by_id[s].get("parallel") for s in pending_in_wave)
        try:
            if run_parallel and len(auto_steps) > 1:
                with ThreadPoolExecutor(max_workers=len(auto_steps)) as executor:
                    futures = {
                        step_id: executor.submit(_execute_auto_step, step, resolved_inputs, registry)
                        for step_id, step, resolved_inputs in auto_steps
                    }
                    for step_id, future in futures.items():
                        completed_steps[step_id] = future.result()
            else:
                for step_id, step, resolved_inputs in auto_steps:
                    completed_steps[step_id] = _execute_auto_step(step, resolved_inputs, registry)
        except _StepFailure as failure:
            state["status"] = "failed"
            state["error"] = failure.error
            return state

        if manual_step_id is not None:
            state["status"] = "paused"
            state["pending_step"] = manual_pending
            return state

    state["status"] = "completed"
    state["pending_step"] = None
    return state


def resume_skill(
    frontmatter: dict,
    run_inputs: dict,
    state: dict,
    step_output: Any,
    registry: Optional[Any] = None,
) -> dict:
    """Inject step_output as the completed result for state['pending_step'],
    then continue executing remaining waves. Raises SkillEngineError if
    state['status'] != 'paused'."""
    if state.get("status") != "paused" or state.get("pending_step") is None:
        raise SkillEngineError("resume_skill called on a state that is not paused")
    if registry is None:
        from tools.tool_registry import registry as default_registry
        registry = default_registry

    resolved_run_inputs = validate_run_inputs(frontmatter, run_inputs)
    pending = state["pending_step"]
    new_state: dict = {
        "status": "running",
        "completed_steps": dict(state["completed_steps"]),
        "pending_step": None,
        "error": None,
    }
    new_state["completed_steps"][pending["step_id"]] = {
        "tool": pending["tool"],
        "output": step_output,
    }

    steps = frontmatter.get("steps", [])
    steps_by_id = {step["id"]: step for step in steps}
    dag = build_dag(steps)
    waves = compute_waves(dag)
    return _run_waves(steps_by_id, waves, resolved_run_inputs, new_state, registry)
