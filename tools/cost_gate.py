"""Budget governance gate: wires config.yaml's budget block to the CostTracker.

docs/ARCHITECTURE.md promises: "The CostTracker enforces spending controls
across the pipeline." This module is the enforcement point that was missing:
nothing in the shipped code constructed a CostTracker or connected
``config.yaml``'s ``budget:`` block to tool execution.

The gate wraps tool execution so that, for every paid operation:

- a preflight estimate is produced (``BaseTool.estimate_cost``)
- the estimate is reserved against the budget before execution
- cap mode refuses reservations that exceed the usable budget
  (``BudgetExceededError``)
- actions over the single-action approval threshold, and first paid use of a
  new tool, raise ``ApprovalRequiredError`` unless approved (in warn/cap mode;
  observe mode records without blocking)
- actual spend is reconciled when the tool finishes, and a failed execution
  is recorded as failed instead of leaving a dangling reservation
- everything persists to ``cost_log.json``

Tools whose ``estimate_cost`` returns 0 (no override, or a genuinely free
operation) pass through untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from lib.config_model import BudgetConfig
from tools.base_tool import BaseTool
from tools.cost_tracker import CostTracker

_OPERATION = "execute"


class CostGate:
    """Wraps tool execution with CostTracker governance."""

    def __init__(self, config: BudgetConfig, cost_log_path: Optional[Path] = None) -> None:
        self.config = config
        self.tracker = CostTracker(
            budget_total_usd=config.total_usd,
            reserve_pct=config.reserve_pct,
            single_action_approval_usd=config.single_action_approval_usd,
            require_approval_for_new_paid_tool=config.require_approval_for_new_paid_tool,
            mode=config.mode,
            cost_log_path=cost_log_path,
        )
        self._wrapped: set[str] = set()

    # ---- Approval ----

    def approve_tool(self, tool: str) -> None:
        """Pre-approve a tool so its paid calls skip the new-tool gate."""
        self.tracker.approve_tool(tool)

    # ---- Preflight ----

    def guard(self, tool: BaseTool, inputs: dict[str, Any]) -> Optional[str]:
        """Estimate and reserve budget for a tool call.

        Returns the cost entry id when a reservation was made, or None for
        free operations. Raises BudgetExceededError or ApprovalRequiredError
        per the tracker's rules.
        """
        estimated = tool.estimate_cost(inputs)
        if not isinstance(estimated, (int, float)) or estimated is None:
            estimated = 0.0
        if float(estimated) <= 0.0:
            return None
        entry_id = self.tracker.estimate(tool.name, _OPERATION, float(estimated))
        try:
            self.tracker.reserve(entry_id)
        except Exception:
            # Keep the cost log clean when a rule refuses the call: the
            # reservation is refunded before the error reaches the caller.
            self.tracker.refund(entry_id)
            raise
        return entry_id

    # ---- Execution wrapping ----

    def execute(self, tool: BaseTool, inputs: dict[str, Any]) -> Any:
        """Run a tool through the gate: guard, execute, reconcile.

        Uses the tool's original (pre-gate) execute, so calling this on an
        already wrapped tool never double-guards. Raises the tracker's errors
        before the tool runs when the budget rules refuse the call.
        """
        entry_id = self.guard(tool, inputs)
        if entry_id is None:
            return self._original_execute(tool)(inputs)
        try:
            result = self._original_execute(tool)(inputs)
        except Exception:
            self.tracker.reconcile(entry_id, 0.0, success=False)
            raise
        actual = getattr(result, "cost_usd", None)
        if not isinstance(actual, (int, float)):
            actual = 0.0
        self.tracker.reconcile(entry_id, float(actual), success=True)
        return result

    @staticmethod
    def _original_execute(tool: BaseTool) -> Any:
        """The tool's execute with any gate wrappers peeled off."""
        original = getattr(tool, "_cost_gate_original_execute", None)
        return original if original is not None else tool.execute

    def wrap(self, tool: BaseTool) -> None:
        """Install the gate as the tool's execute method (idempotent).

        Wraps the tool's pre-gate execute, so replacing one gate with another
        never chains guards.
        """
        if tool.name in self._wrapped and getattr(tool, "_cost_gate_original_execute", None) is not None:
            return
        original_execute = self._original_execute(tool)
        tool._cost_gate_original_execute = original_execute  # type: ignore[attr-defined]

        def guarded(inputs: dict[str, Any], _tool: BaseTool = tool, _orig=original_execute) -> Any:
            entry_id = self.guard(_tool, inputs)
            if entry_id is None:
                return _orig(inputs)
            try:
                result = _orig(inputs)
            except Exception:
                self.tracker.reconcile(entry_id, 0.0, success=False)
                raise
            actual = getattr(result, "cost_usd", None)
            if not isinstance(actual, (int, float)):
                actual = 0.0
            self.tracker.reconcile(entry_id, float(actual), success=True)
            return result

        tool.execute = guarded  # type: ignore[method-assign]
        self._wrapped.add(tool.name)

    # ---- Reporting ----

    def snapshot(self) -> dict[str, Any]:
        """Current cost snapshot for preflight/reporting surfaces."""
        return self.tracker.cost_snapshot()
