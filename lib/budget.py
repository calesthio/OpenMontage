"""Per-project budget governance, wired into every tool call.

Why this module exists
----------------------
`tools/cost_tracker.py` implements estimate -> reserve -> reconcile, and
`docs/ARCHITECTURE.md` says it "enforces spending controls across the
pipeline". It did not. Before this module, `CostTracker` had no caller
anywhere outside its own tests: no skill documented the call protocol, no
pipeline manifest invoked it, and `write_checkpoint(cost_snapshot=...)` was an
optional dict the agent had to assemble by hand. Backlot's board read
`cp["cost_snapshot"]` to draw a cost meter that nothing ever wrote.

So the cap that was meant to stop a runaway spend was unreachable, on a
project whose own README advertises per-video costs to the cent.

How it is wired
---------------
`BaseTool.__init_subclass__` already wraps every concrete `execute()` for
Backlot event emission. That wrapper is the only place in the system that sees
every tool call regardless of what the agent remembers to do, so the gate goes
there rather than into a skill instruction.

Scope is deliberately narrow:

- **Only `ToolRuntime.API` tools are charged.** Those 55 tools are the ones
  that actually spend. The four selectors are `HYBRID` and delegate to a
  provider, so gating on API avoids charging the same call twice.
- **Only calls attributable to a project are governed.** `cost_log.json` is a
  per-project artifact, so an ad-hoc tool call outside `projects/` is left
  alone — the same boundary the event layer already uses.
- **Only non-zero estimates open an entry.** A free call costs nothing to let
  through and would only add noise to the log.

Failure policy
--------------
Infrastructure failures inside this layer are swallowed: a broken config or an
unwritable log must never take down a render. Governance decisions are not —
`BudgetExceededError` and `ApprovalRequiredError` propagate to the caller,
because refusing to spend is the entire point.

Escape hatches
--------------
- `OPENMONTAGE_BUDGET_MODE=observe|warn|cap` overrides config.yaml.
- `OPENMONTAGE_BUDGET_TOTAL_USD=<float>` overrides the ceiling.
- `OPENMONTAGE_SINGLE_ACTION_USD=<float>` overrides the per-call approval
  threshold.
- `OPENMONTAGE_APPROVE_TOOLS=name,name` (or `*`) pre-approves paid tools for
  unattended runs, standing in for the human who would otherwise be asked.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Optional

from lib.config_model import BudgetMode
from tools.cost_tracker import (
    ApprovalRequiredError,
    BudgetExceededError,
    CostTracker,
)

__all__ = [
    "ApprovalRequiredError",
    "BudgetExceededError",
    "budget_enabled",
    "cost_snapshot",
    "reset_trackers",
    "tracker_for",
]

_LOCK = threading.RLock()
_TRACKERS: dict[str, CostTracker] = {}

_DISABLE_FLAG = "OPENMONTAGE_BUDGET_DISABLED"
_MODE_ENV = "OPENMONTAGE_BUDGET_MODE"
_TOTAL_ENV = "OPENMONTAGE_BUDGET_TOTAL_USD"
_SINGLE_ENV = "OPENMONTAGE_SINGLE_ACTION_USD"
_APPROVE_ENV = "OPENMONTAGE_APPROVE_TOOLS"

_REPO_ROOT = Path(__file__).resolve().parent.parent


def budget_enabled() -> bool:
    """False disables the gate entirely (kill switch for debugging)."""
    return os.environ.get(_DISABLE_FLAG, "").strip().lower() not in {"1", "true", "yes"}


def _budget_config() -> dict[str, Any]:
    """Read the `budget:` block from config.yaml, then apply env overrides."""
    cfg: dict[str, Any] = {}
    config_path = _REPO_ROOT / "config.yaml"
    if config_path.is_file():
        try:
            import yaml

            with open(config_path, encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
            block = loaded.get("budget")
            if isinstance(block, dict):
                cfg = dict(block)
        except Exception:
            cfg = {}

    mode_raw = os.environ.get(_MODE_ENV, "").strip().lower() or cfg.get("mode", "warn")
    try:
        mode = BudgetMode(mode_raw)
    except ValueError:
        mode = BudgetMode.WARN

    total_raw = os.environ.get(_TOTAL_ENV, "").strip() or cfg.get("total_usd", 10.0)
    try:
        total = float(total_raw)
    except (TypeError, ValueError):
        total = 10.0

    single_raw = (
        os.environ.get(_SINGLE_ENV, "").strip()
        or cfg.get("single_action_approval_usd", 0.50)
    )
    try:
        single = float(single_raw)
    except (TypeError, ValueError):
        single = 0.50

    return {
        "mode": mode,
        "budget_total_usd": total,
        "reserve_pct": float(cfg.get("reserve_pct", 0.10) or 0.0),
        "single_action_approval_usd": single,
        "require_approval_for_new_paid_tool": bool(
            cfg.get("require_approval_for_new_paid_tool", True)
        ),
    }


def _preapproved() -> set[str]:
    raw = os.environ.get(_APPROVE_ENV, "").strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def tracker_for(project_dir: Path) -> Optional[CostTracker]:
    """Return the cached CostTracker for a project, creating it on first use.

    Returns None when the gate is disabled or the tracker cannot be built;
    callers treat None as "ungoverned" and proceed.
    """
    if not budget_enabled():
        return None
    try:
        key = str(Path(project_dir).resolve())
    except Exception:
        return None

    with _LOCK:
        existing = _TRACKERS.get(key)
        if existing is not None:
            return existing
        try:
            cfg = _budget_config()
            tracker = CostTracker(
                cost_log_path=Path(key) / "cost_log.json",
                **cfg,
            )
            approve = _preapproved()
            if "*" in approve:
                tracker.require_approval_for_new_paid_tool = False
            else:
                for name in approve:
                    tracker.approve_tool(name)
            _TRACKERS[key] = tracker
            return tracker
        except Exception:
            return None


def cost_snapshot(project_dir: Path) -> Optional[dict[str, float]]:
    """Live spend summary for a project, or None if it has no tracker yet.

    `lib.checkpoint.write_checkpoint` calls this to fill `cost_snapshot` when
    the caller did not supply one, which is what finally puts numbers behind
    Backlot's cost meter.
    """
    with _LOCK:
        try:
            key = str(Path(project_dir).resolve())
        except Exception:
            return None
        tracker = _TRACKERS.get(key)
    if tracker is None:
        log = Path(project_dir) / "cost_log.json"
        if not log.is_file():
            return None
        tracker = tracker_for(project_dir)
        if tracker is None:
            return None
    try:
        return tracker.cost_snapshot()
    except Exception:
        return None


def reset_trackers() -> None:
    """Drop cached trackers. Tests use this to isolate projects."""
    with _LOCK:
        _TRACKERS.clear()
