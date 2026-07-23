"""Shared, opt-in test fixtures.

Nothing in this file is autouse. Every fixture here applies only to tests that
request it by name, so placing it at the ``tests/`` root adds no repo-wide
behavior -- a test that does not name a fixture is completely unaffected.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def budget_gate_isolated(tmp_path, monkeypatch):
    """Isolate the budget gate onto a private config + ledger for one test.

    Purpose is DETERMINISM, not neutralization. Every control of the gate stays
    fully in force; only the *environment the gate reads* is redirected:

      - ``OPENMONTAGE_CONFIG`` -> a private ``config.yaml`` under ``tmp_path``,
        so the repo's real ``config.yaml`` (and any future edit to it) cannot
        make these tests flap.
      - ``OPENMONTAGE_COST_LOG`` -> a private ledger under ``tmp_path``, so tests
        never touch ``pipeline/cost_log.json`` and never contend with each other.

    What remains ENFORCED, exactly as in production:

      - the fail-closed ``None``-bound refusal -- a paid production tool that has
        not yet declared ``max_cost_usd()`` still raises ``BudgetGateError``.
        This fixture therefore CANNOT hide a missing or broken bound; a test
        that opts in will keep failing until the tool declares a real bound.
      - the daily aggregate cap (``mode: cap``).
      - both approval safeguards: ``single_action_approval_usd`` (a $5.00 test
        ceiling -- still refuses anything above it) and
        ``require_approval_for_new_paid_tool`` (still refuses the first paid use
        of any tool that was not explicitly approved).

    A test that legitimately expects a paid provider call to proceed approves
    that specific tool through the gate's OWN api -- it does not disable the
    safeguard::

        def test_veo_execute(budget_gate_isolated):
            budget_gate_isolated.approve_tool("veo_video")
            ...

    Yields the process-wide :class:`CostTracker` the gate will use, so the test
    can call ``approve_tool`` on the very instance ``execute()`` later reserves
    against.
    """
    import lib.budget_gate as gate

    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "budget:\n"
        "  mode: cap\n"
        "  total_usd: 100.00\n"
        "  period: daily\n"
        "  timezone: system_local\n"
        "  reserve_pct: 0.0\n"
        "  single_action_approval_usd: 5.00\n"
        "  require_approval_for_new_paid_tool: true\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENMONTAGE_CONFIG", str(cfg))
    monkeypatch.setenv("OPENMONTAGE_COST_LOG", str(tmp_path / "cost_log.json"))

    gate.reset()
    try:
        yield gate.get_tracker()
    finally:
        gate.reset()
