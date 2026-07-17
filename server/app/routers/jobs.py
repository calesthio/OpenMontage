"""Job API: create, query, approve pipeline jobs."""

import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.store import job_store, TERMINAL_STATUSES, INFLIGHT_STATUSES
from app.pipeline_catalog import list_manifest_names
from app.runner.stage_runner import run_pipeline_job, _resolve_stages, PIPELINE_MAP
from app.interfaces import get_job_queue

OM_ROOT = Path(__file__).parent.parent.parent.parent

router = APIRouter()

# Stage names are always simple ASCII identifiers (CINEMATIC_STAGES / every
# pipeline_defs/*.yaml stage `name:`) — never containing a path separator.
_SAFE_STAGE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def _reject_path_traversal(v: str, field: str) -> str:
    # project_name is a free-text, human-entered field (real project names in
    # this codebase are often CJK, e.g. "小兔子电视") so it can't be locked to
    # an ASCII identifier pattern the way artifact/stage names can — but it's
    # still joined unsanitized into a filesystem path in multiple places
    # (this file's save_artifact, and stage_runner.py's project_dir), so "/"
    # and ".." must be blocked outright. Confirmed live: project_name=
    # "../../outside_target" let POST /jobs/{id}/artifact write a real file
    # entirely outside the projects/ tree.
    if "/" in v or "\\" in v or ".." in v:
        raise ValueError(f"{field} must not contain '/', '\\\\', or '..'")
    return v


class CreateJobRequest(BaseModel):
    project_name: str
    content_type: str          # e.g. "marketing_film"
    pipeline: str              # e.g. "cinematic"
    brand_info: dict[str, Any]
    options: dict[str, Any] = {}

    @field_validator("project_name")
    @classmethod
    def _validate_project_name(cls, v: str) -> str:
        return _reject_path_traversal(v, "project_name")


class ApproveStageRequest(BaseModel):
    action: str               # "approve" | "reject"
    feedback: str = ""


class SaveArtifactRequest(BaseModel):
    # Either field may identify the target: `artifact_name` is the real
    # produces-name (e.g. "brief", "scene_plan") and is what the UI should
    # send; `stage` is kept for backward compatibility and resolves to that
    # stage's primary produces name (see save_artifact below). At least one
    # must be provided.
    stage: str | None = None
    artifact_name: str | None = None
    content: dict[str, Any]

    @field_validator("stage", "artifact_name")
    @classmethod
    def _validate_name(cls, v: str | None) -> str | None:
        if v is not None and not _SAFE_STAGE_NAME.match(v):
            raise ValueError(
                "must contain only letters, numbers, underscores, and hyphens"
            )
        return v


@router.post("", status_code=201)
async def create_job(req: CreateJobRequest):
    # Without this, an unknown pipeline name silently fell back to cinematic's
    # stages deep inside _resolve_stages — the job would run, just not the
    # pipeline the caller asked for, with no error until someone noticed the
    # wrong stages in the output. PIPELINE_MAP contributes aliases like
    # "marketing_film" that aren't manifest files but are still valid.
    valid_pipelines = set(list_manifest_names()) | set(PIPELINE_MAP)
    if req.pipeline not in valid_pipelines:
        raise HTTPException(400, f"Unknown pipeline: {req.pipeline!r}")
    # project_dir is keyed only by project_name (see save_artifact and
    # stage_runner.py's project_dir) — two in-flight jobs sharing the same
    # project_name would concurrently write into the same artifacts/renders/
    # directory, corrupting whichever wrote last. Reject the second one at
    # creation time instead.
    for other_id, other in job_store.all().items():
        if other.get("project_name") == req.project_name and other.get("status") in INFLIGHT_STATUSES:
            raise HTTPException(
                409,
                f"another job is already using this project name (job {other_id}, "
                f"status {other.get('status')}); pick a different name or wait for it to finish",
            )
    job_id = str(uuid.uuid4())
    job_store.create(job_id, req.model_dump())
    get_job_queue().enqueue(run_pipeline_job, job_id, req.model_dump())
    return {"job_id": job_id, "status": "queued"}


@router.get("")
async def list_jobs():
    """Return all jobs, newest first."""
    jobs = list(job_store.all().values())
    jobs.sort(key=lambda j: j.get("created_at", 0), reverse=True)
    return {"jobs": jobs}


