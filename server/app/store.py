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
import json
import threading
import time
from pathlib import Path
from typing import Any

# Cap the retained per-job in-memory event ring so a long-running job can't grow
# the buffer without bound. Reconnecting clients still get recent events; the
# full history remains on disk in the JSONL log.
MAX_EVENTS_PER_JOB = 5000

TERMINAL_STATUSES = {"completed", "failed"}
_INFLIGHT_STATUSES = {"queued", "running", "awaiting_approval"}

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
        self._load_all()

    # ---- Persistence helpers ----

    def _job_path(self, job_id: str) -> Path:
        return self._persist_dir / f"{job_id}.json"

    def _events_path(self, job_id: str) -> Path:
        return self._persist_dir / f"{job_id}.events.jsonl"

    def _persist_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        path = self._job_path(job_id)
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2))
            tmp.replace(path)   # atomic on POSIX
        except OSError:
            pass  # persistence is best-effort; never crash a job over disk I/O

    def _append_event_to_disk(self, job_id: str, event: dict) -> None:
        try:
            with open(self._events_path(job_id), "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
            pass

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
            if job.get("status") in _INFLIGHT_STATUSES:
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
            try:
                self._events_path(job_id).write_text("")
            except OSError:
                pass
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
        job = self.get(job_id)
        if not job or job.get("status") != "awaiting_approval":
            return False
        with self._lock:
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
