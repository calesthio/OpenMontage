"""SSE event stream: GET /jobs/{id}/events"""

import asyncio
import json
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.store import job_store, TERMINAL_STATUSES

router = APIRouter()


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
        while True:
            events = job_store.get_events(job_id, after_seq=seq)
            for ev in events:
                seq = ev["seq"]
                last_type = ev.get("type")
                data = json.dumps(ev, ensure_ascii=False)
                yield f"id: {seq}\ndata: {data}\n\n"
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
                    if last_type in ("job_completed", "job_failed"):
                        return   # already ended on a real terminal event
                    # The persisted event log may predate the terminal state —
                    # e.g. a job interrupted by a server restart mid-flight is
                    # marked failed without a job_failed event ever being
                    # appended (store._load_all has no live SSE client to push
                    # to at startup time). Without this, a (re)connecting client
                    # sees the stream close with no terminal event, its local
                    # `status` stays stuck at the last real event (e.g.
                    # "awaiting_approval"), and it reconnects forever. Synthesize
                    # the terminal event here so every client — live or
                    # reconnecting — always observes one.
                    seq += 1
                    ev_type = "job_completed" if job["status"] == "completed" else "job_failed"
                    synthetic = {
                        "seq": seq,
                        "type": ev_type,
                        "ts": time.time(),
                        "render_url": job.get("render_url"),
                        # Only present on a multi-variant (A/B) job — mirrors
                        # the real job_completed/preview_ready events emitted
                        # by stage_runner.py, so a client resuming mid-flight
                        # (or after a server restart) sees the same shape a
                        # live client would have.
                        **({"render_urls": job["render_urls"]} if job.get("render_urls") else {}),
                        "message": "Job was interrupted (e.g. a server restart) before completion" if job.get("interrupted") else None,
                    }
                    yield f"id: {seq}\ndata: {json.dumps(synthetic, ensure_ascii=False)}\n\n"
                    return
            elif last_type in ("job_completed", "job_failed"):
                # The batch we just delivered genuinely ends on a real
                # terminal event (not an old one buried mid-batch) — done.
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
