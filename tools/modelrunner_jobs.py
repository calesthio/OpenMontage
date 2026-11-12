"""Run, collect, and account for one ModelRunner job — shared by the four tools.

Billing contract every ModelRunner tool reports through this module:

- `cost_usd` is what THIS call caused to be spent. After a delivered result it
  is the charge read back from the account's request record
  (`GET /requests/{id}` -> totalPrice), falling back to the estimate only when
  the record cannot be read. `None` means the charge is unknown: a job was (or
  may have been) accepted and its outcome could not be verified. Never 0.0 for
  an accepted job unless the record says it was not billed.
- `data["billing_status"]`: not_submitted | not_collected | unknown |
  possibly_billed | pending | partial | charged | failed.
- `data["resubmit_safe"]` is False whenever a job may exist (a `failed` job
  is settled and unbilled, so a new submit is safe). Recover a
  submitted job with a collect call (`request_id`, or `status_url` /
  `response_url`), which only reads and never submits.
- A collect call reports `cost_usd=0.0` — it spends nothing — and puts the
  job's own charge in `data["billing"]`, so a job is never counted twice.
- Every submission is checkpointed to a job file (`job_path`, default
  `<output_path>.job.json`): the attempt id before the POST, the request id
  and queue URLs once accepted. A process that dies mid-poll still leaves
  what a collect call needs.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools import modelrunner_client
from tools.base_tool import ToolResult
from tools.provider_jobs import save_job

COLLECT_KEYS = ("request_id", "status_url", "response_url")

COLLECT_SCHEMA_PROPERTIES = {
    "request_id": {
        "type": "string",
        "description": "Collect an already-submitted ModelRunner job by id. Polls and downloads only; makes no new (paid) submission.",
    },
    "status_url": {"type": "string", "description": "Collect an already-submitted job by its status_url (no new submission)."},
    "response_url": {"type": "string", "description": "Collect an already-submitted job by its response_url (no new submission)."},
    "job_path": {
        "type": "string",
        "description": "Where to checkpoint the submitted job (attempt id, request_id, queue URLs). Default: <output_path>.job.json.",
    },
}


def is_collect(inputs: dict[str, Any]) -> bool:
    return any(inputs.get(key) for key in COLLECT_KEYS)


def collect_coordinates(inputs: dict[str, Any], endpoint_id: str) -> dict[str, Any]:
    """Queue coordinates for a collect call. Pure: no network, no submission."""
    status_url = inputs.get("status_url")
    response_url = inputs.get("response_url")
    request_id = inputs.get("request_id")
    if status_url or response_url:
        for url, label in ((status_url, "status_url"), (response_url, "response_url")):
            if url:
                modelrunner_client._assert_api_url(str(url), label)
        if not response_url:
            response_url = str(status_url).removesuffix("/status")
        if not status_url:
            status_url = f"{response_url}/status"
        if not request_id:
            request_id = str(response_url).rstrip("/").rsplit("/", 1)[-1]
        coords = modelrunner_client.queue_urls_for(endpoint_id, str(request_id))
        coords.update(status_url=str(status_url), response_url=str(response_url))
        return coords
    return modelrunner_client.queue_urls_for(endpoint_id, str(request_id))


def submit(
    tool: str, endpoint_id: str, payload: dict[str, Any], api_key: str,
    inputs: dict[str, Any], default_output: str, estimate: float,
) -> dict[str, Any]:
    """Submit one paid job, checkpointing it to disk before and after the POST.

    The attempt id is written BEFORE anything is sent — an unwritable job path
    fails here, unbilled — so a crash at any later point leaves either the
    attempt id (find the job by its `openmontage_attempt` metadata) or the
    request id and queue URLs (collect it).
    """
    path = Path(inputs.get("job_path") or f"{inputs.get('output_path') or default_output}.job.json")
    attempt_id = modelrunner_client.new_attempt_id()
    job = {
        "tool": tool, "provider": "modelrunner", "endpoint": endpoint_id,
        "attempt_id": attempt_id, "state": "submitting",
        "estimated_cost_usd": round(estimate, 6),
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    save_job(path, job)

    def checkpoint(update: dict[str, Any]) -> None:
        try:
            save_job(path, {**job, **update})
        except OSError:
            pass  # the coordinates are also in the ToolResult; never mask the job

    try:
        queue = modelrunner_client.submit(endpoint_id, payload, api_key, attempt_id=attempt_id)
    except Exception as exc:
        known = getattr(exc, "queue", None)
        if known:
            known["job_path"] = str(path)
            checkpoint({**known, "state": "unknown"})
        else:
            checkpoint({"state": "not_submitted", "error": str(exc)[:500]})
        raise
    checkpoint({**queue, "state": "accepted"})
    return {**queue, "job_path": str(path)}


def fetch_outputs(
    queue: dict[str, Any], api_key: str, *, interval: float, timeout: float, cardinality: str
) -> list[str]:
    """Wait for an accepted job and return its validated output URLs."""
    modelrunner_client.poll(queue["status_url"], api_key, interval=interval, timeout=timeout)
    result = modelrunner_client.get_result(queue["response_url"], api_key)
    return modelrunner_client.extract_outputs(result, cardinality)


def settle(queue: dict[str, Any], api_key: str, estimate: float, *, collected: bool) -> tuple[float | None, dict[str, Any]]:
    """(cost_usd, billing dict) for a delivered job, read from its request record."""
    record = modelrunner_client.get_request_record(queue.get("request_id", ""), api_key)
    status = record["billing_status"]
    charged = record["total_price"]
    if status in ("charged", "partial") and charged is not None:
        cost, source = charged, "modelrunner_request_record"
    elif status == "failed":
        cost, source = 0.0, "modelrunner_request_record"
    else:
        cost, source = round(estimate, 6), "estimate"
    billing = {
        "status": status or "unknown",
        "charged_usd": charged if status in ("charged", "partial") else None,
        "estimated_usd": round(estimate, 6),
        "source": source,
    }
    return (0.0 if collected else cost), billing


def _saved_in(known: dict[str, Any]) -> str:
    path = known.get("job_path")
    return f" These coordinates are saved in {path}." if path else ""


def failure(
    label: str,
    exc: Exception,
    queue: dict[str, Any],
    started: float,
    estimate: float,
    api_key: str | None,
    *,
    collected: bool = False,
) -> ToolResult:
    """Failed result with honest billing provenance (see the module docstring)."""
    known = {**getattr(exc, "queue", {}), **queue}
    data: dict[str, Any]
    cost: float | None
    if not known and collected:
        # A collect call names a job that exists; failing before reaching it
        # never makes a resubmit safe.
        data, cost = {
            "billing_status": "not_collected",
            "resubmit_safe": False,
            "recovery_hint": "This call collects an existing job. Fix the collect inputs and retry; do not resubmit.",
        }, None
    elif not known:
        data, cost = {"billing_status": "not_submitted", "resubmit_safe": True}, 0.0
    elif known.get("submit_outcome") == "ambiguous":
        data = {
            **known,
            "billing_status": "unknown",
            "resubmit_safe": False,
            "estimated_usd": round(estimate, 6),
            "recovery_hint": (
                "The submit got no definite answer, so the job may exist and bill. "
                "Look it up in your ModelRunner request history by metadata "
                f"{modelrunner_client.ATTEMPT_METADATA_KEY}={known.get('attempt_id')} "
                "(GET /requests?metadata=...) and collect it by request_id before resubmitting."
                + _saved_in(known)
            ),
        }
        cost = None
    else:
        record = (
            modelrunner_client.get_request_record(known.get("request_id", ""), api_key)
            if api_key else {"billing_status": None, "total_price": None}
        )
        status = record["billing_status"]
        if status == "failed":
            billing_status, cost = "failed", 0.0
        elif status in ("charged", "partial") and record["total_price"] is not None:
            billing_status, cost = status, record["total_price"]
        else:
            billing_status, cost = "possibly_billed", None
        data = {**known, "billing_status": billing_status, "estimated_usd": round(estimate, 6)}
        if billing_status == "failed":
            # Settled and unbilled: the job is over, so a new submit is a new job.
            data["resubmit_safe"] = True
        else:
            data["resubmit_safe"] = False
            data["recovery_hint"] = (
                "The job was accepted. Re-run this tool with request_id="
                f"{known.get('request_id')} to collect it; that polls and downloads "
                "without a new paid submission." + _saved_in(known)
            )
    if collected:
        data["billing"] = {"status": data["billing_status"], "charged_usd": cost}
        cost = 0.0
    return ToolResult(
        success=False,
        error=f"ModelRunner {label} failed: {exc}",
        data=data,
        cost_usd=cost,
        duration_seconds=round(time.time() - started, 2),
    )
