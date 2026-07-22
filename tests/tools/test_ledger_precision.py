"""Ledger monetary precision: no positive paid amount can become ledger zero.

The ledger's explicit quantum is $0.0001 (LEDGER_QUANTUM_USD). Positive
amounts quantize UPWARD in Decimal (ROUND_CEILING) at the central accounting
layer -- estimate/reservation, actual-cost reconciliation, and the gate's
settle-fallback handle. Provider estimators return raw floats and perform no
monetary rounding of their own, so a genuine sub-quantum charge (a
1-character TTS request, a sub-second transcription) reaches the gate as a
positive number and reserves at least one quantum. Repeated sub-quantum
calls therefore accumulate against the cap instead of slipping under it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from lib.config_model import BudgetMode
from tools.base_tool import BaseTool, ToolResult, ToolRuntime
from tools.cost_tracker import (
    BudgetExceededError,
    CostTracker,
    LEDGER_QUANTUM_USD,
    format_usd,
    quantize_usd,
)


def make_tracker(log_path, **kw):
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


# ---- The quantization rule itself ----

class TestQuantizeUsd:
    def test_quantum_is_declared(self):
        assert float(LEDGER_QUANTUM_USD) == 0.0001

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (0.0, 0.0),                # exactly zero stays exactly zero
            (-1.0, 0.0),               # negatives can never credit the ledger
            (0.00001, 0.0001),         # sub-quantum positives ceil to one quantum
            (0.00004, 0.0001),
            (0.0001, 0.0001),          # exact quantum unchanged
            (0.00012, 0.0002),         # ceiling, not nearest
            (0.0003, 0.0003),
            (3.20, 3.20),              # normal values keep exact precision
            (10.0, 10.0),
        ],
    )
    def test_grid(self, raw, expected):
        assert quantize_usd(raw) == pytest.approx(expected, abs=1e-12)

    def test_positive_never_becomes_zero(self):
        for raw in (1e-7, 1e-6, 1e-5, 5.4e-5, 9.9e-5):
            assert quantize_usd(raw) >= float(LEDGER_QUANTUM_USD)


# ---- Reservation and reconciliation on the grid ----

class TestLedgerAccounting:
    def test_sub_quantum_bound_reserves_one_quantum(self, tmp_path):
        t = make_tracker(tmp_path / "log.json")
        eid = t.estimate("tiny_paid", "op", 0.00004)
        entry = next(e for e in t.entries if e["id"] == eid)
        assert entry["estimated_usd"] == pytest.approx(0.0001)
        t.reserve(eid)
        assert t.reserved_on(t.current_budget_date()) == pytest.approx(0.0001)

    def test_positive_actual_cannot_be_recorded_as_zero(self, tmp_path):
        t = make_tracker(tmp_path / "log.json")
        eid = t.estimate("tiny_paid", "op", 0.00004)
        t.reserve(eid)
        t.reconcile(eid, 0.00004, success=True)
        entry = next(e for e in t.entries if e["id"] == eid)
        assert entry["actual_usd"] == pytest.approx(0.0001)
        assert t.spent_on(t.current_budget_date()) > 0

    def test_repeated_sub_quantum_calls_reach_a_small_cap(self, tmp_path):
        """Five $0.00004 calls fill a $0.0005 cap; the sixth is refused.
        Without upward quantization they would all record zero forever."""
        t = make_tracker(tmp_path / "log.json", budget_total_usd=0.0005)
        for _ in range(5):
            eid = t.estimate("tiny_paid", "op", 0.00004)
            t.reserve(eid)
            t.reconcile(eid, 0.00004, success=True)
        assert t.spent_on(t.current_budget_date()) == pytest.approx(0.0005)
        with pytest.raises(BudgetExceededError):
            t.reserve(t.estimate("tiny_paid", "op", 0.00004))

    def test_exact_cap_at_quantum_scale_still_allowed(self, tmp_path):
        t = make_tracker(tmp_path / "log.json", budget_total_usd=0.0003)
        for _ in range(3):
            t.reserve(t.estimate("tiny_paid", "op", 0.0001))
        assert t.reserved_on(t.current_budget_date()) == pytest.approx(0.0003)
        with pytest.raises(BudgetExceededError):
            t.reserve(t.estimate("tiny_paid", "op", 0.0001))

    def test_refund_releases_exactly_the_quantized_reservation(self, tmp_path):
        t = make_tracker(tmp_path / "log.json")
        eid = t.estimate("tiny_paid", "op", 0.00004)
        t.reserve(eid)
        t.refund(eid)
        assert t.reserved_on(t.current_budget_date()) == pytest.approx(0.0)
        assert t.remaining_on(t.current_budget_date()) == pytest.approx(10.0)

    def test_reconcile_clears_reservation_and_records_grid_actual(self, tmp_path):
        t = make_tracker(tmp_path / "log.json")
        eid = t.estimate("tiny_paid", "op", 0.00025)
        t.reserve(eid)
        t.reconcile(eid, 0.00013, success=True)
        entry = next(e for e in t.entries if e["id"] == eid)
        assert entry["reserved_usd"] == 0.0
        assert entry["actual_usd"] == pytest.approx(0.0002)  # ceiling of 0.00013
        assert t.remaining_on(t.current_budget_date()) == pytest.approx(10.0 - 0.0002)

    def test_zero_estimate_records_exactly_zero(self, tmp_path):
        t = make_tracker(tmp_path / "log.json")
        eid = t.estimate("free_row", "op", 0.0)
        entry = next(e for e in t.entries if e["id"] == eid)
        assert entry["estimated_usd"] == 0.0


# ---- Short-input estimators no longer fabricate zero ----

class TestShortInputEstimators:
    def test_one_char_kling_tts_is_positive_before_quantization(self):
        from tools.audio.kling_tts import KlingTTS

        tool = KlingTTS()
        estimate = tool.estimate_cost({"text": "x"})
        bound = tool.max_cost_usd({"text": "x"})
        assert estimate == pytest.approx(0.000018)
        assert bound == pytest.approx(0.000054)
        assert bound >= estimate
        assert quantize_usd(bound) >= 0.0001  # what the ledger will reserve

    @pytest.mark.parametrize(
        "module,cls,inputs",
        [
            ("tools.audio.openai_tts", "OpenAITTS", {"text": "x"}),
            ("tools.audio.doubao_tts", "DoubaoTTS", {"text": "x"}),
            ("tools.audio.dashscope_tts", "DashscopeTTS", {"text": "x"}),
            ("tools.audio.google_tts", "GoogleTTS", {"text": "x", "voice": "en-US-Standard-A"}),
            ("tools.audio.music_gen", "MusicGen", {"prompt": "p", "duration_seconds": 0.05}),
            ("tools.analysis.azure_stt", "AzureSpeechToText", {"duration_seconds": 0.1}),
        ],
    )
    def test_genuine_paid_request_never_estimates_zero(self, module, cls, inputs):
        import importlib

        tool = getattr(importlib.import_module(module), cls)()
        estimate = tool.estimate_cost(inputs)
        assert estimate > 0, f"{tool.name}: positive paid request estimated zero"
        bound = tool.max_cost_usd(inputs)
        assert bound is not None and bound >= estimate
        assert quantize_usd(bound) >= float(LEDGER_QUANTUM_USD)


# ---- End-to-end through the gate ----

class _SubQuantumPaidTool(BaseTool):
    name = "sub_quantum_paid"
    runtime = ToolRuntime.API

    def estimate_cost(self, inputs):
        return 0.00002

    def max_cost_usd(self, inputs):
        return 0.00004

    def execute(self, inputs):
        return ToolResult(success=True, cost_usd=0.00004)


class TestGateEndToEnd:
    def test_sub_quantum_call_is_gated_reserved_and_settled_nonzero(
        self, budget_gate_isolated, monkeypatch
    ):
        import os

        budget_gate_isolated.approve_tool("sub_quantum_paid")
        result = _SubQuantumPaidTool().execute({})
        assert result.success

        log = json.loads(Path(os.environ["OPENMONTAGE_COST_LOG"]).read_text())
        entry = log["entries"][-1]
        assert entry["tool"] == "sub_quantum_paid"
        assert entry["status"] == "completed"
        assert entry["actual_usd"] == pytest.approx(0.0001)  # never zero
        assert entry["reserved_usd"] == 0.0                  # settled

    def test_three_sub_quantum_calls_accumulate_in_the_ledger(
        self, budget_gate_isolated
    ):
        import os

        budget_gate_isolated.approve_tool("sub_quantum_paid")
        for _ in range(3):
            assert _SubQuantumPaidTool().execute({}).success
        log = json.loads(Path(os.environ["OPENMONTAGE_COST_LOG"]).read_text())
        total = sum(e["actual_usd"] for e in log["entries"])
        assert total == pytest.approx(0.0003)


# ---- Operator messages stay accurate at this scale ----

class TestMessages:
    def test_quantum_scale_amounts_display_accurately(self):
        assert format_usd(0.0001) == "$0.0001"
        assert format_usd(0.00004) == "$0.000040"
        assert format_usd(0.0018) == "$0.0018"
