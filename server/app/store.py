"""In-memory job store for v1 (will be replaced by Postgres in M0-3)."""

from __future__ import annotations

import asyncio
import threading
from typing import Any


class JobStore:
    """Thread-safe in-memory store for job state and SSE event queues."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._events: dict[str, list[dict]] = {}
        self._approval_events: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str, data: dict) -> None:
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "current_stage": None,
                "stages": [],
                "cost_cny": 0.0,
                **data,
            }
            self._events[job_id] = []
            self._approval_events[job_id] = asyncio.Event()

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)

    def push_event(self, job_id: str, event: dict) -> None:
        with self._lock:
            if job_id in self._events:
                seq = len(self._events[job_id])
                self._events[job_id].append({"seq": seq, **event})

    def get_events(self, job_id: str, after_seq: int = -1) -> list[dict]:
        with self._lock:
            events = self._events.get(job_id, [])
            return [e for e in events if e["seq"] > after_seq]

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
