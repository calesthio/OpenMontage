"""SSE stream: regular replay, and the terminal-state synthesis fix.

Regression: a job interrupted by a server restart (marked failed by
JobStore._load_all) never had a job_failed event appended to its persisted
log — its last real event stayed whatever it was mid-flight (e.g.
awaiting_approval). A (re)connecting client would drain history, see the
stream close with no terminal event, and — per page.tsx's onerror handler —
reconnect forever, stuck showing the stale "awaiting_approval" state with no
visible next action. The fix: synthesize a terminal event whenever a client
(re)connects to a job that is already terminal but has no new events to drain.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.routers import events
from app.store import JobStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    ts = JobStore(persist_dir=tmp_path / "js")
    monkeypatch.setattr(events, "job_store", ts)
    return TestClient(main.app), ts


def _read_events(resp):
    out = []
    for line in resp.iter_lines():
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: "):]))
    return out


def test_normal_replay_ends_on_real_terminal_event(client):
    c, ts = client
    ts.create("j1", {})
    ts.push_event("j1", {"type": "stage_started", "stage": "research"})
    ts.push_event("j1", {"type": "job_completed", "render_url": "/media/j1/renders/final.mp4"})
    ts.update("j1", status="completed", render_url="/media/j1/renders/final.mp4")

    with c.stream("GET", "/jobs/j1/events") as resp:
        evs = _read_events(resp)
    assert [e["type"] for e in evs] == ["stage_started", "job_completed"]
    assert evs[-1]["render_url"] == "/media/j1/renders/final.mp4"


def test_interrupted_job_synthesizes_job_failed(client):
    c, ts = client
    ts.create("j2", {})
    # Simulate what _load_all does on restart: last REAL event is still
    # awaiting_approval, but status was flipped to failed+interrupted with no
    # corresponding event ever appended.
    ts.push_event("j2", {"type": "stage_started", "stage": "script"})
    ts.push_event("j2", {"type": "awaiting_approval", "stage": "script"})
    ts.update("j2", status="failed", interrupted=True)

    with c.stream("GET", "/jobs/j2/events") as resp:
        evs = _read_events(resp)

    assert [e["type"] for e in evs] == ["stage_started", "awaiting_approval", "job_failed"]
    assert "interrupted" in evs[-1]["message"].lower()


def test_reconnect_past_all_history_still_gets_synthesized_terminal(client):
    c, ts = client
    ts.create("j3", {})
    ts.push_event("j3", {"type": "awaiting_approval", "stage": "proposal"})
    ts.update("j3", status="failed", interrupted=True)

    # Client already has every real event (lastEventId=0, the only pushed one).
    with c.stream("GET", "/jobs/j3/events?lastEventId=0") as resp:
        evs = _read_events(resp)
    assert [e["type"] for e in evs] == ["job_failed"]


def test_completed_job_with_stale_last_event_synthesizes_job_completed(client):
    c, ts = client
    ts.create("j4", {})
    ts.push_event("j4", {"type": "stage_completed", "stage": "compose"})
    ts.update("j4", status="completed", render_url="/media/j4/renders/final.mp4")

    with c.stream("GET", "/jobs/j4/events") as resp:
        evs = _read_events(resp)
    assert evs[-1]["type"] == "job_completed"
    assert evs[-1]["render_url"] == "/media/j4/renders/final.mp4"


def test_old_terminal_event_mid_history_does_not_truncate_the_replay(client):
    # Found live: a job failed once (job_failed persisted at some seq), was
    # later retried, and genuinely succeeded — appending MANY more events
    # including a real job_completed further down the log. The old code
    # returned as soon as it saw ANY job_completed/job_failed while iterating
    # a batch, so a full replay (or any reconnect) stopped dead at the FIRST
    # (old, superseded) job_failed and never delivered the retry's real
    # outcome — the client stayed stuck reporting the stale old failure
    # forever. A full replay must deliver every event and only stop at the
    # LAST one, which is the real, current outcome.
    c, ts = client
    ts.create("j5", {})
    ts.push_event("j5", {"type": "stage_started", "stage": "edit"})
    ts.push_event("j5", {"type": "job_failed", "stage": "edit", "message": "old failure"})
    ts.push_event("j5", {"type": "job_started", "resumed": True})
    ts.push_event("j5", {"type": "stage_skipped", "stage": "edit"})
    ts.push_event("j5", {"type": "stage_completed", "stage": "compose"})
    ts.push_event("j5", {"type": "job_completed", "render_url": "/media/j5/renders/final.mp4"})
    ts.update("j5", status="completed", render_url="/media/j5/renders/final.mp4")

    with c.stream("GET", "/jobs/j5/events") as resp:
        evs = _read_events(resp)

    types = [e["type"] for e in evs]
    assert types == [
        "stage_started", "job_failed", "job_started", "stage_skipped",
        "stage_completed", "job_completed",
    ]
    # The stream delivered ALL of it, including past the old job_failed, and
    # stopped only at the real (last) terminal event — not synthesized again.
    assert evs[-1]["render_url"] == "/media/j5/renders/final.mp4"
    assert len(evs) == 6


def test_cancelled_job_stream_does_not_append_spurious_job_failed(client):
    # Regression (audit 2026-07-15, BUG-4): "cancelled" entered
    # TERMINAL_STATUSES but the terminal-event tuples here only listed
    # job_completed/job_failed, so after the real job_cancelled was delivered
    # the next empty drain synthesized a job_failed on top of it — the UI
    # flipped 已取消 → 失败 and rendered a retry button whose POST then 400s.
    c, ts = client
    ts.create("j6", {})
    ts.push_event("j6", {"type": "job_started"})
    ts.update("j6", status="cancelled")
    ts.push_event("j6", {"type": "job_cancelled"})

    with c.stream("GET", "/jobs/j6/events") as resp:
        evs = _read_events(resp)
    assert [e["type"] for e in evs] == ["job_started", "job_cancelled"]


def test_cancelled_job_with_stale_last_event_synthesizes_job_cancelled(client):
    # The synthetic branch must map status="cancelled" to job_cancelled,
    # never job_failed.
    c, ts = client
    ts.create("j7", {})
    ts.push_event("j7", {"type": "stage_started", "stage": "script"})
    ts.update("j7", status="cancelled")

    with c.stream("GET", "/jobs/j7/events") as resp:
        evs = _read_events(resp)
    assert evs[-1]["type"] == "job_cancelled"


def test_synthesized_terminal_event_does_not_collide_with_retry_seq(client):
    # Regression (audit 2026-07-15, BUG-5): the old stream-local synthetic
    # minted seq=max+1 WITHOUT storing it, so the next real event pushed after
    # a retry reused the exact same seq — a client resuming with
    # lastEventId=<synthetic seq> silently skipped the retry's job_started
    # (the event that carries the pipeline's stage list). The terminal event
    # is now stored through push_event, so it owns its seq.
    c, ts = client
    ts.create("j8", {})
    ts.push_event("j8", {"type": "awaiting_approval", "stage": "script"})
    ts.update("j8", status="failed", interrupted=True)

    with c.stream("GET", "/jobs/j8/events") as resp:
        evs = _read_events(resp)
    assert evs[-1]["type"] == "job_failed"
    synthetic_seq = evs[-1]["seq"]

    # Retry: status back to queued, runner pushes job_started.
    ts.update("j8", status="queued")
    ts.push_event("j8", {"type": "job_started", "stages": ["script", "compose"]})
    ts.update("j8", status="running")

    # Resume from the synthesized terminal event's id — the retry's
    # job_started must NOT be skipped.
    assert [e["type"] for e in ts.get_events("j8", after_seq=synthetic_seq)] == ["job_started"]


def test_ensure_terminal_event_is_idempotent(client):
    # Two SSE generators racing on the same terminal job must not append two
    # terminal events.
    _c, ts = client
    ts.create("j9", {})
    ts.push_event("j9", {"type": "stage_started", "stage": "script"})
    ts.update("j9", status="failed")
    ts.ensure_terminal_event("j9")
    ts.ensure_terminal_event("j9")
    types = [e["type"] for e in ts.get_events("j9")]
    assert types == ["stage_started", "job_failed"]


def test_unknown_job_returns_404_instead_of_an_empty_stream(client):
    # Regression: this endpoint used to open a 200 empty SSE stream for a
    # nonexistent job_id, inconsistent with GET /jobs/{id} which 404s for the
    # same case.
    c, _ts = client
    with c.stream("GET", "/jobs/does-not-exist/events") as resp:
        evs = _read_events(resp)
    assert resp.status_code == 404
    assert evs == []
