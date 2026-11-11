"""Spend must be recorded without relying on the agent to type it.

Before the 2026-11-11 audit no project had a `cost_log.json`: the estimate →
reserve → reconcile lifecycle depended on agent discipline, checkpoint cost
snapshots were hand-typed, the manifest's `budget_default_usd` and the config's
`budget.total_usd` disagreed and neither was applied, and rented GPU time had
nowhere to go (a run that cost $0.208 showed $0).
"""

import json

import jsonschema
import pytest

from backlot.state import load_board_state
from lib import events
from lib.checkpoint import init_project, write_checkpoint
from lib.config_model import BudgetMode, OpenMontageConfig
from schemas.artifacts import load_schema
from tools import base_tool
from tools import cost_tracker as cost_tracker_mod
from tools.base_tool import BaseTool, ToolResult
from tools.cost_tracker import (
    CostTracker,
    main as cost_cli,
    project_cost_snapshot,
    resolve_budget_usd,
)
from tests.contracts.test_phase0_contracts import sample_artifact


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    monkeypatch.setattr(events, "PROJECTS_DIR", root)
    init_project("film", title="Film", pipeline_type="cinematic", pipeline_dir=root)
    return root / "film"


class PaidClip(BaseTool):
    name = "paid_clip"

    def estimate_cost(self, inputs):
        return float(inputs.get("price", 0.25))

    def execute(self, inputs):
        return ToolResult(success=True, cost_usd=float(inputs.get("price", 0.25)))


class Selector(BaseTool):
    name = "clip_selector"

    def execute(self, inputs):
        return PaidClip().execute(inputs)  # nested call: depth 1


class FreeLocal(BaseTool):
    name = "free_local"

    def execute(self, inputs):
        return ToolResult(success=True, cost_usd=0.0)


def _run(tool, project, **inputs):
    return tool.execute({"project_dir": str(project), **inputs})


def _ledger(project):
    return json.loads((project / "cost_log.json").read_text())


# ---- one budget -------------------------------------------------------------


def test_budget_precedence_is_approved_then_pipeline_default_then_config():
    config = OpenMontageConfig()  # ceiling 10.00
    assert resolve_budget_usd("cinematic", config=config) == (
        2.0, "pipeline_defs/cinematic.yaml orchestration.budget_default_usd")
    assert resolve_budget_usd(None, config=config) == (10.0, "config.yaml budget.total_usd")
    assert resolve_budget_usd("framework-smoke", config=config)[0] == 10.0  # no default
    assert resolve_budget_usd("cinematic", approved_usd=0.64, config=config) == (0.64, "approved")
    # the user approved more than the ceiling: their explicit number stands
    assert resolve_budget_usd("cinematic", approved_usd=25.0, config=config)[0] == 25.0


def test_config_ceiling_caps_a_pipeline_default():
    config = OpenMontageConfig.model_validate({"budget": {"total_usd": 1.0}})
    budget, source = resolve_budget_usd("cinematic", config=config)
    assert budget == 1.0 and "caps cinematic default $2.00" in source


def test_project_tracker_takes_the_pipeline_default_from_the_marker(project):
    tracker = CostTracker.for_project(project)
    assert tracker.budget_total_usd == 2.0
    tracker.record_spend("x", "seed the log", 0.0)
    assert _ledger(project)["metadata"]["budget_source"].startswith("pipeline_defs/cinematic.yaml")

    CostTracker.for_project(project).set_budget(0.64)
    again = CostTracker.for_project(project)
    assert again.budget_total_usd == 0.64 and again.budget_source == "approved"


# ---- automatic recording ----------------------------------------------------


def test_tool_costs_reach_the_ledger_without_the_agent(project):
    _run(PaidClip(), project, price=0.25)
    _run(FreeLocal(), project)
    _run(PaidClip(), project, price=0.10)

    tracker = CostTracker.for_project(project)
    assert tracker.sync_tool_events() == 2          # free calls are not ledger noise
    assert tracker.budget_spent_usd == pytest.approx(0.35)
    assert {e["source"] for e in tracker.entries} == {"tool_event"}

    # idempotent
    assert CostTracker.for_project(project).sync_tool_events() == 0
    assert CostTracker.for_project(project).budget_spent_usd == pytest.approx(0.35)
    jsonschema.validate(_ledger(project), load_schema("cost_log"))


def test_a_selector_and_its_provider_are_counted_once(project):
    _run(Selector(), project, price=0.40)
    tracker = CostTracker.for_project(project)
    tracker.sync_tool_events()
    assert tracker.budget_spent_usd == pytest.approx(0.40)
    assert [e["tool"] for e in tracker.entries] == ["clip_selector"]


def test_a_call_that_was_also_reconciled_by_hand_is_not_double_counted(project):
    tracker = CostTracker.for_project(project)
    entry = tracker.estimate("paid_clip", "scene 1", 0.25)
    tracker.reserve(entry, approved=True)
    _run(PaidClip(), project, price=0.25)
    tracker.reconcile(entry, 0.25)

    assert tracker.sync_tool_events() == 0
    assert tracker.budget_spent_usd == pytest.approx(0.25)
    assert tracker.entries[0]["call_id"]            # the event was matched to it


def test_checkpoint_carries_the_recorded_spend_by_itself(project):
    root = project.parent
    _run(PaidClip(), project, price=0.25)
    path = write_checkpoint(root, "film", "research", "completed",
                            {"research_brief": sample_artifact("research_brief")})
    snapshot = json.loads(path.read_text())["cost_snapshot"]
    assert snapshot == {
        "total_spent_usd": 0.25, "total_reserved_usd": 0.0, "budget_remaining_usd": 1.75,
    }
    assert load_board_state(project)["cost"] == snapshot


