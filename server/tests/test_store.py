"""JobStore: CRUD, event ring + bisect, durable persistence, approval gate."""

from __future__ import annotations

import asyncio

import pytest

from app import store as store_mod
from app.store import JobStore, MAX_EVENTS_PER_JOB


def test_create_get_update_all(store):
    store.create("j1", {"project_name": "demo", "options": {"x": 1}})
    job = store.get("j1")
    assert job["status"] == "queued"
    assert job["completed_stages"] == []
    assert job["cost_cny"] == 0.0
    assert job["project_name"] == "demo"

    store.update("j1", status="running", cost_cny=3.5)
    assert store.get("j1")["status"] == "running"
    assert store.get("j1")["cost_cny"] == 3.5
    assert "j1" in store.all()
    assert store.get("missing") is None


def test_events_seq_and_bisect(store):
    store.create("j", {})
    for i in range(10):
        store.push_event("j", {"type": "x", "i": i})

    assert [e["seq"] for e in store.get_events("j", after_seq=-1)] == list(range(10))
    assert [e["seq"] for e in store.get_events("j", after_seq=4)] == [5, 6, 7, 8, 9]
    assert store.get_events("j", after_seq=9) == []      # caught up
    assert store.get_events("j", after_seq=999) == []    # beyond head
    # stored events carry the injected payload
    assert store.get_events("j", after_seq=-1)[0]["type"] == "x"


def test_event_ring_capped_but_seq_monotonic(store, monkeypatch):
    monkeypatch.setattr(store_mod, "MAX_EVENTS_PER_JOB", 50)
    store.create("j", {})
    for i in range(70):
        store.push_event("j", {"type": "e"})
    events = store.get_events("j", after_seq=-1)
    assert len(events) == 50                 # trimmed to cap
    assert events[0]["seq"] == 20            # oldest 20 evicted
    assert events[-1]["seq"] == 69           # seq stays monotonic across trim
    # a reconnect below the retained window still returns the retained tail
    assert store.get_events("j", after_seq=5)[0]["seq"] == 20


def test_persistence_round_trip(tmp_path):
    d = tmp_path / "js"
    s1 = JobStore(persist_dir=d)
    s1.create("j1", {"project_name": "demo"})
    s1.update("j1", status="running", current_stage="script",
              completed_stages=["research", "proposal"], cost_cny=12.5)
    for i in range(4):
        s1.push_event("j1", {"type": "stage_started", "i": i})

    # Simulate restart.
    s2 = JobStore(persist_dir=d)
    j = s2.get("j1")
    assert j is not None
    assert j["completed_stages"] == ["research", "proposal"]
    assert j["cost_cny"] == 12.5
    # was mid-flight ("running") → interrupted → failed (retryable)
    assert j["status"] == "failed"
    assert j["interrupted"] is True
    assert [e["seq"] for e in s2.get_events("j1", after_seq=-1)] == [0, 1, 2, 3]
    # seq continues after reload
    s2.push_event("j1", {"type": "x"})
    assert s2.get_events("j1", after_seq=3)[0]["seq"] == 4


def test_completed_job_not_marked_interrupted(tmp_path):
    d = tmp_path / "js"
    s1 = JobStore(persist_dir=d)
    s1.create("done", {})
    s1.update("done", status="completed")
    s2 = JobStore(persist_dir=d)
    assert s2.get("done")["status"] == "completed"
    assert s2.get("done").get("interrupted") is not True


async def test_approval_approve(store):
    store.create("j", {})
    store.update("j", status="awaiting_approval")

    async def approver():
        await asyncio.sleep(0.01)
        assert store.set_approval("j", "approve", "") is True

    asyncio.create_task(approver())
    result = await store.wait_for_approval("j", timeout=2.0)
    assert result["action"] == "approve"


async def test_approval_reject_carries_feedback(store):
    store.create("j", {})
    store.update("j", status="awaiting_approval")

    async def approver():
        await asyncio.sleep(0.01)
        store.set_approval("j", "reject", "make it punchier")

    asyncio.create_task(approver())
    result = await store.wait_for_approval("j", timeout=2.0)
    assert result["action"] == "reject"
    assert result["feedback"] == "make it punchier"


def test_set_approval_rejected_when_not_awaiting(store):
    store.create("j", {})  # status queued, not awaiting_approval
    assert store.set_approval("j", "approve", "") is False


async def test_approval_timeout_defaults_to_reject(store):
    store.create("j", {})
    store.update("j", status="awaiting_approval")
    result = await store.wait_for_approval("j", timeout=0.05)
    assert result["action"] == "reject"
