"""Contract tests for the skill execution engine (RFC #349 phase 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.skill_engine import SkillEngineError, resolve_value, validate_run_inputs

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

FRONTMATTER = {
    "name": "test_skill",
    "version": "1.0",
    "inputs": {
        "topic": {"type": "string", "required": True},
        "duration": {"type": "number", "default": 30},
        "style": {"type": "enum", "values": ["cinematic", "casual"], "default": "cinematic"},
    },
}


def test_resolve_value_whole_string_preserves_type():
    run_inputs = {"topic": {"nested": "dict"}}
    assert resolve_value("${inputs.topic}", run_inputs, {}) == {"nested": "dict"}


def test_resolve_value_embedded_placeholder_stringifies():
    run_inputs = {"topic": "black holes"}
    result = resolve_value("a video about ${inputs.topic}", run_inputs, {})
    assert result == "a video about black holes"


def test_resolve_value_dotted_path_into_step_output():
    completed_steps = {"draft_rig": {"output": {"rig_plan": {"parts": 3}}}}
    result = resolve_value("${steps.draft_rig.output.rig_plan}", {}, completed_steps)
    assert result == {"parts": 3}


def test_resolve_value_unresolved_input_raises():
    with pytest.raises(SkillEngineError, match="topic"):
        resolve_value("${inputs.topic}", {}, {})


def test_resolve_value_unresolved_step_raises():
    with pytest.raises(SkillEngineError, match="missing_step"):
        resolve_value("${steps.missing_step.output}", {}, {})


def test_resolve_value_recurses_through_dict():
    run_inputs = {"topic": "black holes"}
    value = {"a": "${inputs.topic}", "b": [1, "${inputs.topic}"]}
    result = resolve_value(value, run_inputs, {})
    assert result == {"a": "black holes", "b": [1, "black holes"]}


def test_validate_run_inputs_applies_defaults():
    resolved = validate_run_inputs(FRONTMATTER, {"topic": "black holes"})
    assert resolved["duration"] == 30
    assert resolved["style"] == "cinematic"
    assert resolved["topic"] == "black holes"


def test_validate_run_inputs_missing_required_raises():
    with pytest.raises(SkillEngineError, match="topic"):
        validate_run_inputs(FRONTMATTER, {})


def test_validate_run_inputs_type_mismatch_raises():
    with pytest.raises(SkillEngineError, match="duration"):
        validate_run_inputs(FRONTMATTER, {"topic": "x", "duration": "not a number"})


def test_validate_run_inputs_enum_violation_raises():
    with pytest.raises(SkillEngineError, match="style"):
        validate_run_inputs(FRONTMATTER, {"topic": "x", "style": "invalid"})


from lib.skill_engine import build_dag, compute_waves


def test_build_dag_linear_chain_orders_dependency():
    steps = [
        {"id": "a", "tool": "t", "inputs": {}},
        {"id": "b", "tool": "t", "inputs": {"x": "${steps.a.output}"}},
    ]
    dag = build_dag(steps)
    assert dag == {"a": set(), "b": {"a"}}
    assert compute_waves(dag) == [["a"], ["b"]]


def test_compute_waves_preserves_declaration_order_within_a_wave():
    # "second" is declared before "first" and neither depends on the other.
    # The wave must list them in declaration order, not alphabetical order
    # — this is exactly the ordering the real rig-plan-director pilot
    # relies on to decide which pending step surfaces first.
    steps = [
        {"id": "second", "tool": "t", "inputs": {}},
        {"id": "first", "tool": "t", "inputs": {}},
    ]
    dag = build_dag(steps)
    assert compute_waves(dag) == [["second", "first"]]


def test_build_dag_unknown_step_reference_raises():
    steps = [{"id": "a", "tool": "t", "inputs": {"x": "${steps.missing.output}"}}]
    with pytest.raises(SkillEngineError, match="missing"):
        build_dag(steps)


def test_build_dag_cycle_raises():
    steps = [
        {"id": "a", "tool": "t", "inputs": {"x": "${steps.b.output}"}},
        {"id": "b", "tool": "t", "inputs": {"x": "${steps.a.output}"}},
    ]
    with pytest.raises(SkillEngineError, match="Cycle detected"):
        build_dag(steps)


from tools.base_tool import BaseTool
from lib.skill_engine import run_skill


class _StubAutoTool(BaseTool):
    name = "stub_auto_tool"
    capability = "test"
    agent_skills: list = []

    def execute(self, inputs):
        raise AssertionError("the engine must never call a tool itself — it only plans")


class _ManualTool(BaseTool):
    name = "manual_tool"
    capability = "test"
    agent_skills = ["some-layer3-skill"]

    def execute(self, inputs):
        raise AssertionError("the engine must never call a tool itself — it only plans")


def _frontmatter_with_steps(steps):
    return {
        "name": "test_skill",
        "version": "1.0",
        "inputs": {"topic": {"type": "string", "required": True}},
        "steps": steps,
    }


def test_run_skill_never_calls_a_tool(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])

    state = run_skill(frontmatter, {"topic": "black holes"}, registry=isolated_tool_registry)

    assert state["status"] == "paused"
    assert [p["step_id"] for p in state["pending_steps"]] == ["a"]
    assert state["pending_steps"][0]["tool"] == "stub_auto_tool"
    assert state["pending_steps"][0]["agent_skills"] == []
    assert state["pending_steps"][0]["resolved_inputs"] == {"topic": "black holes"}


def test_run_skill_pauses_on_agent_supervised_tool(isolated_tool_registry):
    isolated_tool_registry.register(_ManualTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "manual_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])

    state = run_skill(frontmatter, {"topic": "x"}, registry=isolated_tool_registry)

    assert state["status"] == "paused"
    assert state["pending_steps"][0]["step_id"] == "a"
    assert state["pending_steps"][0]["tool"] == "manual_tool"
    assert state["pending_steps"][0]["agent_skills"] == ["some-layer3-skill"]
    assert state["pending_steps"][0]["resolved_inputs"] == {"topic": "x"}


def test_run_skill_batches_independent_steps_into_one_wave(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    isolated_tool_registry.register(_ManualTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
        {"id": "b", "tool": "manual_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])

    state = run_skill(frontmatter, {"topic": "x"}, registry=isolated_tool_registry)

    # Both are ready (neither depends on the other) and neither has been
    # executed — the whole wave surfaces together so the agent decides
    # ordering/concurrency itself; the engine never forces it.
    assert state["status"] == "paused"
    assert [p["step_id"] for p in state["pending_steps"]] == ["a", "b"]
    assert state["completed_steps"] == {}


def test_resume_skill_partial_wave_leaves_remaining_step_pending(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
        {"id": "b", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])
    run_inputs = {"topic": "x"}
    state = run_skill(frontmatter, run_inputs, registry=isolated_tool_registry)
    assert [p["step_id"] for p in state["pending_steps"]] == ["a", "b"]

    state = resume_skill(
        frontmatter, run_inputs, state,
        step_outputs={"a": {"received": {"topic": "x"}}},
        registry=isolated_tool_registry,
    )

    assert state["status"] == "paused"
    assert [p["step_id"] for p in state["pending_steps"]] == ["b"]
    assert state["completed_steps"]["a"]["output"] == {"received": {"topic": "x"}}


def test_resume_skill_chains_step_output_into_next_wave(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
        {"id": "b", "tool": "stub_auto_tool", "inputs": {"topic": "${steps.a.output.received.topic}"}},
    ])
    run_inputs = {"topic": "black holes"}
    state = run_skill(frontmatter, run_inputs, registry=isolated_tool_registry)

    state = resume_skill(
        frontmatter, run_inputs, state,
        step_outputs={"a": {"received": {"topic": "black holes"}}},
        registry=isolated_tool_registry,
    )

    assert state["status"] == "paused"
    assert state["pending_steps"][0]["resolved_inputs"] == {"topic": "black holes"}

    state = resume_skill(
        frontmatter, run_inputs, state,
        step_outputs={"b": {"received": {"topic": "black holes"}}},
        registry=isolated_tool_registry,
    )

    assert state["status"] == "completed"
    assert state["completed_steps"]["b"]["output"] == {"received": {"topic": "black holes"}}
    assert state["outputs"] == {}


def test_resume_skill_rejects_output_for_a_step_not_currently_pending(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
        {"id": "b", "tool": "stub_auto_tool", "inputs": {"topic": "${steps.a.output}"}},
    ])
    run_inputs = {"topic": "x"}
    state = run_skill(frontmatter, run_inputs, registry=isolated_tool_registry)

    with pytest.raises(SkillEngineError, match="not currently pending"):
        resume_skill(
            frontmatter, run_inputs, state,
            step_outputs={"b": {}},
            registry=isolated_tool_registry,
        )


def test_run_skill_unknown_tool_name_raises(isolated_tool_registry):
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "nonexistent_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])

    state = run_skill(frontmatter, {"topic": "x"}, registry=isolated_tool_registry)

    assert state["status"] == "failed"
    assert "nonexistent_tool" in state["error"]


def test_build_dag_rejects_duplicate_step_ids():
    steps = [
        {"id": "a", "tool": "t", "inputs": {}},
        {"id": "a", "tool": "t", "inputs": {}},
    ]
    with pytest.raises(SkillEngineError, match="Duplicate step id"):
        build_dag(steps)


def test_run_skill_rejects_duplicate_step_ids(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {}},
        {"id": "a", "tool": "stub_auto_tool", "inputs": {}},
    ])

    with pytest.raises(SkillEngineError, match="Duplicate step id"):
        run_skill(frontmatter, {"topic": "x"}, registry=isolated_tool_registry)


from lib.skill_frontmatter import load_skill_frontmatter
from lib.skill_engine import resume_skill
from tools.tool_registry import registry as global_registry

RIG_PLAN_DIRECTOR = (
    PROJECT_ROOT
    / "skills"
    / "pipelines"
    / "character-animation"
    / "rig-plan-director.md"
)

_VALID_RIG_PLAN = {
    "version": "1.0",
    "characters": [
        {
            "character_id": "fox",
            "parts": [{"id": "body", "kind": "body", "layer": 0}],
            "joints": {},
            "layers": ["body"],
            "required_poses": ["idle"],
        }
    ],
}

_VALID_POSE_LIBRARY = {
    "version": "1.0",
    "characters": [
        {
            "character_id": "fox",
            "poses": {"idle": {"description": "idle pose"}},
        }
    ],
}


def test_resume_skill_requires_a_paused_state(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])
    run_inputs = {"topic": "x"}
    state = run_skill(frontmatter, run_inputs, registry=isolated_tool_registry)
    completed_state = resume_skill(
        frontmatter, run_inputs, state,
        step_outputs={"a": {}},
        registry=isolated_tool_registry,
    )
    assert completed_state["status"] == "completed"

    with pytest.raises(SkillEngineError, match="not paused"):
        resume_skill(frontmatter, run_inputs, completed_state, step_outputs={}, registry=isolated_tool_registry)


def test_run_skill_surfaces_both_pilot_steps_in_the_first_wave():
    global_registry.discover()
    frontmatter = load_skill_frontmatter(RIG_PLAN_DIRECTOR)

    state = run_skill(frontmatter, {"character_design": "a friendly fox"}, registry=global_registry)

    # draft_rig and draft_poses are independent (both depend only on
    # inputs.character_design) so they land in the same wave together.
    assert state["status"] == "paused"
    step_ids = [p["step_id"] for p in state["pending_steps"]]
    assert step_ids == ["draft_rig", "draft_poses"]
    by_id = {p["step_id"]: p for p in state["pending_steps"]}
    assert by_id["draft_rig"]["tool"] == "svg_rig_builder"
    assert by_id["draft_poses"]["tool"] == "pose_library_builder"
    real_rig_tool = global_registry.get("svg_rig_builder")
    assert by_id["draft_rig"]["agent_skills"] == list(real_rig_tool.agent_skills)


def test_resume_skill_completes_pilot_and_validates_declared_outputs():
    global_registry.discover()
    frontmatter = load_skill_frontmatter(RIG_PLAN_DIRECTOR)
    run_inputs = {"character_design": "a friendly fox"}

    state = run_skill(frontmatter, run_inputs, registry=global_registry)
    state = resume_skill(
        frontmatter, run_inputs, state,
        step_outputs={"draft_rig": _VALID_RIG_PLAN},
        registry=global_registry,
    )

    assert state["status"] == "paused"
    assert [p["step_id"] for p in state["pending_steps"]] == ["draft_poses"]

    state = resume_skill(
        frontmatter, run_inputs, state,
        step_outputs={"draft_poses": _VALID_POSE_LIBRARY},
        registry=global_registry,
    )

    assert state["status"] == "completed"
    assert state["completed_steps"]["draft_rig"]["output"] == _VALID_RIG_PLAN
    assert state["completed_steps"]["draft_poses"]["output"] == _VALID_POSE_LIBRARY
    assert state["outputs"] == {"rig_plan": _VALID_RIG_PLAN, "pose_library": _VALID_POSE_LIBRARY}


def test_resume_skill_rejects_completion_when_declared_output_is_schema_invalid():
    global_registry.discover()
    frontmatter = load_skill_frontmatter(RIG_PLAN_DIRECTOR)
    run_inputs = {"character_design": "a friendly fox"}

    state = run_skill(frontmatter, run_inputs, registry=global_registry)
    state = resume_skill(
        frontmatter, run_inputs, state,
        # Missing every required rig_plan field — not a real rig plan.
        step_outputs={"draft_rig": {"rig_id": "fox_rig_v1"}},
        registry=global_registry,
    )

    with pytest.raises(SkillEngineError, match="rig_plan"):
        resume_skill(
            frontmatter, run_inputs, state,
            step_outputs={"draft_poses": _VALID_POSE_LIBRARY},
            registry=global_registry,
        )
