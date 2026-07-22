"""Budget enforcement gate: the wiring between config.yaml and paid calls.

This module is what makes the hard cap real. Prior to it, `CostTracker` was a
fully-tested library that nothing ever called, and the `budget:` block in
config.yaml was inert -- a paid provider key would have spent without limit.

Design
------
Enforcement rides on BaseTool's execute() wrapper (see tools/base_tool.py), so
every tool -- current and future -- is covered without per-tool changes. A
safety control that must be remembered on each new provider is a checklist,
not a control.

The ledger is a single shared one at `pipeline/cost_log.json` (path from config
`paths.pipeline_dir`; `pipeline/` is gitignored). `budget.total_usd` is the
maximum provider spend PER CALENDAR DAY, across all projects and all
processes -- not per project, and not per process. Day boundaries come from
`budget.timezone`; history is preserved, never cleared to free budget.

What is reserved is the tool's max_cost_usd() upper bound, not its
estimate_cost() approximation -- see tools/base_tool.py:_enforce_budget.

Fail closed
-----------
Every failure path here refuses the paid call: unreadable ledger, unparseable
config, unwritable log. A budget control whose failure mode is "no budget
control" is worse than none, because it looks like protection.

Scope
-----
Whether the gate applies is decided by CLASSIFICATION (`BaseTool.paid`), not
by the size of the estimate:

- LOCAL/LOCAL_GPU tools are free -- they never touch this module -- unless a
  tool explicitly marks itself `paid = True`.
- API/HYBRID tools are treated as PAID unless they explicitly declare
  `paid = False` (the genuinely free stock-media-search tools).
- A paid tool is gated even when its `estimate_cost()` returns zero: a zero
  estimate means "unknown", never "free".
- Every paid request must provide a defensible `max_cost_usd()` bound, or the
  call is refused (fail closed).
- An explicit ZERO bound is honoured only for requests that are guaranteed
  not to dispatch to a paid provider (a selector's rank mode, requests
  execute() refuses locally).

Zero-key and local pipelines therefore behave exactly as before, while a
broken or information-starved estimate can no longer skip the gate.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import NamedTuple, Optional

from lib.config_model import OpenMontageConfig
from tools.cost_tracker import CostTracker, quantize_usd


class BudgetHandle(NamedTuple):
    """An accepted reservation, to be settled exactly once."""
    tracker: CostTracker
    entry_id: str
    estimated_usd: float


# Guards the cached tracker. The tracker itself has its own lock covering the
# check-and-reserve critical section.
_LOCK = threading.Lock()
_TRACKER: Optional[CostTracker] = None
_TRACKER_KEY: Optional[tuple] = None


def _config_path() -> Optional[Path]:
    override = os.environ.get("OPENMONTAGE_CONFIG")
    return Path(override) if override else None


def cost_log_path(cfg: OpenMontageConfig) -> Path:
    """Resolve the cumulative ledger path. OPENMONTAGE_COST_LOG overrides."""
    override = os.environ.get("OPENMONTAGE_COST_LOG")
    if override:
        return Path(override)
    return cfg.resolve_path("pipeline_dir") / "cost_log.json"


def get_tracker() -> CostTracker:
    """Return the process-wide tracker, rebuilt if config changed.

    Shared by every caller so that concurrent reservations contend on one
    ledger and one lock.
    """
    global _TRACKER, _TRACKER_KEY
    with _LOCK:
        cfg = OpenMontageConfig.load(_config_path())
        b = cfg.budget
        path = cost_log_path(cfg)
        key = (
            str(path), b.mode, b.total_usd, b.reserve_pct,
            b.single_action_approval_usd, b.require_approval_for_new_paid_tool,
            b.period, b.timezone,
        )
        if _TRACKER is None or _TRACKER_KEY != key:
            # Config is the sole authority for these -- CostTracker._load()
            # deliberately does not restore mode or total from the log.
            _TRACKER = CostTracker(
                budget_total_usd=b.total_usd,
                reserve_pct=b.reserve_pct,
                single_action_approval_usd=b.single_action_approval_usd,
                require_approval_for_new_paid_tool=b.require_approval_for_new_paid_tool,
                mode=b.mode,
                cost_log_path=path,
                period=b.period,
                tz_name=b.timezone,
            )
            _TRACKER_KEY = key
        return _TRACKER


def reset() -> None:
    """Drop the cached tracker. For tests and after a deliberate config change."""
    global _TRACKER, _TRACKER_KEY
    with _LOCK:
        _TRACKER = None
        _TRACKER_KEY = None


def reserve(tool: str, operation: str, bound_usd: float) -> BudgetHandle:
    """Account for a paid call BEFORE it runs, against its day's bucket.

    `bound_usd` must be the tool's max_cost_usd() upper bound, not its
    estimate: the cap is only guaranteed if the worst case is what we hold.

    Raises BudgetExceededError (day's cap reached, or the day is marked over
    budget), ApprovalRequiredError (a configured safeguard fired),
    CostLogCorruptError (spend unknown), or LedgerLockError (ledger busy).
    In every case the caller must not proceed to the provider.
    """
    tracker = get_tracker()
    entry_id = tracker.estimate(tool, operation, bound_usd)
    try:
        tracker.reserve(entry_id)
    except BaseException:
        # A rejected call never reached the provider, so releasing is correct
        # here -- and it stops a refusal from leaving a dangling ESTIMATED row.
        tracker.refund(entry_id)
        raise
    # Ceiling-quantized so a positive bound settled as "actual unknown" can
    # never charge zero -- it matches exactly what the ledger reserved.
    return BudgetHandle(tracker, entry_id, quantize_usd(bound_usd))


def settle(handle: BudgetHandle, actual_usd: Optional[float], success: bool) -> None:
    """Resolve a reservation after the call finished, failed, or was cancelled.

    Lands in the entry's original budget_date, whatever today is now.

    `actual_usd=None` means the real cost is unknown (the tool raised, or
    reported no cost). We charge the reserved bound rather than releasing: a
    provider that errored may still have billed, and under-counting spend is
    the failure that breaks the cap.
    """
    actual = handle.estimated_usd if actual_usd is None else actual_usd
    handle.tracker.reconcile(handle.entry_id, actual, success=success)
