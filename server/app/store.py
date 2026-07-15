"""Durable job store for v1.

Filesystem-first (no DB): job records are written through to
projects/.jobstore/<job_id>.json and events to an append-only
<job_id>.events.jsonl. On startup the store rehydrates from disk so a server
restart no longer wipes jobs — the retry endpoint keeps working and in-flight
jobs that were interrupted by the restart are surfaced as failed+retryable.
"""

from __future__ import annotations

import asyncio
import bisect
import concurrent.futures
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Cap the retained per-job in-memory event ring so a long-running job can't grow
# the buffer without bound. Reconnecting clients still get recent events; the
# full history remains on disk in the JSONL log.
MAX_EVENTS_PER_JOB = 5000

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
# Public (no leading underscore): reused by routers/jobs.py to detect an
# in-flight job sharing a project_name with a new job request (see
# create_job's uniqueness check).
INFLIGHT_STATUSES = {"queued", "running", "awaiting_approval"}

# Repo-root .jobstore/ — deliberately NOT under projects/, which is exposed via
# the /media StaticFiles mount (persisting job records there would leak
# brand_info/options/cost over HTTP).
_PERSIST_DIR = Path(__file__).resolve().parent.parent.parent / ".jobstore"


class JobStore:
    """Thread-safe, disk-backed store for job state and SSE event queues."""

    def __init__(self, persist_dir: Path | None = None):
        self._jobs: dict[str, dict] = {}
        self._events: dict[str, list[dict]] = {}
        self._event_seq: dict[str, int] = {}
        self._approval_events: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._persist_dir = persist_dir or _PERSIST_DIR
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        # Disk writes triggered from create()/update()/push_event() would
        # otherwise block whatever event loop called them (every route handler
        # and the pipeline runner are async). A single worker keeps writes to
        # the same job's files in submission order — the actual write only
        # ever runs here when a loop is running (see _run_io); outside a loop
        # (direct/script/test usage) there's nothing to block, so it runs
        # inline and stays exactly as durable as before.
        self._io_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="jobstore-io"
        )
        self._load_all()

    # ---- Persistence helpers ----

    def _job_path(self, job_id: str) -> Path:
        return self._persist_dir / f"{job_id}.json"

    def _events_path(self, job_id: str) -> Path:
        return self._persist_dir / f"{job_id}.events.jsonl"

    def _run_io(self, fn, *args: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            fn(*args)
        else:
            loop.run_in_executor(self._io_executor, fn, *args)

    def _write_job_file(self, job_id: str, payload: str) -> None:
        path = self._job_path(job_id)
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(payload)
            tmp.replace(path)   # atomic on POSIX
        except OSError:
            # Persistence is best-effort; never crash a job over disk I/O —
            # but a silent failure here is exactly why a restart previously
            # lost jobs mid-flight, so at least make it discoverable.
            logger.warning("Failed to persist job %s to %s", job_id, path, exc_info=True)

    def _persist_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        payload = json.dumps(job, ensure_ascii=False, indent=2)
        self._run_io(self._write_job_file, job_id, payload)

    def _write_event_line(self, job_id: str, line: str) -> None:
        path = self._events_path(job_id)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            logger.warning("Failed to append event for job %s to %s", job_id, path, exc_info=True)

    def _append_event_to_disk(self, job_id: str, event: dict) -> None:
        line = json.dumps(event, ensure_ascii=False) + "\n"
        self._run_io(self._write_event_line, job_id, line)

    def _truncate_events_file(self, job_id: str) -> None:
        path = self._events_path(job_id)
        try:
            path.write_text("")
        except OSError:
            logger.warning("Failed to reset events log for job %s at %s", job_id, path, exc_info=True)

    def reset_events_log(self, job_id: str) -> None:
        """Truncate a job's on-disk events.jsonl so a fresh run starts clean.

        Used by create() below and by routers/jobs.py's retry_job — a retry
        is semantically a new run, so without this every retry kept
        appending to the SAME on-disk file from the very first attempt
        onward with no cap (only the in-memory ring buffer is capped).
        """
        self._run_io(self._truncate_events_file, job_id)

    def _load_all(self) -> None:
        for job_file in sorted(self._persist_dir.glob("*.json")):
            if job_file.name.endswith(".json.tmp"):
                continue
            try:
                job = json.loads(job_file.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            job_id = job.get("job_id") or job_file.stem
            # A job left mid-flight when the process died is orphaned — no worker
            # is driving it anymore. Mark it failed so the UI offers retry (which
            # resumes from completed_stages).
            if job.get("status") in INFLIGHT_STATUSES:
                job["status"] = "failed"
                job["interrupted"] = True
            self._jobs[job_id] = job

            events: list[dict] = []
            ev_path = self._events_path(job_id)
            if ev_path.exists():
                try:
                    for line in ev_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line:
                            events.append(json.loads(line))
                except (OSError, json.JSONDecodeError):
                    events = []
            max_seq = max((e.get("seq", -1) for e in events), default=-1)
            self._events[job_id] = events[-MAX_EVENTS_PER_JOB:]
            self._event_seq[job_id] = max_seq + 1
            self._approval_events[job_id] = asyncio.Event()
            if job.get("interrupted"):
                self._persist_job(job_id)

    # ---- Job CRUD ----

    def create(self, job_id: str, data: dict) -> None:
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "current_stage": None,
                "stages": [],
                "completed_stages": [],
                "cost_cny": 0.0,
                "created_at": time.time(),
                **data,
            }
            self._events[job_id] = []
            self._event_seq[job_id] = 0
            self._approval_events[job_id] = asyncio.Event()
            # Start a fresh events log for this job.
            self.reset_events_log(job_id)
            self._persist_job(job_id)

    def all(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._jobs)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)
                self._persist_job(job_id)

    def delete(self, job_id: str) -> bool:
        """Remove a job's in-memory state and its persisted files. Returns
        False if the job doesn't exist so callers can 404 without a redundant
        get() first."""
        with self._lock:
            if job_id not in self._jobs:
                return False
            del self._jobs[job_id]
            self._events.pop(job_id, None)
            self._event_seq.pop(job_id, None)
            self._approval_events.pop(job_id, None)
            self._approval_results.pop(job_id, None)
        for path in (self._job_path(job_id), self._events_path(job_id)):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to remove persisted file %s for job %s", path, job_id, exc_info=True)
        return True

    # ---- Events ----

    def push_event(self, job_id: str, event: dict) -> None:
        with self._lock:
            if job_id not in self._events:
                return
            seq = self._event_seq.get(job_id, 0)
            self._event_seq[job_id] = seq + 1
            stored = {"seq": seq, **event}
            buf = self._events[job_id]
            buf.append(stored)
            if len(buf) > MAX_EVENTS_PER_JOB:
                del buf[: len(buf) - MAX_EVENTS_PER_JOB]
            self._append_event_to_disk(job_id, stored)

    # Event types that legitimately end a job's stream. Kept here (next to the
    # status set) so routers/events.py and ensure_terminal_event can't drift
    # apart on what counts as terminal — the cancelled case was exactly such a
    # drift: "cancelled" entered TERMINAL_STATUSES but the SSE endpoint's
    # terminal-event tuple never learned about job_cancelled, so every
    # cancellation was followed by a spurious synthetic job_failed.
    TERMINAL_EVENT_TYPES = ("job_completed", "job_failed", "job_cancelled")
    _TERMINAL_EVENT_BY_STATUS = {
        "completed": "job_completed",
        "failed": "job_failed",
        "cancelled": "job_cancelled",
    }

    def ensure_terminal_event(self, job_id: str) -> None:
        """Append the missing terminal event for a job already in a terminal status.

        A job interrupted by a server restart is marked failed by _load_all
        without a job_failed event ever being pushed (no live SSE client
        exists at startup). Appending the terminal event HERE — as a real,
        stored, seq-numbered event — instead of synthesizing one inside each
        SSE generator keeps sequence numbers authoritative: the old
        stream-local synthetic minted seq=max+1 without storing it, so the
        next real event after a retry reused the same seq and a client
        resuming from the synthetic id silently skipped it (job_started,
        which carries the stage list, was the usual casualty).

        Idempotent under the store lock: no-op when the log already ends on a
        terminal event, and concurrent SSE generators can't both append one.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.get("status") not in TERMINAL_STATUSES:
                return
            events = self._events.get(job_id, [])
            if events and events[-1].get("type") in self.TERMINAL_EVENT_TYPES:
                return
            self.push_event(job_id, {
                "type": self._TERMINAL_EVENT_BY_STATUS[job["status"]],
                "ts": time.time(),
                "render_url": job.get("render_url"),
                # Only present on a multi-variant (A/B) job — mirrors the real
                # job_completed/preview_ready events emitted by stage_runner.py.
                **({"render_urls": job["render_urls"]} if job.get("render_urls") else {}),
                "message": (
                    "Job was interrupted (e.g. a server restart) before completion"
                    if job.get("interrupted") else None
                ),
            })

    def get_events(self, job_id: str, after_seq: int = -1) -> list[dict]:
        with self._lock:
            events = self._events.get(job_id, [])
            if not events:
                return []
            # seq is strictly ascending → binary-search the cut point instead of
            # scanning all (up to MAX_EVENTS_PER_JOB) events on every 0.5s poll.
            idx = bisect.bisect_right(events, after_seq, key=lambda e: e["seq"])
            return events[idx:]

    # ---- Approval gate ----

    def set_approval(self, job_id: str, action: str, feedback: str) -> bool:
        """Record the human's approve/reject decision for a job's approval gate.

        The status check and the result write must happen atomically under
        one lock acquisition: two near-simultaneous POST /approve calls both
        read status=="awaiting_approval" (it doesn't change until
        wait_for_approval's caller advances the pipeline, which happens well
        after this returns), so without a single lock spanning check-then-write
        both calls would pass the check and the second write would silently
        clobber the first's decision before wait_for_approval ever consumes
        it. Treating an already-pending (not yet consumed) result as
        "resolved" for any later caller makes the second of two racing calls
        return False instead of silently discarding the first action.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.get("status") != "awaiting_approval":
                return False
            if job_id in self._approval_results:
                return False
            self._approval_results[job_id] = {"action": action, "feedback": feedback}
        ev = self._approval_events.get(job_id)
        if ev:
            # Schedule event set on the loop where it was created
            try:
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(ev.set)
            except RuntimeError:
                ev.set()
        return True

    async def wait_for_approval(self, job_id: str, timeout: float = 3600.0) -> dict:
        ev = self._approval_events.get(job_id)
        if not ev:
            return {"action": "reject", "feedback": "Job not found"}
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return {"action": "reject", "feedback": "Approval timed out"}
        ev.clear()
        with self._lock:
            return self._approval_results.pop(job_id, {"action": "reject", "feedback": ""})


job_store = JobStore()