def test_explicit_snapshot_still_wins(project):
    root = project.parent
    _run(PaidClip(), project, price=0.25)
    path = write_checkpoint(root, "film", "research", "in_progress", {},
                            cost_snapshot={"total_spent_usd": 9.99})
    assert json.loads(path.read_text())["cost_snapshot"] == {"total_spent_usd": 9.99}


def test_a_free_run_writes_no_snapshot_so_the_manifest_total_still_shows(project):
    """The board falls back to asset_manifest.total_cost_usd when no snapshot
    exists; an automatic 0.0 would hide it."""
    root = project.parent
    _run(FreeLocal(), project)
    path = write_checkpoint(root, "film", "research", "in_progress", {})
    assert "cost_snapshot" not in json.loads(path.read_text())
    assert project_cost_snapshot(project) is None
    assert not (project / "cost_log.json").exists()

    (project / "artifacts" / "asset_manifest.json").write_text(
        json.dumps({"version": "1.0", "assets": [], "total_cost_usd": 0.3}))
    assert load_board_state(project)["cost"] == {"total_spent_usd": 0.3}


def test_board_reads_the_ledger_when_no_checkpoint_has_a_snapshot(project):
    CostTracker.for_project(project).record_spend("stock_license", "one clip", 1.5)
    cost = load_board_state(project)["cost"]
    assert cost["total_spent_usd"] == 1.5 and cost["budget_remaining_usd"] == 0.5


def test_a_broken_ledger_never_blocks_a_checkpoint(project, caplog):
    root = project.parent
    (project / "cost_log.json").write_text("{ torn", encoding="utf-8")
    path = write_checkpoint(root, "film", "research", "in_progress", {})
    assert path.exists() and "cost_snapshot" not in json.loads(path.read_text())
    assert "Cost snapshot could not be derived" in caplog.text


# ---- spend no tool reports --------------------------------------------------


def test_rented_gpu_time_is_recorded(project):
    tracker = CostTracker.for_project(project)
    tracker.record_rental("vastai_gpu", hours=0.52, usd_per_hour=0.40, details="assets stage")
    assert tracker.budget_spent_usd == pytest.approx(0.208)
    entry = _ledger(project)["entries"][0]
    assert entry["source"] == "rental" and entry["status"] == "completed"
    assert entry["details"] == "assets stage"
    jsonschema.validate(_ledger(project), load_schema("cost_log"))
    with pytest.raises(ValueError):
        tracker.record_spend("x", "y", -1)


def test_command_line_records_and_shows(project, capsys):
    assert cost_cli(["record", str(project), "--tool", "vastai_gpu",
                     "--hours", "0.52", "--rate", "0.40"]) == 0
    assert cost_cli(["budget", str(project), "--usd", "0.46"]) == 0
    capsys.readouterr()
    assert cost_cli(["show", str(project)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["total_spent_usd"] == 0.208
    assert shown["budget_total_usd"] == 0.46 and shown["budget_source"] == "approved"
    assert shown["budget_remaining_usd"] == pytest.approx(0.252)
    assert shown["spent_by_tool"] == {"vastai_gpu": 0.208}
    with pytest.raises(SystemExit):
        cost_cli(["record", str(project), "--tool", "x"])     # neither --usd nor --hours/--rate
    with pytest.raises(SystemExit):
        cost_cli(["show", "no-such-project-anywhere"])


# ---- cap mode is a hard stop in the tool layer ------------------------------


@pytest.fixture
def budget_mode(monkeypatch):
    def set_mode(mode):
        config = OpenMontageConfig()
        config.budget.mode = mode
        monkeypatch.setattr(OpenMontageConfig, "load", classmethod(lambda cls, path=None: config))
    return set_mode


def test_cap_mode_refuses_a_call_that_does_not_fit(project, budget_mode):
    budget_mode(BudgetMode.CAP)
    CostTracker.for_project(project).set_budget(0.30)

    first = _run(PaidClip(), project, price=0.25)
    assert first.success is True

    second = _run(PaidClip(), project, price=0.25)   # 0.05 left
    assert second.success is False
    assert "BUDGET CAP" in second.error and "$0.05" in second.error
    # refused before the provider: no cost, and the refusal is in the event log
    assert CostTracker.for_project(project).budget_spent_usd == pytest.approx(0.25)
    last = events.read_events(project)[-1]
    assert last["event"] == "error" and "BUDGET CAP" in last["error"]

    assert _run(PaidClip(), project, price=0.05).success is True   # exactly fits
    assert _run(FreeLocal(), project).success is True              # free is never blocked


@pytest.mark.parametrize("mode", [BudgetMode.WARN, BudgetMode.OBSERVE])
def test_other_modes_never_block(project, budget_mode, mode):
    budget_mode(mode)
    CostTracker.for_project(project).set_budget(0.10)
    assert _run(PaidClip(), project, price=0.25).success is True
    tracker = CostTracker.for_project(project)
    tracker.sync_tool_events()
    assert tracker.over_budget is True


def test_cap_check_ignores_dry_runs_and_unattributed_calls(project, budget_mode):
    budget_mode(BudgetMode.CAP)
    CostTracker.for_project(project).set_budget(0.0)
    assert base_tool._budget_cap_block(PaidClip(), {"dry_run": True}, project) is None
    assert PaidClip().execute({"price": 0.25}).success is True     # no project: not governed


def test_a_failure_inside_the_cap_check_lets_the_call_through(project, budget_mode, monkeypatch):
    budget_mode(BudgetMode.CAP)

    def boom(*args, **kwargs):
        raise RuntimeError("ledger unreadable")

    monkeypatch.setattr(cost_tracker_mod.CostTracker, "for_project", classmethod(boom))
    assert _run(PaidClip(), project, price=0.25).success is True
