"""Regression tests for tools/base_tool.py:

- BaseTool.estimate_cost()'s $0.00 default logs a warning when the tool is
  declared runtime=API (paid) and never overrode it, so the footgun (silently
  bypassing cost_tracker.reserve()'s budget-approval gates) is at least
  visible in logs -- but stays silent for legitimately free/local tools and
  for tools that do override it.
- idempotency_key() tolerates non-JSON-native values (Path, datetime, etc.)
  in idempotency_key_fields via json.dumps(..., default=str) instead of
  raising TypeError.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.base_tool import BaseTool, ToolResult, ToolRuntime


class _FreeLocalTool(BaseTool):
    """Legitimately free tool that never overrides estimate_cost()."""

    name = "free_local_tool"
    runtime = ToolRuntime.LOCAL

    def execute(self, inputs):
        return ToolResult(success=True)


class _PaidApiToolMissingEstimate(BaseTool):
    """Paid tool that forgot to override estimate_cost() -- the footgun."""

    name = "paid_api_tool_missing_estimate"
    runtime = ToolRuntime.API

    def execute(self, inputs):
        return ToolResult(success=True)


class _PaidApiToolWithEstimate(BaseTool):
    """Paid tool that correctly overrides estimate_cost()."""

    name = "paid_api_tool_with_estimate"
    runtime = ToolRuntime.API

    def estimate_cost(self, inputs):
        return 0.05

    def execute(self, inputs):
        return ToolResult(success=True)


def test_free_local_tool_default_estimate_cost_logs_no_warning(caplog):
    tool = _FreeLocalTool()
    with caplog.at_level("WARNING"):
        cost = tool.estimate_cost({})
    assert cost == 0.0
    assert len(caplog.records) == 0


def test_paid_api_tool_missing_estimate_cost_logs_warning(caplog):
    tool = _PaidApiToolMissingEstimate()
    with caplog.at_level("WARNING"):
        cost = tool.estimate_cost({})
    assert cost == 0.0
    assert len(caplog.records) == 1
    assert "paid_api_tool_missing_estimate" in caplog.records[0].message
    assert "estimate_cost" in caplog.records[0].message


def test_cost_currency_defaults_to_usd():
    # Regression: confirmed live that every tool's cost_usd was treated as
    # CNY unconditionally by the job cost ledger — real for the ~40 non-MaaS
    # provider tools whose cost_usd is genuine US dollars. cost_currency
    # defaults to "USD" (matching the field's literal name and what's true
    # for the large majority of tools); only MaasBaseTool overrides it.
    assert _PaidApiToolWithEstimate.cost_currency == "USD"
    assert _PaidApiToolWithEstimate().cost_currency == "USD"


def test_paid_api_tool_with_override_logs_no_warning(caplog):
    tool = _PaidApiToolWithEstimate()
    with caplog.at_level("WARNING"):
        cost = tool.estimate_cost({})
    assert cost == 0.05
    assert len(caplog.records) == 0


# ---- idempotency_key() non-serializable input ----


class _IdempotentTool(BaseTool):
    name = "idempotent_tool"
    idempotency_key_fields = ["output_path", "created_at"]

    def execute(self, inputs):
        return ToolResult(success=True)


def test_idempotency_key_tolerates_path_and_datetime_values():
    tool = _IdempotentTool()
    inputs = {
        "output_path": Path("/tmp/some/output.mp4"),
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    # Must not raise TypeError, and must produce a stable 16-char hex digest.
    key = tool.idempotency_key(inputs)
    assert isinstance(key, str)
    assert len(key) == 16
    assert key == tool.idempotency_key(inputs)


def test_idempotency_key_still_works_for_plain_json_native_values():
    tool = _IdempotentTool()
    inputs = {"output_path": "/tmp/out.mp4", "created_at": "2026-01-01"}
    key = tool.idempotency_key(inputs)
    assert isinstance(key, str)
    assert len(key) == 16
