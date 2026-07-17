"""JobStore: CRUD, event ring + bisect, durable persistence, approval gate."""

from __future__ import annotations

import asyncio
import json

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


def test_persist_job_failure_is_logged_not_swallowed(tmp_path, caplog):
    # Regression: _persist_job used to catch OSError and do nothing, so a
    # disk failure here was completely invisible.
    s = JobStore(persist_dir=tmp_path / "js")
    s.create("j", {})
    s._persist_dir = tmp_path / "does-not-exist"   # forces write_text to raise
    caplog.clear()
    with caplog.at_level("WARNING"):
        s.update("j", status="running")
    assert any("j" in r.getMessage() and "persist" in r.getMessage().lower()
               for r in caplog.records)


def test_append_event_failure_is_logged_not_swallowed(tmp_path, caplog):
    # Regression: _append_event_to_disk used to catch OSError and do nothing.
    s = JobStore(persist_dir=tmp_path / "js")
    s.create("j", {})
    s._persist_dir = tmp_path / "does-not-exist"   # forces the append to raise
    caplog.clear()
    with caplog.at_level("WARNING"):
        s.push_event("j", {"type": "x"})
    assert any("j" in r.getMessage() and "event" in r.getMessage().lower()
               for r in caplog.records)


async def test_writes_are_offloaded_but_still_land_when_a_loop_is_running(tmp_path):
    # create()/update()/push_event() used to always write synchronously,
    # blocking whatever event loop called them (every route handler and the
    # pipeline runner). This test runs with a real running loop, so the
    # actual disk write is now handed to a background thread instead — give
    # it a moment to land, then confirm it did.
    s = JobStore(persist_dir=tmp_path / "js")
    s.create("j", {"project_name": "demo"})
    s.update("j", status="running")
    s.push_event("j", {"type": "x"})
    await asyncio.sleep(0.2)
    assert json.loads((tmp_path / "js" / "j.json").read_text())["status"] == "running"
    assert len((tmp_path / "js" / "j.events.jsonl").read_text().splitlines()) == 1


def test_reset_events_log_truncates_disk_file_but_keeps_job(tmp_path):
    # Regression: create() truncates events.jsonl once, but nothing reset it
    # on retry, so every retry kept appending to the SAME on-disk file from
    # the very first attempt onward with no cap.
    d = tmp_path / "js"
    s = JobStore(persist_dir=d)
    s.create("j", {})
    s.push_event("j", {"type": "a"})
    s.push_event("j", {"type": "b"})
    events_path = d / "j.events.jsonl"
    assert len(events_path.read_text().splitlines()) == 2

    s.reset_events_log("j")
    assert events_path.read_text() == ""
    # the job record itself is untouched
    assert s.get("j") is not None


def test_terminal_statuses_include_cancelled():
    # Regression: "cancelled" is a new terminal status (added alongside the
    # cancel endpoint) — anywhere completed/failed are checked together as
    # terminal must recognize it too.
    from app.store import TERMINAL_STATUSES
    assert TERMINAL_STATUSES == {"completed", "failed", "cancelled"}


def test_delete_removes_job_and_persisted_files(tmp_path):
    d = tmp_path / "js"
    s = JobStore(persist_dir=d)
    s.create("j", {})
    s.push_event("j", {"type": "x"})
    assert (d / "j.json").exists()
    assert (d / "j.events.jsonl").exists()

    assert s.delete("j") is True
    assert s.get("j") is None
    assert s.get_events("j", after_seq=-1) == []
    assert not (d / "j.json").exists()
    assert not (d / "j.events.jsonl").exists()

    assert s.delete("missing") is False


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


async def test_approval_timeout_reports_timeout_not_reject(store):
    # Roadmap 0.2: a timeout is no longer fabricated into a reject — the
    # runner's ladder (stage_runner._wait_for_decision) owns what a timeout
    # means (remind → keep waiting → expire loudly).
    store.create("j", {})
    store.update("j", status="awaiting_approval")
    result = await store.wait_for_approval("j", timeout=0.05)
    assert result["action"] == "timeout"


async def test_set_approval_second_racing_call_does_not_clobber_first(store):
    # Regression: set_approval used to read status and write the result
    # without a lock spanning both -- two near-simultaneous approve calls
    # could both observe status=="awaiting_approval" (it doesn't flip until
    # wait_for_approval's caller advances the pipeline, well after this
    # returns), so the second write would silently clobber the first's
    # decision before wait_for_approval ever consumed it.
    store.create("j", {})
    store.update("j", status="awaiting_approval")

    assert store.set_approval("j", "approve", "first") is True
    # Second call arrives before wait_for_approval has consumed the first
    # result -- status is still "awaiting_approval", but must be rejected,
    # not silently accepted and overwrite the pending decision.
    assert store.set_approval("j", "reject", "second") is False

    result = await store.wait_for_approval("j", timeout=1.0)
    assert result == {"action": "approve", "feedback": "first"}


async def test_set_approval_allows_a_new_decision_after_the_first_is_consumed(store):
    # Once wait_for_approval consumes a decision, a fresh approval cycle
    # (e.g. after the pipeline re-enters awaiting_approval for the next
    # gated stage) must be accepted again -- the "already resolved" guard is
    # per-pending-result, not a permanent lockout for the job.
    store.create("j", {})
    store.update("j", status="awaiting_approval")
    assert store.set_approval("j", "approve", "first") is True
    await store.wait_for_approval("j", timeout=1.0)

    store.update("j", status="awaiting_approval")
    assert store.set_approval("j", "reject", "second") is True
    result = await store.wait_for_approval("j", timeout=1.0)
    assert result == {"action": "reject", "feedback": "second"}
