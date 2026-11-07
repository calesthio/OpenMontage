"""Strict zero-cost gate behaviour (Master Plan section 9).

The gate must fail closed: an operation nobody priced, or an endpoint nobody
named, is BLOCKED — never treated as free. Auth, billing, rate-limit and
transport failures must never silently switch to another provider.
"""

from __future__ import annotations

import pytest

from lib.zero_cost_gate import (
    AUTH_ERROR,
    BILLING_ERROR,
    BUDGETED,
    NO_RESULTS,
    RATE_LIMITED,
    STRICT_ZERO_COST,
    TRANSPORT_ERROR,
    UNKNOWN_FAILURE,
    RunBudgetLedger,
    ToolFacts,
    ZeroCostViolation,
    assert_zero_cost,
    classify_failure,
    evaluate_call,
    evaluate_batch,
    failure_note,
    facts_from_registry,
    reroute_allowed,
)


def _local(**overrides):
    facts = dict(
        tool="video_compose",
        operation="render",
        runtime="local",
        route="ffmpeg",
        cost_usd=0.0,
    )
    facts.update(overrides)
    return ToolFacts(**facts)


def _cloud(**overrides):
    facts = dict(
        tool="example_cloud_tts",
        operation="synthesize",
        runtime="api",
        route="https://api.example.com/v1/tts",
        cost_usd=0.02,
    )
    facts.update(overrides)
    return ToolFacts(**facts)


# --- fail closed -----------------------------------------------------------


def test_unknown_cost_is_blocked_not_treated_as_free() -> None:
    decision = evaluate_call(_local(cost_usd=None))
    assert decision.blocked
    assert "cost_usd is null" in decision.reason


def test_unknown_route_is_blocked() -> None:
    decision = evaluate_call(_local(route=None))
    assert decision.blocked
    assert "unknown route" in decision.reason


def test_negative_cost_is_blocked() -> None:
    decision = evaluate_call(_local(cost_usd=-0.01))
    assert decision.blocked


def test_unavailable_tool_is_blocked() -> None:
    """An unavailable provider is surfaced, never routed around."""

    decision = evaluate_call(_local(status="unavailable"))
    assert decision.blocked
    assert "surface the provider" in decision.reason


# --- what passes -----------------------------------------------------------


def test_declared_zero_cost_local_call_is_allowed() -> None:
    decision = evaluate_call(_local())
    assert decision.allowed
    assert decision.cost_usd == 0.0


def test_a_batch_reports_every_decision() -> None:
    decisions = evaluate_batch([_local(), _cloud()])
    assert [d.verdict for d in decisions] == ["allowed", "blocked"]


# --- paid paths ------------------------------------------------------------


def test_paid_call_is_blocked_in_strict_mode() -> None:
    decision = evaluate_call(_cloud())
    assert decision.blocked
    assert "strict zero-cost" in decision.reason


def test_paid_call_requires_explicit_user_approval() -> None:
    denied = evaluate_call(_cloud())
    approved = evaluate_call(_cloud(), user_approved=True)
    assert denied.blocked and approved.allowed


def test_budgeted_mode_allows_a_priced_call_without_approval() -> None:
    decision = evaluate_call(_cloud(), mode=BUDGETED)
    assert decision.allowed
    assert decision.mode == BUDGETED


def test_budgeted_mode_still_blocks_unknown_cost() -> None:
    decision = evaluate_call(_cloud(cost_usd=None), mode=BUDGETED)
    assert decision.blocked


def test_assert_zero_cost_raises_on_a_blocked_call() -> None:
    with pytest.raises(ZeroCostViolation):
        assert_zero_cost(_cloud())
    assert_zero_cost(_local())  # must not raise


# --- failure taxonomy ------------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "message", "expected"),
    [
        (401, "Unauthorized", AUTH_ERROR),
        (403, "Forbidden", AUTH_ERROR),
        (429, "Too Many Requests", RATE_LIMITED),
        (402, "Payment Required", BILLING_ERROR),
        (500, "Internal Server Error", TRANSPORT_ERROR),
        (None, "connection reset by peer", TRANSPORT_ERROR),
        (404, "no results for query", TRANSPORT_ERROR),
    ],
)
def test_failure_classification(status_code, message, expected) -> None:
    assert classify_failure(status_code, message) == expected


def test_no_results_stays_distinct_from_an_error() -> None:
    """'Nothing matched' and 'the search could not run' are different facts."""

    assert classify_failure(200, "empty result set") == UNKNOWN_FAILURE
    assert classify_failure(None, "rate limited") == RATE_LIMITED
    assert NO_RESULTS not in {classify_failure(429, "x"), classify_failure(401, "y")}


@pytest.mark.parametrize(
    "failure",
    [AUTH_ERROR, BILLING_ERROR, RATE_LIMITED, TRANSPORT_ERROR, UNKNOWN_FAILURE, NO_RESULTS],
)
def test_no_failure_ever_reroutes(failure) -> None:
    assert reroute_allowed(failure) is False


def test_failure_notes_exist_for_the_taxonomy() -> None:
    for failure in (
        AUTH_ERROR,
        BILLING_ERROR,
        RATE_LIMITED,
        TRANSPORT_ERROR,
        NO_RESULTS,
        UNKNOWN_FAILURE,
    ):
        assert failure_note(failure)


# --- ledger ----------------------------------------------------------------


def test_ledger_records_blocked_and_allowed_and_totals_cost() -> None:
    ledger = RunBudgetLedger()
    ledger.record(evaluate_call(_local()))
    ledger.record(evaluate_call(_cloud()))
    summary = ledger.summary()
    assert summary["allowed"] == 1
    assert summary["blocked"] == 1
    assert summary["total_cost_usd"] == 0.0
    assert summary["mode"] == STRICT_ZERO_COST
    assert summary["blocked_reasons"][0]["tool"] == "example_cloud_tts"


def test_ledger_accumulates_only_allowed_cost() -> None:
    ledger = RunBudgetLedger(mode=BUDGETED)
    ledger.record(evaluate_call(_cloud(), mode=BUDGETED, user_approved=True))
    ledger.record(evaluate_call(_local(), mode=BUDGETED))
    assert ledger.total_cost_usd == 0.02


# --- registry integration --------------------------------------------------


def test_facts_from_registry_reports_the_real_runtime() -> None:
    facts = facts_from_registry("video_compose", "render")
    assert facts.tool == "video_compose"
    assert facts.is_local
    # cost is never invented by the registry lookup
    assert facts.cost_usd is None
    assert evaluate_call(facts).blocked


def test_facts_from_registry_blocks_an_unpriced_cloud_route() -> None:
    facts = facts_from_registry("elevenlabs_tts", "synthesize")
    assert facts.cost_known is False
    assert evaluate_call(facts).blocked


def test_facts_from_registry_for_an_unknown_tool_is_blocked() -> None:
    facts = facts_from_registry("not_a_real_tool")
    assert facts.status == "unknown"
    assert evaluate_call(facts).blocked
