"""Budget hard-cap enforcement tests.

These cover the daily bucket model, cross-process locking, the max_cost_usd
boundedness contract, and the fail-closed paths. The load-bearing ones are the
tests that prove a blocked call never reached the provider, and that two
separate PROCESSES cannot jointly exceed the daily cap -- an in-process lock
passes the thread test while leaving the real (python -c per tool) process
model unprotected.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib.config_model import BudgetMode
from tools.base_tool import BaseTool, BudgetGateError, ToolResult, ToolRuntime
from tools.cost_tracker import (
    ApprovalRequiredError,
    BudgetExceededError,
    BudgetPeriodError,
    CostLogCorruptError,
    CostTracker,
)


def make_tracker(log_path, **kw):
    """Tracker with both independent safeguards off, so tests isolate `mode`."""
    defaults = dict(
        budget_total_usd=10.0,
        reserve_pct=0.0,
        single_action_approval_usd=None,
        require_approval_for_new_paid_tool=False,
        mode=BudgetMode.CAP,
        cost_log_path=log_path,
    )
    defaults.update(kw)
    return CostTracker(**defaults)


def spend(tracker, amount, tool="paid_tool"):
    eid = tracker.estimate(tool, "op", amount)
    tracker.reserve(eid)
    tracker.reconcile(eid, amount, success=True)
    return eid


# ===================== Daily bucket: allow / block =====================

class TestDailyCap:
    def test_below_cap_allowed(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        eid = t.estimate("paid_tool", "op", 4.0)
        t.reserve(eid)
        assert t.entries[-1]["status"] == "reserved"

    def test_exact_cap_allowed(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        spend(t, 7.0)
        eid = t.estimate("paid_tool", "op", 3.0)  # exactly hits $10.00
        t.reserve(eid)
        assert t.entries[-1]["status"] == "reserved"
        assert t.remaining_on(t.current_budget_date()) == pytest.approx(0.0)

    def test_over_cap_blocked(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        spend(t, 9.5)
        eid = t.estimate("paid_tool", "op", 0.75)
        with pytest.raises(BudgetExceededError) as exc:
            t.reserve(eid)
        assert t.entries[-1]["status"] == "estimated"  # rejected: consumed nothing

        msg = str(exc.value)
        for expected in ["10.00", "9.50", "0.75", "0.50"]:
            assert expected in msg, f"refusal must state {expected}: {msg}"

    def test_reservations_consume_budget_before_reconcile(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        t.reserve(t.estimate("paid_tool", "op", 6.0))  # in flight, unresolved
        eid = t.estimate("paid_tool", "op", 5.0)
        with pytest.raises(BudgetExceededError):
            t.reserve(eid)


# ===================== Daily bucket: day isolation =====================

class FakeClock:
    def __init__(self, moment: datetime):
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


class TestDayIsolation:
    def test_yesterday_spend_does_not_consume_today(self, tmp_path):
        log = tmp_path / "cost_log.json"
        clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc))
        t = make_tracker(log, clock=clock)
        spend(t, 10.0)  # exhaust 07-16
        assert t.remaining_on("2026-07-16") == pytest.approx(0.0)

        clock.moment = datetime(2026, 7, 17, 9, 0, tzinfo=timezone.utc)
        assert t.remaining_on("2026-07-17") == pytest.approx(10.0)
        t.reserve(t.estimate("paid_tool", "op", 10.0))  # fresh bucket
        assert t.entries[-1]["budget_date"] == "2026-07-17"

    def test_today_spend_does_not_alter_yesterday(self, tmp_path):
        log = tmp_path / "cost_log.json"
        clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc))
        t = make_tracker(log, clock=clock)
        spend(t, 4.0)
        clock.moment = datetime(2026, 7, 17, 9, 0, tzinfo=timezone.utc)
        spend(t, 6.0)
        assert t.spent_on("2026-07-16") == pytest.approx(4.0)
        assert t.spent_on("2026-07-17") == pytest.approx(6.0)

    def test_history_is_preserved_not_cleared(self, tmp_path):
        log = tmp_path / "cost_log.json"
        clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc))
        t = make_tracker(log, clock=clock)
        spend(t, 10.0)
        clock.moment = datetime(2026, 7, 17, 9, 0, tzinfo=timezone.utc)
        spend(t, 1.0)
        dates = {e["budget_date"] for e in t.entries}
        assert dates == {"2026-07-16", "2026-07-17"}
        assert t.spent_on("2026-07-16") == pytest.approx(10.0)


# ===================== Midnight =====================

class TestMidnight:
    def test_reservation_keeps_original_date_across_midnight(self, tmp_path):
        log = tmp_path / "cost_log.json"
        clock = FakeClock(datetime(2026, 7, 16, 23, 59, 30, tzinfo=timezone.utc))
        t = make_tracker(log, clock=clock)
        eid = t.estimate("paid_tool", "op", 6.0)
        t.reserve(eid)

        clock.moment = datetime(2026, 7, 17, 0, 0, 30, tzinfo=timezone.utc)

        entry = next(e for e in t.entries if e["id"] == eid)
        assert entry["budget_date"] == "2026-07-16"      # immutable
        assert entry["status"] == "reserved"             # did not vanish
        assert t.reserved_on("2026-07-16") == pytest.approx(6.0)
        assert t.reserved_on("2026-07-17") == pytest.approx(0.0)
        assert t.remaining_on("2026-07-17") == pytest.approx(10.0)

    def test_reconcile_after_midnight_updates_original_bucket(self, tmp_path):
        log = tmp_path / "cost_log.json"
        clock = FakeClock(datetime(2026, 7, 16, 23, 59, 30, tzinfo=timezone.utc))
        t = make_tracker(log, clock=clock)
        eid = t.estimate("paid_tool", "op", 6.0)
        t.reserve(eid)

        clock.moment = datetime(2026, 7, 17, 0, 5, 0, tzinfo=timezone.utc)
        t.reconcile(eid, 6.0, success=True)

        assert t.spent_on("2026-07-16") == pytest.approx(6.0)  # original day
        assert t.spent_on("2026-07-17") == pytest.approx(0.0)  # not today

    def test_unresolved_reservation_survives_restart_in_original_date(self, tmp_path):
        log = tmp_path / "cost_log.json"
        clock = FakeClock(datetime(2026, 7, 16, 23, 59, 30, tzinfo=timezone.utc))
        t1 = make_tracker(log, clock=clock)
        t1.reserve(t1.estimate("paid_tool", "op", 6.0))  # never reconciled

        after = FakeClock(datetime(2026, 7, 17, 0, 10, 0, tzinfo=timezone.utc))
        t2 = make_tracker(log, clock=after)
        assert t2.reserved_on("2026-07-16") == pytest.approx(6.0)
        assert t2.remaining_on("2026-07-17") == pytest.approx(10.0)


# ===================== Restart / persistence =====================

class TestPersistence:
    def test_spend_survives_restart(self, tmp_path):
        log = tmp_path / "cost_log.json"
        clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc))
        spend(make_tracker(log, clock=clock), 9.5)

        t2 = make_tracker(log, clock=clock)
        assert t2.spent_on("2026-07-16") == pytest.approx(9.5)
        with pytest.raises(BudgetExceededError):
            t2.reserve(t2.estimate("paid_tool", "op", 1.0))

    def test_corrupt_ledger_fails_closed(self, tmp_path):
        log = tmp_path / "cost_log.json"
        spend(make_tracker(log), 1.0)
        log.write_text('{"version": "2.0", "entries": [{"id": "x"')  # truncated

        with pytest.raises(CostLogCorruptError):
            make_tracker(log)

    def test_stale_log_cannot_raise_cap_or_downgrade_mode(self, tmp_path):
        log = tmp_path / "cost_log.json"
        spend(make_tracker(log), 1.0)
        data = json.loads(log.read_text())
        data["budget_total_usd"] = 999.0   # attacker/stale value
        data["budget_mode"] = "observe"
        log.write_text(json.dumps(data))

        t = make_tracker(log)  # config says $10 / cap
        assert t.budget_total_usd == 10.0
        assert t.mode == BudgetMode.CAP
        with pytest.raises(BudgetExceededError):
            t.reserve(t.estimate("paid_tool", "op", 50.0))

    def test_atomic_write_leaves_no_partial_file(self, tmp_path):
        log = tmp_path / "cost_log.json"
        t = make_tracker(log)
        for _ in range(5):
            spend(t, 0.1)
            json.loads(log.read_text())  # always complete, never truncated
        assert not list(tmp_path.glob("*.tmp"))

    def test_unsupported_period_fails_closed(self, tmp_path):
        with pytest.raises(BudgetPeriodError):
            make_tracker(tmp_path / "cost_log.json", period="monthly")

    def test_unresolvable_timezone_fails_closed(self, tmp_path):
        with pytest.raises(BudgetPeriodError):
            make_tracker(tmp_path / "cost_log.json", tz_name="Not/AZone")


# ===================== Overrun =====================

class TestOverrun:
    def test_actual_over_reservation_records_full_actual(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        eid = t.estimate("paid_tool", "op", 2.0)
        t.reserve(eid)
        t.reconcile(eid, 5.0, success=True)  # provider billed more than bounded

        entry = next(e for e in t.entries if e["id"] == eid)
        assert entry["actual_usd"] == 5.0            # full, never truncated
        assert entry["actual_exceeded_reservation"] is True
        assert t.spent_on(t.current_budget_date()) == pytest.approx(5.0)

    def test_overrun_blocks_further_calls_that_date(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        eid = t.estimate("paid_tool", "op", 2.0)
        t.reserve(eid)
        t.reconcile(eid, 5.0, success=True)

        today = t.current_budget_date()
        assert t.is_overrun(today)
        with pytest.raises(BudgetExceededError, match="OVER BUDGET"):
            t.reserve(t.estimate("paid_tool", "op", 0.01))  # would otherwise fit

    def test_overrun_is_sticky_across_restart(self, tmp_path):
        log = tmp_path / "cost_log.json"
        t = make_tracker(log)
        eid = t.estimate("paid_tool", "op", 2.0)
        t.reserve(eid)
        t.reconcile(eid, 5.0, success=True)
        today = t.current_budget_date()

        assert make_tracker(log).is_overrun(today)

    def test_overrun_does_not_block_the_next_day(self, tmp_path):
        log = tmp_path / "cost_log.json"
        clock = FakeClock(datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc))
        t = make_tracker(log, clock=clock)
        eid = t.estimate("paid_tool", "op", 2.0)
        t.reserve(eid)
        t.reconcile(eid, 5.0, success=True)
        assert t.is_overrun("2026-07-16")

        clock.moment = datetime(2026, 7, 17, 9, 0, tzinfo=timezone.utc)
        assert not t.is_overrun("2026-07-17")
        t.reserve(t.estimate("paid_tool", "op", 1.0))  # new day is open


# ===================== Failure / retry accounting =====================

class TestFailureAccounting:
    def test_failed_call_still_consumes_budget(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        eid = t.estimate("paid_tool", "op", 4.0)
        t.reserve(eid)
        t.reconcile(eid, 4.0, success=False)  # provider billed, then errored

        assert t.spent_on(t.current_budget_date()) == pytest.approx(4.0)
        assert t.entries[-1]["status"] == "failed"

    def test_retries_accumulate_and_cannot_bypass_cap(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        for _ in range(2):
            eid = t.estimate("paid_tool", "op", 4.0)
            t.reserve(eid)
            t.reconcile(eid, 4.0, success=False)

        assert t.spent_on(t.current_budget_date()) == pytest.approx(8.0)
        with pytest.raises(BudgetExceededError):  # third retry refused
            t.reserve(t.estimate("paid_tool", "op", 4.0))

    def test_spend_never_recorded_below_zero(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        eid = t.estimate("paid_tool", "op", 1.0)
        t.reserve(eid)
        t.reconcile(eid, -50.0, success=True)  # provider returns nonsense
        assert t.entries[-1]["actual_usd"] == 0.0
        assert t.spent_on(t.current_budget_date()) >= 0.0

    def test_refund_releases_only_undispatched_calls(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        eid = t.estimate("paid_tool", "op", 6.0)
        t.reserve(eid)
        t.refund(eid)
        assert t.remaining_on(t.current_budget_date()) == pytest.approx(10.0)


# ===================== Independent safeguards =====================

class TestIndependentSafeguards:
    def test_cap_does_not_raise_on_first_paid_tool_use(self, tmp_path):
        """The old coupling: cap inherited warn's approval raise. It must not."""
        t = make_tracker(
            tmp_path / "cost_log.json",
            mode=BudgetMode.CAP,
            require_approval_for_new_paid_tool=False,
        )
        t.reserve(t.estimate("never_approved", "op", 1.0))  # no ApprovalRequiredError
        assert t.entries[-1]["status"] == "reserved"

    def test_single_action_threshold_fires_in_every_mode(self, tmp_path):
        for mode in (BudgetMode.OBSERVE, BudgetMode.WARN, BudgetMode.CAP):
            t = make_tracker(
                tmp_path / f"log_{mode.value}.json",
                mode=mode,
                single_action_approval_usd=0.50,
            )
            with pytest.raises(ApprovalRequiredError, match="independent of budget mode"):
                t.reserve(t.estimate("paid_tool", "op", 0.75))

    def test_single_action_threshold_disabled_by_none(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json", single_action_approval_usd=None)
        t.reserve(t.estimate("paid_tool", "op", 9.0))
        assert t.entries[-1]["status"] == "reserved"

    def test_new_paid_tool_approval_fires_in_every_mode(self, tmp_path):
        for mode in (BudgetMode.OBSERVE, BudgetMode.WARN, BudgetMode.CAP):
            t = make_tracker(
                tmp_path / f"log_{mode.value}.json",
                mode=mode,
                require_approval_for_new_paid_tool=True,
            )
            with pytest.raises(ApprovalRequiredError, match="First paid use"):
                t.reserve(t.estimate("paid_tool", "op", 1.0))

    def test_warn_flags_but_proceeds_where_cap_blocks(self, tmp_path):
        warn = make_tracker(
            tmp_path / "warn.json", mode=BudgetMode.WARN, reserve_pct=0.0
        )
        spend(warn, 9.0)
        warn.reserve(warn.estimate("paid_tool", "op", 5.0))
        assert warn.entries[-1]["status"] == "reserved"
        assert warn.entries[-1]["budget_warning"] is True

        cap = make_tracker(tmp_path / "cap.json", mode=BudgetMode.CAP)
        spend(cap, 9.0)
        with pytest.raises(BudgetExceededError):
            cap.reserve(cap.estimate("paid_tool", "op", 5.0))

    def test_observe_records_but_never_blocks(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json", mode=BudgetMode.OBSERVE)
        spend(t, 9.0)
        t.reserve(t.estimate("paid_tool", "op", 50.0))
        assert t.entries[-1]["status"] == "reserved"


# ===================== Concurrency: threads =====================

class TestThreadConcurrency:
    def test_threads_cannot_jointly_exceed_daily_cap(self, tmp_path):
        t = make_tracker(tmp_path / "cost_log.json")
        accepted, errors = [], []

        def attempt():
            try:
                eid = t.estimate("paid_tool", "op", 4.0)
                t.reserve(eid)
                accepted.append(eid)
            except BudgetExceededError:
                errors.append(1)

        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(accepted) == 2, "only 2 x $4 fit in $10 alongside no other spend"
        assert len(errors) == 6
        assert t.reserved_on(t.current_budget_date()) <= 10.0 + 1e-6


# ===================== Concurrency: processes =====================

_CHILD = textwrap.dedent(
    """
    import sys, json
    sys.path.insert(0, {root!r})
    from pathlib import Path
    from lib.config_model import BudgetMode
    from tools.cost_tracker import CostTracker, BudgetExceededError

    t = CostTracker(
        budget_total_usd=10.0, reserve_pct=0.0,
        single_action_approval_usd=None,
        require_approval_for_new_paid_tool=False,
        mode=BudgetMode.CAP, cost_log_path=Path({log!r}),
    )
    try:
        eid = t.estimate("paid_tool", "op", 4.0)
        t.reserve(eid)
        print("ACCEPTED")
    except BudgetExceededError:
        print("BLOCKED")
    """
)


class TestProcessConcurrency:
    """The tests that justify the OS file lock.

    OpenMontage invokes tools as separate `python -c` processes, so a
    threading.Lock protects nothing here. These fail against an in-process
    lock and pass with the ledger lock.
    """

    def test_separate_processes_cannot_reserve_same_remaining_budget(self, tmp_path):
        log = tmp_path / "cost_log.json"
        code = _CHILD.format(root=str(ROOT), log=str(log))

        procs = [
            subprocess.Popen(
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for _ in range(6)
        ]
        outs = [p.communicate() for p in procs]

        for out, err in outs:
            assert "Traceback" not in err, err
        accepted = sum("ACCEPTED" in out for out, _ in outs)
        blocked = sum("BLOCKED" in out for out, _ in outs)

        assert accepted + blocked == 6
        assert accepted == 2, f"only 2 x $4 fit in $10; {accepted} were accepted"

    def test_combined_process_reservations_never_exceed_cap(self, tmp_path):
        log = tmp_path / "cost_log.json"
        code = _CHILD.format(root=str(ROOT), log=str(log))
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for _ in range(6)
        ]
        for p in procs:
            p.communicate()

        t = CostTracker(
            budget_total_usd=10.0, reserve_pct=0.0,
            single_action_approval_usd=None,
            require_approval_for_new_paid_tool=False,
            mode=BudgetMode.CAP, cost_log_path=log,
        )
        assert t.reserved_on(t.current_budget_date()) <= 10.0 + 1e-6

    def test_crashed_process_does_not_permanently_block_ledger(self, tmp_path):
        """OS locks die with the process; a crash must not wedge the ledger."""
        log = tmp_path / "cost_log.json"
        crash = textwrap.dedent(
            f"""
            import sys, os
            sys.path.insert(0, {str(ROOT)!r})
            from pathlib import Path
            from lib.ledger_lock import ledger_lock
            with ledger_lock(Path({str(log)!r})):
                os._exit(1)   # hard kill while holding the lock
            """
        )
        proc = subprocess.run([sys.executable, "-c", crash], capture_output=True)
        assert proc.returncode == 1

        t = make_tracker(log)  # must not hang or raise
        t.reserve(t.estimate("paid_tool", "op", 1.0))
        assert t.entries[-1]["status"] == "reserved"


# ===================== The gate: boundedness + free paths =====================

class _Recorder:
    def __init__(self):
        self.called = False


class UnboundedPaidTool(BaseTool):
    """A paid tool that cannot bound its cost -- i.e. every tool in the repo today."""
    name = "unbounded_paid"
    runtime = ToolRuntime.API

    def __init__(self, recorder):
        self.recorder = recorder

    def estimate_cost(self, inputs):
        return 1.0

    def execute(self, inputs):
        self.recorder.called = True  # would be the provider call
        return ToolResult(success=True, cost_usd=1.0)


class BoundedPaidTool(UnboundedPaidTool):
    name = "bounded_paid"

    def max_cost_usd(self, inputs):
        return 2.0


class FreeLocalTool(BaseTool):
    name = "free_local"
    runtime = ToolRuntime.LOCAL

    def __init__(self, recorder):
        self.recorder = recorder

    def execute(self, inputs):
        self.recorder.called = True
        return ToolResult(success=True, cost_usd=0.0)


class ZeroCostApiTool(UnboundedPaidTool):
    name = "zero_cost_api"

    def estimate_cost(self, inputs):
        return 0.0


class BadBoundTool(UnboundedPaidTool):
    name = "bad_bound"

    def max_cost_usd(self, inputs):
        return 0.5  # below its own estimate of 1.0 -- not a bound


@pytest.fixture
def gate_env(tmp_path, monkeypatch):
    """Point the gate at an isolated config + ledger."""
    import lib.budget_gate as gate

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "budget:\n"
        "  mode: cap\n"
        "  total_usd: 10.00\n"
        "  period: daily\n"
        "  timezone: system_local\n"
        "  reserve_pct: 0.0\n"
        "  single_action_approval_usd: null\n"
        "  require_approval_for_new_paid_tool: false\n"
    )
    monkeypatch.setenv("OPENMONTAGE_CONFIG", str(cfg))
    monkeypatch.setenv("OPENMONTAGE_COST_LOG", str(tmp_path / "cost_log.json"))
    gate.reset()
    yield tmp_path
    gate.reset()


class TestGateBoundedness:
    def test_unbounded_paid_tool_fails_closed_and_names_the_tool(self, gate_env):
        rec = _Recorder()
        with pytest.raises(BudgetGateError, match="unbounded_paid"):
            UnboundedPaidTool(rec).execute({})
        assert rec.called is False, "provider must not be reached"

    def test_bound_below_estimate_fails_closed(self, gate_env):
        rec = _Recorder()
        with pytest.raises(BudgetGateError, match="not an upper bound"):
            BadBoundTool(rec).execute({})
        assert rec.called is False

    def test_bounded_paid_tool_proceeds_and_is_recorded(self, gate_env):
        rec = _Recorder()
        result = BoundedPaidTool(rec).execute({})
        assert result.success and rec.called

        log = json.loads((gate_env / "cost_log.json").read_text())
        assert log["entries"][-1]["tool"] == "bounded_paid"
        assert log["entries"][-1]["reserved_usd"] == 0.0     # settled
        assert log["entries"][-1]["actual_usd"] == 1.0       # actual, not the bound
        assert log["entries"][-1]["budget_date"]

    def test_gate_blocks_before_provider_when_cap_reached(self, gate_env):
        import lib.budget_gate as gate

        t = gate.get_tracker()
        spend(t, 9.5, tool="prior")
        gate.reset()

        rec = _Recorder()
        with pytest.raises(BudgetExceededError):
            BoundedPaidTool(rec).execute({})  # bound $2.00 > $0.50 remaining
        assert rec.called is False, "blocked call must never reach the provider"


class TestGateFreePaths:
    def test_local_tool_untouched_and_writes_no_ledger(self, gate_env):
        rec = _Recorder()
        assert FreeLocalTool(rec).execute({}).success
        assert rec.called
        assert not (gate_env / "cost_log.json").exists()

    def test_zero_cost_api_tool_allowed(self, gate_env):
        rec = _Recorder()
        assert ZeroCostApiTool(rec).execute({}).success
        assert rec.called
        assert not (gate_env / "cost_log.json").exists()