@router.get("/{job_id}")
async def get_job(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/{job_id}/approve")
async def approve_stage(job_id: str, req: ApproveStageRequest):
    ok = job_store.set_approval(job_id, req.action, req.feedback)
    if not ok:
        # Distinguish "another request already resolved this gate" (status is
        # genuinely awaiting_approval, but JobStore.set_approval's
        # check-then-write lock lost the race to a concurrent approve call)
        # from the plain "no such job / nothing to approve" case, so a client
        # that lost a double-click race gets an honest, actionable message
        # instead of vanishing behind the same 404 as a missing job.
        job = job_store.get(job_id)
        if job and job.get("status") == "awaiting_approval":
            raise HTTPException(409, "This job's approval gate was already resolved by another request")
        raise HTTPException(404, "Job not found or not awaiting approval")
    return {"job_id": job_id, "action": req.action}


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a queued/running/awaiting_approval job. Returns 200 immediately.

    - awaiting_approval: reuses the existing reject plumbing (set_approval)
      verbatim to unblock the pipeline's wait_for_approval() call, then sets
      status to the new terminal "cancelled" status directly so the caller
      gets a deterministic answer without waiting on the background runner.
    - queued/running: only flips a cancel_requested flag; the runner
      (stage_runner.py) is responsible for noticing the flag and performing
      the actual async flip to "cancelled" — status is returned unchanged.
    - already terminal (completed/failed/cancelled): 400.
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    status = job.get("status")
    if status in TERMINAL_STATUSES:
        raise HTTPException(400, f"Job is already {status} and cannot be cancelled")
    if status == "awaiting_approval":
        ok = job_store.set_approval(job_id, "reject", "Cancelled by user")
        if not ok:
            # Lost a race with a concurrent approve/reject/cancel call that
            # already resolved this job's approval gate.
            raise HTTPException(409, "This job's approval gate was already resolved by another request")
        job_store.update(job_id, status="cancelled", cancel_requested=True)
        return {"job_id": job_id, "status": "cancelled"}
    # queued or running: the terminal flip happens asynchronously once the
    # runner notices cancel_requested.
    job_store.update(job_id, cancel_requested=True)
    return {"job_id": job_id, "status": status}


@router.post("/{job_id}/artifact")
async def save_artifact(job_id: str, req: SaveArtifactRequest):
    """Overwrite a stage artifact (used by inline edit in the UI).

    Artifacts are stored under their PRODUCES name (stage "idea" produces
    "brief" → artifacts/brief.json), which for 6 of 8 cinematic stages
    differs from the stage name. The original implementation wrote
    artifacts/<stage>.json unconditionally — the user's edit landed in an
    orphan file the pipeline never reads, the UI said "saved", and the next
    stage silently consumed the OLD data. Resolve the real artifact name
    from the pipeline's produces declarations instead.
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    stages = _resolve_stages(job.get("pipeline", "cinematic"))
    # Names the pipeline can actually read back: every stage's declared
    # produces, plus the stage name itself for stages that declare none
    # (the prompt tells the agent to fall back to the stage name there).
    valid_artifact_names: set[str] = set()
    for s in stages:
        produces = s.get("produces") or []
        valid_artifact_names.update(produces)
        if not produces:
            valid_artifact_names.add(s["name"])

    if req.artifact_name is not None:
        artifact_name = req.artifact_name
        if artifact_name not in valid_artifact_names:
            raise HTTPException(
                400, f"{artifact_name!r} is not an artifact of this job's pipeline"
            )
    elif req.stage is not None:
        # Backward-compatible path: resolve the stage's primary artifact.
        stage_def = next((s for s in stages if s["name"] == req.stage), None)
        if stage_def is None:
            raise HTTPException(400, f"{req.stage!r} is not a stage of this job's pipeline")
        produces = stage_def.get("produces") or []
        artifact_name = produces[0] if produces else req.stage
    else:
        raise HTTPException(400, "Provide artifact_name (preferred) or stage")

    project_name = job.get("project_name", job_id)
    artifacts_dir = OM_ROOT / "projects" / project_name / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out = artifacts_dir / f"{artifact_name}.json"
    out.write_text(json.dumps(req.content, ensure_ascii=False, indent=2))
    return {"saved": artifact_name, "path": str(out)}


@router.post("/{job_id}/retry")
async def retry_job(job_id: str):
    """Re-run a failed job — resumes from completed_stages.

    Only "failed" is retryable. A live "running" job must NEVER be retried:
    the persistence layer already flips any job that was mid-flight when the
    process died to "failed" on startup (JobStore._load_all), so a genuinely
    orphaned job always shows up as "failed", never stuck at "running". Prior
    to this fix "running" was also accepted (meant for that orphaned case),
    but that let a still-live job be retried too — enqueuing a SECOND
    concurrent run_pipeline_job for the same job_id, racing the first one and
    corrupting whichever artifact each happened to write last.
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") != "failed":
        raise HTTPException(400, "Only failed jobs can be retried")
    # A retry is semantically a new run — start its on-disk event log fresh,
    # same as create() does, so retrying repeatedly doesn't keep appending
    # to the SAME events.jsonl from the very first attempt onward forever.
    job_store.reset_events_log(job_id)
    job_store.update(job_id, status="queued")
    get_job_queue().enqueue(run_pipeline_job, job_id, {
        "project_name": job.get("project_name", job_id),
        "content_type": job.get("content_type", "marketing_film"),
        "pipeline": job.get("pipeline", "cinematic"),
        "brand_info": job.get("brand_info", {}),
        "options": job.get("options", {}),
    })
    return {"job_id": job_id, "status": "queued"}


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str):
    """Remove a finished job's record — mirrors brands' delete pattern.

    Restricted to terminal jobs (completed/failed/cancelled) so a job's state
    can never be ripped out from under the task that's still actively
    updating it — same reasoning as retry_job's status guard above.
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") not in TERMINAL_STATUSES:
        raise HTTPException(400, "Only completed, failed, or cancelled jobs can be deleted")
    job_store.delete(job_id)
    return None
