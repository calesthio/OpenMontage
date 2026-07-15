"""SSE event stream: GET /jobs/{id}/events"""

import asyncio
import json
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.store import job_store, TERMINAL_STATUSES

router = APIRouter()

# How often to emit an SSE keep-alive comment during silent stretches (a long
# pipeline stage with no events to push). Without this, a reverse proxy or
# load balancer's idle-connection timeout can drop the connection during a
# quiet stage even though the job itself is still healthy.
_HEARTBEAT_INTERVAL = 15.0


@router.get("/{job_id}/events")
async def job_events(job_id: str, lastEventId: int = -1):
    # GET /jobs/{id} 404s for an unknown job; this endpoint silently opened an
    # empty 200 stream for the same case instead — check up front so the two
    # stay consistent for a client that doesn't yet know whether job_id is real.
    if job_store.get(job_id) is None:
        raise HTTPException(404, "Job not found")

    async def generator():
        seq = lastEventId
        last_type = None
        last_activity = time.time()
        while True:
            events = job_store.get_events(job_id, after_seq=seq)
            for ev in events:
                seq = ev["seq"]
                last_type = ev.get("type")
                data = json.dumps(ev, ensure_ascii=False)
                yield f"id: {seq}\ndata: {data}\n\n"
            if events:
                last_activity = time.time()
            # Only decide to close AFTER draining the whole batch just
            # fetched — never mid-batch. A full replay (or any reconnect
            # spanning more than one retry cycle) can contain an OLD
            # job_failed/job_completed from an earlier, since-superseded
            # attempt followed by MANY more events from a later retry that
            # actually finished differently (even a real job_completed).
            # Returning as soon as any terminal-type event was seen — instead
            # of only the LAST one in the batch — silently truncated the
            # replay right at that old event, so a client resuming from
            # scratch (or reconnecting after a gap) never saw the job's real,
            # later outcome and kept reconnecting/misreporting forever.
            if not events:
                # Nothing new this tick: if the job is already terminal we've
                # drained everything, so close instead of looping forever (a
                # reconnect after completion would otherwise leak a
                # connection). No second query — an empty drain IS the
                # "caught up" signal.
                job = job_store.get(job_id)
                if job is None:
                    return
                if job.get("status") in TERMINAL_STATUSES:
                    if last_type in job_store.TERMINAL_EVENT_TYPES:
                        return   # already ended on a real terminal event
                    # The persisted event log may predate the terminal state —
                    # e.g. a job interrupted by a server restart mid-flight is
                    # marked failed without a job_failed event ever being
                    # appended (store._load_all has no live SSE client to push
                    # to at startup time). Without this, a (re)connecting client
                    # sees the stream close with no terminal event, its local
                    # `status` stays stuck at the last real event (e.g.
                    # "awaiting_approval"), and it reconnects forever. Ask the
                    # store to append the missing terminal event as a REAL,
                    # seq-numbered event (idempotent), then drain it like any
                    # other — a stream-local synthetic with an invented seq
                    # collided with the next real event after a retry, making
                    # resuming clients skip it.
                    job_store.ensure_terminal_event(job_id)
                    if not job_store.get_events(job_id, after_seq=seq):
                        # Nothing more will ever arrive for a terminal job
                        # (e.g. this client's lastEventId is already past the
                        # end of the log) — close instead of looping.
                        return
                    continue
            elif last_type in job_store.TERMINAL_EVENT_TYPES:
                # The batch we just delivered genuinely ends on a real
                # terminal event (not an old one buried mid-batch) — done.
                return
            # No new events this tick and the job is still in flight: a long
            # silent stage (no stage_started/progress events for minutes)
            # would otherwise leave the connection producing nothing at all,
            # risking an idle-timeout disconnect behind a reverse proxy. An
            # SSE comment line (leading ":") is invisible to EventSource's
            # onmessage but keeps the socket demonstrably alive.
            now = time.time()
            if now - last_activity >= _HEARTBEAT_INTERVAL:
                last_activity = now
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
