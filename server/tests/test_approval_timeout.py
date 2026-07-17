"""Approval-gate timeout semantics.

Original race (audit 2026-07-15, BUG-13): a decision landing in the instant
between asyncio.wait_for timing out and the caller processing it used to stay
behind in _approval_results with the asyncio.Event still set — the job's NEXT
gate's wait_for_approval returned immediately and consumed the dead gate's
decision, silently approving a different question than the one the human
answered.

Roadmap 0.2 then changed WHAT a timeout means: wait_for_approval no longer
fabricates a reject on the human's behalf — it returns
{"action": "timeout"}, and the runner's _wait_for_decision ladder decides
what to do (remind, keep waiting, eventually expire loudly). A boundary
decision is now CONSUMED AND HONORED by the gate it answered, which closes
the original race even harder: there is nothing left behind for the next
gate to steal.
"""

from __future__ import annotations

import asyncio

import pytest


async def test_boundary_decision_is_honored_by_its_own_gate(store, monkeypatch):
    store.create("j1", {})
    store.update("j1", status="awaiting_approval")

    # The human's decision lands "at the boundary": recorded in the store,
    # but the waiter's asyncio.wait_for has already fired its TimeoutError.
    assert store.set_approval("j1", "approve", "late") is True

    real_wait_for = asyncio.wait_for

    async def timing_out_wait_for(awaitable, timeout):
        awaitable.close()  # avoid the un-awaited-coroutine warning
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", timing_out_wait_for)
    result = await store.wait_for_approval("j1", timeout=3600)
    monkeypatch.setattr(asyncio, "wait_for", real_wait_for)

    # The decision belongs to THIS gate — it must be returned, not discarded
    # as the old auto-reject did (losing the human's actual answer).
    assert result == {"action": "approve", "feedback": "late"}

    # Let set_approval's deferred call_soon_threadsafe(ev.set) fire — it can
    # land AFTER the timeout path's own cleanup, which is exactly why the
    # next gate must re-arm through begin_approval_gate.
    await asyncio.sleep(0)

    # The next gate has nothing to steal: it times out on its own merits
    # and reports that honestly as a timeout, never as a fabricated reject.
    store.begin_approval_gate("j1")
    store.update("j1", status="awaiting_approval")
    result2 = await store.wait_for_approval("j1", timeout=0.05)
    assert result2["action"] == "timeout"


async def test_timeout_is_reported_as_timeout_not_reject(store):
    # Regression (roadmap 0.2): the old behavior silently returned
    # {"action": "reject", "feedback": "Approval timed out"} — at a stage
    # gate that triggered a paid regenerate the human never asked for.
    store.create("j3", {})
    store.update("j3", status="awaiting_approval")
    result = await store.wait_for_approval("j3", timeout=0.05)
    assert result["action"] == "timeout"


async def test_normal_approval_still_flows(store):
    store.create("j2", {})
    store.update("j2", status="awaiting_approval")

    async def approve_soon():
        await asyncio.sleep(0.01)
        store.set_approval("j2", "approve", "ok")

    task = asyncio.create_task(approve_soon())
    result = await store.wait_for_approval("j2", timeout=5)
    await task
    assert result == {"action": "approve", "feedback": "ok"}
