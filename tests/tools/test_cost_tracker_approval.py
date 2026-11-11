"""Budget governance must be usable after the user says yes.

Regression tests for the cost tracker:

- an action above the single-action threshold could never be reserved in
  warn/cap mode, approved or not, so a governed run had to bypass the tracker;
- the persisted log did not validate against ``cost_log.schema.json``;
- a budget passed to the constructor was silently ignored once a log existed;
- the log was written in place and read without an explicit encoding.
"""

import json

import pytest

from lib.config_model import BudgetConfig, BudgetMode, OpenMontageConfig
from schemas.artifacts import validate_artifact
from tools.cost_tracker import ApprovalRequiredError, BudgetExceededError, CostTracker


def test_approved_action_above_the_threshold_can_be_reserved():
    tracker = CostTracker(mode=BudgetMode.WARN, single_action_approval_usd=0.50)
    entry_id = tracker.estimate("kling_video", "clip", 0.90)

    with pytest.raises(ApprovalRequiredError, match="approved=True"):
        tracker.reserve(entry_id)
    tracker.reserve(entry_id, approved=True)

    entry = tracker.entries[0]
    assert entry["status"] == "reserved"
    assert entry["approved"] is True


def test_approving_an_action_approves_the_tool_for_later_paid_calls():
    tracker = CostTracker(mode=BudgetMode.WARN)
    tracker.reserve(tracker.estimate("kling_video", "clip", 0.90), approved=True)

    cheap = tracker.estimate("kling_video", "clip", 0.10)
    tracker.reserve(cheap)

    assert tracker.entries[-1]["status"] == "reserved"


def test_approval_never_lifts_the_cap():
    tracker = CostTracker(budget_total_usd=1.0, mode=BudgetMode.CAP)
    entry_id = tracker.estimate("kling_video", "clip", 5.0)

    with pytest.raises(BudgetExceededError):
        tracker.reserve(entry_id, approved=True)

    assert tracker.entries[0]["status"] == "estimated"


def test_persisted_log_validates_against_its_schema(tmp_path):
    log_path = tmp_path / "cost_log.json"
    tracker = CostTracker(
        budget_total_usd=1.0, reserve_pct=0.0, mode=BudgetMode.WARN,
        cost_log_path=log_path,
    )
    tracker.approve_tool("flux")
    over_budget = tracker.estimate("kling_video", "clip", 2.0)
    tracker.reserve(over_budget, approved=True)  # warn mode: flagged, not blocked
    tracker.reconcile(over_budget, 1.9)

    persisted = json.loads(log_path.read_text(encoding="utf-8"))

    assert persisted["entries"][0]["budget_warning"] is True
    validate_artifact("cost_log", persisted)


def test_set_budget_persists_where_the_constructor_argument_does_not(tmp_path):
    log_path = tmp_path / "cost_log.json"
    CostTracker(budget_total_usd=10.0, cost_log_path=log_path).estimate("t", "op", 0.0)

    # An existing log is authoritative: the constructor only seeds a new one.
    assert CostTracker(budget_total_usd=25.0, cost_log_path=log_path).budget_total_usd == 10.0

    CostTracker(cost_log_path=log_path).set_budget(25.0)

    assert CostTracker(cost_log_path=log_path).budget_total_usd == 25.0


def test_for_project_applies_the_configured_budget_policy(tmp_path):
    config = OpenMontageConfig(
        budget=BudgetConfig(
            mode=BudgetMode.CAP, total_usd=3.0, reserve_pct=0.0,
            single_action_approval_usd=1.5,
            require_approval_for_new_paid_tool=False,
        )
    )

    tracker = CostTracker.for_project(tmp_path / "film", config=config)
    tracker.reserve(tracker.estimate("flux", "image", 1.0))

    assert tracker.mode is BudgetMode.CAP
    assert tracker.budget_total_usd == 3.0
    assert tracker.cost_snapshot()["budget_remaining_usd"] == 2.0
    assert (tmp_path / "film" / "cost_log.json").is_file()


def test_for_project_seeds_the_budget_the_user_approved(tmp_path):
    tracker = CostTracker.for_project(
        tmp_path / "film", budget_total_usd=0.46, config=OpenMontageConfig()
    )

    assert tracker.budget_total_usd == 0.46


def test_non_ascii_operation_round_trips(tmp_path):
    log_path = tmp_path / "cost_log.json"
    CostTracker(cost_log_path=log_path).estimate("comfyui_tts", "บรรยายภาษาไทย", 0.0)

    assert CostTracker(cost_log_path=log_path).entries[0]["operation"] == "บรรยายภาษาไทย"


def test_failed_save_keeps_the_previous_ledger(tmp_path, monkeypatch):
    log_path = tmp_path / "cost_log.json"
    tracker = CostTracker(cost_log_path=log_path)
    tracker.estimate("flux", "image", 0.05)
    original = log_path.read_bytes()

    import tools.cost_tracker as cost_tracker_module

    def failing_dump(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(cost_tracker_module.json, "dump", failing_dump)
    with pytest.raises(OSError):
        tracker.estimate("flux", "image", 0.05)

    assert log_path.read_bytes() == original


def test_corrupt_ledger_is_reported_by_path(tmp_path):
    log_path = tmp_path / "cost_log.json"
    log_path.write_text('{"entries": [', encoding="utf-8")

    with pytest.raises(ValueError, match="cost_log.json"):
        CostTracker(cost_log_path=log_path)
