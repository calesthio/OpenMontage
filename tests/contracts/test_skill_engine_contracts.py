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


from tools.base_tool import BaseTool, ToolResult
from lib.skill_engine import run_skill


class _StubAutoTool(BaseTool):
    name = "stub_auto_tool"
    capability = "test"
    agent_skills: list = []

    def execute(self, inputs):
        return ToolResult(success=True, data={"received": inputs})


class _FailingAutoTool(BaseTool):
    name = "failing_auto_tool"
    capability = "test"
    agent_skills: list = []

    def execute(self, inputs):
        return ToolResult(success=False, error="boom")


class _ManualTool(BaseTool):
    name = "manual_tool"
    capability = "test"
    agent_skills = ["some-layer3-skill"]

    def execute(self, inputs):
        raise AssertionError("engine must not auto-execute a tool with agent_skills")


def _frontmatter_with_steps(steps):
    return {
        "name": "test_skill",
        "version": "1.0",
        "inputs": {"topic": {"type": "string", "required": True}},
        "steps": steps,
    }


def test_run_skill_completes_independent_auto_steps(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
        {"id": "b", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])

    state = run_skill(frontmatter, {"topic": "black holes"}, registry=isolated_tool_registry)

    assert state["status"] == "completed"
    assert state["completed_steps"]["a"]["output"]["received"]["topic"] == "black holes"
    assert state["completed_steps"]["b"]["output"]["received"]["topic"] == "black holes"
    assert state["pending_step"] is None


def test_run_skill_chains_step_output_into_next_step(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
        {"id": "b", "tool": "stub_auto_tool", "inputs": {"topic": "${steps.a.output.received.topic}"}},
    ])

    state = run_skill(frontmatter, {"topic": "black holes"}, registry=isolated_tool_registry)

    assert state["status"] == "completed"
    assert state["completed_steps"]["b"]["output"]["received"]["topic"] == "black holes"


def test_run_skill_stops_on_tool_failure(isolated_tool_registry):
    isolated_tool_registry.register(_FailingAutoTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "failing_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])

    state = run_skill(frontmatter, {"topic": "x"}, registry=isolated_tool_registry)

    assert state["status"] == "failed"
    assert state["error"] == "boom"
    assert "a" not in state["completed_steps"]


def test_run_skill_pauses_on_agent_supervised_tool(isolated_tool_registry):
    isolated_tool_registry.register(_ManualTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "manual_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])

    state = run_skill(frontmatter, {"topic": "x"}, registry=isolated_tool_registry)

    assert state["status"] == "paused"
    assert state["pending_step"]["step_id"] == "a"
    assert state["pending_step"]["tool"] == "manual_tool"
    assert state["pending_step"]["agent_skills"] == ["some-layer3-skill"]
    assert state["pending_step"]["resolved_inputs"] == {"topic": "x"}


def test_run_skill_runs_auto_steps_before_pausing_on_manual_step_in_same_wave(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    isolated_tool_registry.register(_ManualTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
        {"id": "b", "tool": "manual_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])

    state = run_skill(frontmatter, {"topic": "x"}, registry=isolated_tool_registry)

    assert state["status"] == "paused"
    assert "a" in state["completed_steps"]
    assert state["pending_step"]["step_id"] == "b"


def test_run_skill_unknown_tool_name_raises(isolated_tool_registry):
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "nonexistent_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])

    state = run_skill(frontmatter, {"topic": "x"}, registry=isolated_tool_registry)

    assert state["status"] == "failed"
    assert "nonexistent_tool" in state["error"]


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


def test_resume_skill_requires_a_paused_state(isolated_tool_registry):
    isolated_tool_registry.register(_StubAutoTool())
    frontmatter = _frontmatter_with_steps([
        {"id": "a", "tool": "stub_auto_tool", "inputs": {"topic": "${inputs.topic}"}},
    ])
    completed_state = run_skill(frontmatter, {"topic": "x"}, registry=isolated_tool_registry)
    assert completed_state["status"] == "completed"

    with pytest.raises(SkillEngineError, match="not paused"):
        resume_skill(frontmatter, {"topic": "x"}, completed_state, step_output={}, registry=isolated_tool_registry)


def test_run_skill_pauses_on_first_real_pilot_step():
    global_registry.discover()
    frontmatter = load_skill_frontmatter(RIG_PLAN_DIRECTOR)

    state = run_skill(frontmatter, {"character_design": "a friendly fox"}, registry=global_registry)

    assert state["status"] == "paused"
    assert state["pending_step"]["step_id"] == "draft_rig"
    assert state["pending_step"]["tool"] == "svg_rig_builder"
    real_tool = global_registry.get("svg_rig_builder")
    assert state["pending_step"]["agent_skills"] == list(real_tool.agent_skills)


def test_resume_skill_continues_to_next_pause_point_then_completes():
    global_registry.discover()
    frontmatter = load_skill_frontmatter(RIG_PLAN_DIRECTOR)
    run_inputs = {"character_design": "a friendly fox"}

    state = run_skill(frontmatter, run_inputs, registry=global_registry)
    state = resume_skill(
        frontmatter, run_inputs, state,
        step_output={"rig_id": "fox_rig_v1"},
        registry=global_registry,
    )

    assert state["status"] == "paused"
    assert state["pending_step"]["step_id"] == "draft_poses"
    assert state["pending_step"]["tool"] == "pose_library_builder"

    state = resume_skill(
        frontmatter, run_inputs, state,
        step_output={"poses": ["idle", "walk"]},
        registry=global_registry,
    )

    assert state["status"] == "completed"
    assert state["completed_steps"]["draft_rig"]["output"] == {"rig_id": "fox_rig_v1"}
    assert state["completed_steps"]["draft_poses"]["output"] == {"poses": ["idle", "walk"]}
