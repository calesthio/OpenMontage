"""Tool bridge: file ops, artifact writes, compose routing, budget pre-check."""

from __future__ import annotations

import json

import pytest

from app.runner.tool_bridge import execute_tool, BudgetExceededError


class _FakeResult:
    def __init__(self, success=True, cost_usd=0.0, artifacts=None):
        self.success = success
        self.cost_usd = cost_usd
        self.artifacts = artifacts or []
        self.data = {}
        self.error = None


class FakeTool:
    """Minimal BaseTool stand-in — no network."""

    def __init__(self, capability="video_generation", cost=0.0):
        self.capability = capability
        self._cost = cost
        self.executed_with = None

    def estimate_cost(self, inputs):
        return self._cost

    def execute(self, inputs):
        self.executed_with = inputs
        return _FakeResult(cost_usd=self._cost, artifacts=[inputs.get("output_path", "")])


def _run_tool(project_dir, tool, monkeypatch, **kw):
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "discover", lambda: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    args = {"tool_name": "maas_video", "inputs": {"prompt": "x", "operation": "t2v"}}
    return execute_tool("run_openmontage_tool", args, project_dir, **kw)


def test_read_file_missing(tmp_path):
    out = execute_tool("read_file", {"path": "nope/does-not-exist.xyz"}, tmp_path)
    assert out.startswith("ERROR: File not found")


def test_write_artifact_and_missing_params(tmp_path):
    ok = execute_tool("write_artifact", {"artifact_name": "research", "content": {"a": 1}}, tmp_path)
    assert "Written to" in ok
    written = json.loads((tmp_path / "artifacts" / "research.json").read_text())
    assert written == {"a": 1}

    assert "requires 'artifact_name'" in execute_tool("write_artifact", {"content": {}}, tmp_path)
    assert "requires 'content'" in execute_tool("write_artifact", {"artifact_name": "x"}, tmp_path)


def test_unknown_tool(tmp_path):
    assert execute_tool("bogus", {}, tmp_path).startswith("ERROR: Unknown tool")


def test_compose_routes_final_to_renders(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "discover", lambda: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool("run_openmontage_tool",
                 {"tool_name": "video_compose", "inputs": {"operation": "compose"}},
                 tmp_path)
    assert tool.executed_with["output_path"].endswith("/renders/final.mp4")


def test_video_post_non_compose_stays_in_assets(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_post")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "discover", lambda: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)
    execute_tool("run_openmontage_tool",
                 {"tool_name": "video_compose", "inputs": {"operation": "trim"}},
                 tmp_path)
    op = tool.executed_with["output_path"]
    assert "/assets/video_post/" in op and "renders" not in op


def test_repeated_calls_to_same_tool_get_distinct_output_paths(tmp_path, monkeypatch):
    # Regression: a fixed "{tool_name}_output.{ext}" filename meant every call
    # to the same tool within a job silently overwrote the previous one's
    # file. Confirmed live: an assets-stage run that generated 6 distinct
    # video clips (without the agent overriding output_path) left exactly ONE
    # file on disk — each call clobbered the last.
    tool = FakeTool(capability="video_generation")
    from tools import tool_registry
    monkeypatch.setattr(tool_registry.registry, "discover", lambda: None)
    monkeypatch.setattr(tool_registry.registry, "get", lambda name: tool)

    paths = []
    for _ in range(5):
        execute_tool("run_openmontage_tool",
                     {"tool_name": "maas_video", "inputs": {"prompt": "same prompt every time"}},
                     tmp_path)
        paths.append(tool.executed_with["output_path"])

    assert len(set(paths)) == 5, f"expected 5 distinct paths, got {paths}"
    assert all(p.endswith(".mp4") for p in paths)


def test_budget_precheck_blocks_over_budget(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation", cost=5.0)
    acc = []
    with pytest.raises(BudgetExceededError):
        _run_tool(tmp_path, tool, monkeypatch, cost_accumulator=acc, budget_cny=10.0, base_cost=8.0)
    # blocked before execution → nothing spent, tool not run
    assert acc == []
    assert tool.executed_with is None


def test_budget_precheck_allows_within_budget(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation", cost=5.0)
    acc = []
    out = _run_tool(tmp_path, tool, monkeypatch, cost_accumulator=acc, budget_cny=100.0, base_cost=8.0)
    assert json.loads(out)["success"] is True
    assert acc == [5.0]                      # CNY cost accumulated
    assert tool.executed_with is not None


def test_no_budget_runs_freely(tmp_path, monkeypatch):
    tool = FakeTool(capability="video_generation", cost=5.0)
    acc = []
    _run_tool(tmp_path, tool, monkeypatch, cost_accumulator=acc, budget_cny=None, base_cost=0.0)
    assert acc == [5.0]


def test_cost_tracker_ledger_records(tmp_path, monkeypatch):
    from tools.cost_tracker import CostTracker
    from lib.config_model import BudgetMode
    ct = CostTracker(budget_total_usd=1e9, reserve_pct=0.0, single_action_approval_usd=1e9,
                     require_approval_for_new_paid_tool=False, mode=BudgetMode.OBSERVE,
                     cost_log_path=tmp_path / "cost_log.json")
    tool = FakeTool(capability="video_generation", cost=5.0)
    _run_tool(tmp_path, tool, monkeypatch, cost_accumulator=[], cost_tracker=ct)
    assert ct.cost_snapshot()["total_spent_usd"] == 5.0
    assert (tmp_path / "cost_log.json").exists()
