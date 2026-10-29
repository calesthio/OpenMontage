"""The budget gate must actually refuse to spend.

Regression: `CostTracker` had no caller anywhere outside its own tests. The
`cap` mode documented in ARCHITECTURE.md as rejecting operations that exceed
the remaining budget could not fire, because nothing called `reserve()`.

These tests drive a fake paid tool through the real `BaseTool` wrapper, so
they exercise the same path a Veo or Kling call takes.
"""

from __future__ import annotations

import json

import pytest

from lib import budget
from lib.checkpoint import init_project, write_checkpoint
from tools.base_tool import (
    BaseTool,
    ToolResult,
    ToolRuntime,
    ToolTier,
)
from tools.cost_tracker import ApprovalRequiredError, BudgetExceededError


class FakePaidTool(BaseTool):
    """Stands in for any ToolRuntime.API provider."""

    name = "fake_paid_tool"
    tier = ToolTier.GENERATE
    runtime = ToolRuntime.API
    unit_cost = 0.25

    def estimate_cost(self, inputs: dict) -> float:
        return float(inputs.get("cost", self.unit_cost))

    def execute(self, inputs: dict) -> ToolResult:
        return ToolResult(success=True, cost_usd=self.estimate_cost(inputs))


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Re-root the canonical projects/ dir into tmp_path.

    A tool call is only attributable to a project when its path resolves under
    the canonical projects root (lib/events.infer_project_dir) — a deliberate
    rule so an arbitrary output_path cannot spawn a ghost project. The budget
    gate inherits that same boundary, so these tests must re-root it rather
    than point at an unrelated tmp dir.
    """
    import lib.events

    root = tmp_path / "projects"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(lib.events, "PROJECTS_DIR", root)
    budget.reset_trackers()
    monkeypatch.delenv("OPENMONTAGE_BUDGET_DISABLED", raising=False)
    monkeypatch.delenv("OPENMONTAGE_APPROVE_TOOLS", raising=False)
    yield
    budget.reset_trackers()


def _project(tmp_path):
    """A project dir the wrapper will attribute the call to."""
    return init_project("proj", title="Budget", pipeline_type="animated-explainer",
                        pipeline_dir=tmp_path / "projects",
                        style_playbook="clean-professional")


def test_ungoverned_outside_a_project(tmp_path, monkeypatch):
    """A call with no owning project is left alone."""
    monkeypatch.setenv("OPENMONTAGE_BUDGET_MODE", "cap")
    monkeypatch.setenv("OPENMONTAGE_BUDGET_TOTAL_USD", "0.0")
    result = FakePaidTool().execute({"cost": 5.0})
    assert result.success is True


def test_cap_mode_refuses_to_exceed_budget(tmp_path, monkeypatch):
    project = _project(tmp_path)
    monkeypatch.setenv("OPENMONTAGE_BUDGET_MODE", "cap")
    monkeypatch.setenv("OPENMONTAGE_BUDGET_TOTAL_USD", "1.00")
    monkeypatch.setenv("OPENMONTAGE_APPROVE_TOOLS", "*")
    # Isolate the budget ceiling from the single-action approval threshold,
    # which would otherwise fire first on the large call.
    monkeypatch.setenv("OPENMONTAGE_SINGLE_ACTION_USD", "999")

    tool = FakePaidTool()
    # Well inside the budget: allowed, and recorded.
    assert tool.execute({"project_dir": str(project), "cost": 0.20}).success

    # Over the remaining usable budget (1.00 total, 10% holdback): refused.
    with pytest.raises(BudgetExceededError):
        tool.execute({"project_dir": str(project), "cost": 5.00})


def test_first_paid_use_requires_approval(tmp_path, monkeypatch):
    """AGENT_GUIDE.md asks the agent to announce cost before every first paid
    call. Nothing enforced it; now the gate does."""
    project = _project(tmp_path)
    monkeypatch.setenv("OPENMONTAGE_BUDGET_MODE", "warn")
    monkeypatch.setenv("OPENMONTAGE_BUDGET_TOTAL_USD", "100.0")

    with pytest.raises(ApprovalRequiredError):
        FakePaidTool().execute({"project_dir": str(project), "cost": 0.20})


def test_spend_is_recorded_and_reconciled(tmp_path, monkeypatch):
    project = _project(tmp_path)
    monkeypatch.setenv("OPENMONTAGE_BUDGET_MODE", "observe")
    monkeypatch.setenv("OPENMONTAGE_BUDGET_TOTAL_USD", "10.0")
    monkeypatch.setenv("OPENMONTAGE_APPROVE_TOOLS", "*")

    tool = FakePaidTool()
    tool.execute({"project_dir": str(project), "cost": 0.30})
    tool.execute({"project_dir": str(project), "cost": 0.15})

    log = project / "cost_log.json"
    assert log.is_file(), "cost_log.json was never written"
    entries = json.loads(log.read_text())
    entries = entries["entries"] if isinstance(entries, dict) else entries
    completed = [e for e in entries if e["status"] == "completed"]
    assert len(completed) == 2
    assert round(sum(e["actual_usd"] for e in completed), 2) == 0.45


def test_failed_call_is_refunded_not_charged(tmp_path, monkeypatch):
    project = _project(tmp_path)
    monkeypatch.setenv("OPENMONTAGE_BUDGET_MODE", "observe")

    class Exploding(FakePaidTool):
        name = "exploding_paid_tool"

        def execute(self, inputs: dict) -> ToolResult:
            raise RuntimeError("provider 500")

    with pytest.raises(RuntimeError):
        Exploding().execute({"project_dir": str(project), "cost": 2.0})

    tracker = budget.tracker_for(project)
    assert tracker is not None
    assert tracker.budget_spent_usd == 0.0
    assert tracker.budget_reserved_usd == 0.0


def test_checkpoint_backfills_cost_snapshot(tmp_path, monkeypatch):
    """Backlot's cost meter reads checkpoint['cost_snapshot']; nothing wrote it."""
    pipeline_dir = tmp_path / "projects"
    project = _project(tmp_path)
    monkeypatch.setenv("OPENMONTAGE_BUDGET_MODE", "observe")

    FakePaidTool().execute({"project_dir": str(project), "cost": 0.40})

    path = write_checkpoint(
        pipeline_dir, "proj", "research", "in_progress", artifacts={},
        pipeline_type="animated-explainer", style_playbook="clean-professional",
    )
    checkpoint = json.loads(path.read_text())
    snapshot = checkpoint.get("cost_snapshot")
    assert snapshot is not None, "cost_snapshot was not backfilled"
    assert snapshot["total_spent_usd"] == pytest.approx(0.40)


def test_kill_switch_disables_the_gate(tmp_path, monkeypatch):
    project = _project(tmp_path)
    monkeypatch.setenv("OPENMONTAGE_BUDGET_DISABLED", "1")
    monkeypatch.setenv("OPENMONTAGE_BUDGET_MODE", "cap")
    monkeypatch.setenv("OPENMONTAGE_BUDGET_TOTAL_USD", "0.0")
    assert FakePaidTool().execute({"project_dir": str(project), "cost": 9.0}).success
