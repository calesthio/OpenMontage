"""SSE event stream: GET /jobs/{id}/events"""

import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.store import job_store, TERMINAL_STATUSES

router = APIRouter()


@router.get("/{job_id}/events")
async def job_events(job_id: str, lastEventId: int = -1):
    async def generator():
        seq = lastEventId
        while True:
            events = job_store.get_events(job_id, after_seq=seq)
            for ev in events:
                seq = ev["seq"]
                data = json.dumps(ev, ensure_ascii=False)
                yield f"id: {seq}\ndata: {data}\n\n"
                if ev.get("type") in ("job_completed", "job_failed"):
                    return
            # Nothing new this tick: if the job is already terminal we've drained
            # everything, so close instead of looping forever (a reconnect after
            # completion would otherwise leak a connection). No second query —
            # an empty drain IS the "caught up" signal.
            if not events:
                job = job_store.get(job_id)
                if job is None or job.get("status") in TERMINAL_STATUSES:
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
