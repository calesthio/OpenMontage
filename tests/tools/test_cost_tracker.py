"""Regression tests for tools/cost_tracker.py:

- reserve() (and sibling entry-mutating methods) serialize under a lock so
  concurrent tool threads can't jointly overspend past the budget cap.
- estimate_from_reference() falls back to a 5s clip duration when
  clip_duration_seconds is explicitly 0, instead of raising ZeroDivisionError.
- CostTracker.__init__ validates reserve_pct/budget_total_usd/
  single_action_approval_usd, and estimate()/reserve() reject a negative
  estimated_usd.
- BudgetMode.WARN logs a warning when a reservation would have exceeded
  budget, instead of behaving exactly like no cap at all.
"""

import sys
import threading
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.config_model import BudgetMode
from tools.cost_tracker import ApprovalRequiredError, BudgetExceededError, CostTracker


# ---- Thread safety ----


def test_concurrent_reserve_does_not_overspend_cap():
    """Many threads racing reserve() for entries that would jointly exceed
    the budget must not all succeed -- the lock must serialize the
    check-then-commit sequence so CAP mode's guarantee actually holds."""
    budget_total = 10.0
    per_item_cost = 1.0
    tracker = CostTracker(
        budget_total_usd=budget_total,
        reserve_pct=0.01,
        single_action_approval_usd=100.0,
        require_approval_for_new_paid_tool=False,
        mode=BudgetMode.CAP,
    )
    # 20 entries at $1 each = $20 total, double the $10 budget: only some
    # subset can be reserved successfully -- the exact cutoff depends on the
    # reserve_pct holdback, but the invariant under test is that the total
    # committed reservation can never exceed the budget no matter how the
    # threads interleave.
    entry_ids = [tracker.estimate("tool", "op", per_item_cost) for _ in range(20)]

    successes = []
    failures = []
    lock = threading.Lock()

    def worker(entry_id: str) -> None:
        try:
            tracker.reserve(entry_id)
            with lock:
                successes.append(entry_id)
        except BudgetExceededError:
            with lock:
                failures.append(entry_id)

    threads = [threading.Thread(target=worker, args=(eid,)) for eid in entry_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Contention was real (neither all-succeed nor all-fail)...
    assert len(successes) + len(failures) == 20
    assert 0 < len(successes) < 20
    # ...and, crucially, no double-booking: the committed reservation total
    # matches exactly what was recorded and never exceeds the hard budget.
    assert tracker.budget_reserved_usd == len(successes) * per_item_cost
    assert tracker.budget_reserved_usd <= budget_total


# ---- Zero-division guard ----


def _brief(total_scenes=5, word_count=100, duration=60):
    return {
        "structure_analysis": {
            "total_scenes": total_scenes,
            "pacing_profile": {"pacing_style": "steady_educational"},
        },
        "narration_transcript": {"word_count": word_count},
        "source": {"duration_seconds": duration},
    }


def test_explicit_zero_clip_duration_falls_back_to_five_instead_of_raising():
    tracker = CostTracker()
    # Must not raise ZeroDivisionError.
    result = tracker.estimate_from_reference(
        video_analysis_brief=_brief(),
        target_duration_seconds=60,
        tool_plan={
            "video_generation": {
                "tool": "kling_fal",
                "cost_per_unit": 0.30,
                "clip_duration_seconds": 0,
            },
        },
    )
    assert result["estimated_clips"] > 0


def test_absent_clip_duration_still_defaults_to_five():
    """Sanity check the explicit-absent path still behaves as before."""
    tracker = CostTracker()
    result = tracker.estimate_from_reference(
        video_analysis_brief=_brief(),
        target_duration_seconds=60,
        tool_plan={
            "video_generation": {"tool": "kling_fal", "cost_per_unit": 0.30},
        },
    )
    assert result["estimated_clips"] > 0


# ---- Budget config validation ----


@pytest.mark.parametrize("reserve_pct", [-0.1, 1.5, 2.0])
def test_init_rejects_reserve_pct_out_of_range(reserve_pct):
    with pytest.raises(ValueError):
        CostTracker(reserve_pct=reserve_pct)


def test_init_accepts_reserve_pct_boundaries_of_zero_and_one():
    # [0, 1] is inclusive of both ends. 0 is a deliberately-used value
    # elsewhere in the codebase (server/app/runner/stage_runner.py passes
    # reserve_pct=0.0 to neutralize the holdback) so it must stay legal.
    CostTracker(reserve_pct=0.0)
    CostTracker(reserve_pct=1.0)


def test_init_rejects_negative_budget_total():
    with pytest.raises(ValueError):
        CostTracker(budget_total_usd=-5.0)


def test_init_rejects_negative_single_action_approval():
    with pytest.raises(ValueError):
        CostTracker(single_action_approval_usd=-1.0)


def test_estimate_rejects_negative_estimated_usd():
    tracker = CostTracker()
    with pytest.raises(ValueError):
        tracker.estimate("tool", "op", -1.0)


def test_reserve_rejects_entry_with_negative_estimated_usd():
    """Defense in depth: even if a stale/corrupted entry (e.g. loaded from an
    old cost_log.json predating the estimate() guard) carries a negative
    estimated_usd, reserve() must refuse to commit it rather than inflating
    the effective budget."""
    tracker = CostTracker()
    entry_id = tracker.estimate("tool", "op", 0.0)
    entry = tracker._find(entry_id)
    entry["estimated_usd"] = -5.0
    with pytest.raises(ValueError):
        tracker.reserve(entry_id)


# ---- WARN mode ----


def test_warn_mode_logs_warning_on_budget_overage(caplog):
    tracker = CostTracker(
        budget_total_usd=1.0,
        reserve_pct=0.01,
        single_action_approval_usd=100.0,
        require_approval_for_new_paid_tool=False,
        mode=BudgetMode.WARN,
    )
    entry_id = tracker.estimate("expensive_tool", "op", 5.0)
    with caplog.at_level("WARNING"):
        tracker.reserve(entry_id)  # must not raise in WARN mode

    assert any(
        "WARN mode" in record.message or "warn mode" in record.message.lower()
        for record in caplog.records
    )
    # The reservation still goes through -- WARN alerts, it doesn't block.
    entry = tracker._find(entry_id)
    assert entry["status"] == "reserved"


def test_warn_mode_does_not_log_when_within_budget(caplog):
    tracker = CostTracker(
        budget_total_usd=10.0,
        reserve_pct=0.01,
        single_action_approval_usd=100.0,
        require_approval_for_new_paid_tool=False,
        mode=BudgetMode.WARN,
    )
    entry_id = tracker.estimate("cheap_tool", "op", 1.0)
    with caplog.at_level("WARNING"):
        tracker.reserve(entry_id)

    assert not any("WARN mode" in record.message for record in caplog.records)


def test_cap_mode_still_raises_instead_of_only_warning():
    """Make sure the new WARN branch didn't accidentally swallow CAP's raise."""
    tracker = CostTracker(
        budget_total_usd=1.0,
        reserve_pct=0.01,
        single_action_approval_usd=100.0,
        require_approval_for_new_paid_tool=False,
        mode=BudgetMode.CAP,
    )
    entry_id = tracker.estimate("expensive_tool", "op", 5.0)
    with pytest.raises(BudgetExceededError):
        tracker.reserve(entry_id)
