"""Contract tests for the budget governance gate (CostGate).

Covers the enforcement that was missing in production code: config.yaml's
budget block is wired to a CostTracker at tool execution time, and the
tracker's cap / approval / reconcile rules actually run.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib.config_model import BudgetConfig, BudgetMode
from tools.base_tool import BaseTool, ToolResult
from tools.cost_gate import CostGate
from tools.cost_tracker import ApprovalRequiredError, BudgetExceededError
from tools.tool_registry import ToolRegistry


class _PaidTool(BaseTool):
    """Tool whose calls cost money; cost controllable per test."""

    name = "fake_paid"
    estimated = 2.0
    actual = 1.8

    def estimate_cost(self, inputs: dict) -> float:
        return inputs.get("estimate", self.estimated)

    def execute(self, inputs: dict) -> ToolResult:
        if inputs.get("raise_error"):
            raise RuntimeError("boom")
        return ToolResult(success=True, data={}, cost_usd=inputs.get("actual", self.actual))


class _FreeTool(BaseTool):
    """Tool that never costs anything."""

    name = "fake_free"

    def execute(self, inputs: dict) -> ToolResult:
        return ToolResult(success=True, data={})


def _gate(**overrides) -> tuple[CostGate, Path]:
    kwargs = {"mode": BudgetMode.WARN}
    kwargs.update(overrides)
    config = BudgetConfig(**kwargs)
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "cost_log.json"
        return CostGate(config, cost_log_path=log), log


class CostGateTests(unittest.TestCase):
    def test_free_tool_passes_without_entries(self) -> None:
        gate, log = _gate()
        tool = _FreeTool()
        result = gate.execute(tool, {})
        self.assertTrue(result.success)
        self.assertFalse(log.exists())
        self.assertEqual(gate.tracker.entries, [])

    def test_wrapped_tool_records_estimate_reserve_reconcile(self) -> None:
        gate, log = _gate(
            total_usd=100.0,
            single_action_approval_usd=99.0,
            require_approval_for_new_paid_tool=False,
        )
        tool = _PaidTool()
        gate.wrap(tool)
        result = tool.execute({})
        self.assertTrue(result.success)
        self.assertEqual(len(gate.tracker.entries), 1)
        entry = gate.tracker.entries[0]
        self.assertEqual(entry["status"], "completed")
        self.assertEqual(entry["estimated_usd"], 2.0)
        self.assertEqual(entry["actual_usd"], 1.8)
        persisted = json.loads(log.read_text())
        self.assertEqual(persisted["entries"][0]["status"], "completed")

    def test_cap_mode_refuses_over_budget(self) -> None:
        gate, log = _gate(
            mode=BudgetMode.CAP,
            total_usd=1.0,
            single_action_approval_usd=99.0,
            require_approval_for_new_paid_tool=False,
        )
        tool = _PaidTool()
        gate.wrap(tool)
        with self.assertRaises(BudgetExceededError):
            tool.execute({})
        # The refused reservation is refunded, not left dangling.
        self.assertEqual(gate.tracker.entries[0]["status"], "refunded")

    def test_warn_mode_records_warning_but_executes(self) -> None:
        gate, _ = _gate(
            total_usd=1.0,
            single_action_approval_usd=99.0,
            require_approval_for_new_paid_tool=False,
        )
        tool = _PaidTool()
        gate.wrap(tool)
        result = tool.execute({})
        self.assertTrue(result.success)
        entry = gate.tracker.entries[0]
        self.assertTrue(entry["budget_warning"])

    def test_single_action_threshold_raises_in_warn_mode(self) -> None:
        gate, _ = _gate(single_action_approval_usd=0.50)
        tool = _PaidTool()
        gate.wrap(tool)
        with self.assertRaises(ApprovalRequiredError):
            tool.execute({})

    def test_single_action_threshold_ignored_in_observe_mode(self) -> None:
        gate, _ = _gate(mode=BudgetMode.OBSERVE, single_action_approval_usd=0.50)
        tool = _PaidTool()
        gate.wrap(tool)
        result = tool.execute({})
        self.assertTrue(result.success)

    def test_new_paid_tool_requires_approval_once(self) -> None:
        gate, log = _gate(
            single_action_approval_usd=99.0,
            require_approval_for_new_paid_tool=True,
        )
        tool = _PaidTool()
        gate.wrap(tool)
        with self.assertRaises(ApprovalRequiredError):
            tool.execute({})
        gate.approve_tool("fake_paid")
        result = tool.execute({})
        self.assertTrue(result.success)
        # The approval is persisted with the tracker.
        persisted = json.loads(log.read_text())
        self.assertIn("fake_paid", persisted["approved_tools"])

    def test_failed_execution_records_failed_entry(self) -> None:
        gate, log = _gate(
            total_usd=100.0,
            single_action_approval_usd=99.0,
            require_approval_for_new_paid_tool=False,
        )
        tool = _PaidTool()
        gate.wrap(tool)
        with self.assertRaises(RuntimeError):
            tool.execute({"raise_error": True})
        self.assertEqual(gate.tracker.entries[0]["status"], "failed")
        persisted = json.loads(log.read_text())
        self.assertEqual(persisted["entries"][0]["status"], "failed")

    def test_registry_enable_budget_wraps_registered_tools(self) -> None:
        registry = ToolRegistry()
        paid, free = _PaidTool(), _FreeTool()
        registry.register(paid)
        registry.register(free)
        config = BudgetConfig(
            mode=BudgetMode.CAP,
            total_usd=1.0,
            single_action_approval_usd=99.0,
            require_approval_for_new_paid_tool=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "cost_log.json"
            registry.enable_budget(config, cost_log_path=log)
            with self.assertRaises(BudgetExceededError):
                registry.get("fake_paid").execute({})
            result = registry.get("fake_free").execute({})
            self.assertTrue(result.success)

    def test_tools_registered_after_enable_are_wrapped(self) -> None:
        registry = ToolRegistry()
        config = BudgetConfig(
            mode=BudgetMode.CAP,
            total_usd=1.0,
            single_action_approval_usd=99.0,
            require_approval_for_new_paid_tool=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "cost_log.json"
            registry.enable_budget(config, cost_log_path=log)
            registry.register(_PaidTool())
            with self.assertRaises(BudgetExceededError):
                registry.get("fake_paid").execute({})

    def test_enable_budget_from_config_activates_only_with_budget_block(self) -> None:
        from tools.tool_registry import enable_budget_from_config

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # No config.yaml: activation is a no-op.
            gate = enable_budget_from_config(ToolRegistry(), repo_root=root)
            self.assertIsNone(gate)
            # With a budget block: the gate is installed and enforces.
            (root / "config.yaml").write_text(
                "budget:\n"
                "  mode: cap\n"
                "  total_usd: 1.0\n"
                "  single_action_approval_usd: 99.0\n"
                "  require_approval_for_new_paid_tool: false\n"
            )
            registry = ToolRegistry()
            registry.register(_PaidTool())
            gate = enable_budget_from_config(registry, repo_root=root)
            self.assertIsNotNone(gate)
            self.assertEqual(gate.tracker.mode, BudgetMode.CAP)
            with self.assertRaises(BudgetExceededError):
                registry.get("fake_paid").execute({})

    def test_importing_tool_registry_has_no_side_effect(self) -> None:
        # The module import must not activate governance on its own.
        import tools.tool_registry as tr
        self.assertIsNone(tr.registry.cost_gate)


if __name__ == "__main__":
    unittest.main()
