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
from app.runner.stage_runner import run_pipeline_job, _resolve_stages, _load_artifacts, PIPELINE_MAP
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
    # Per-scene keep/reroll (roadmap 2.3): on a reject at the assets gate,
    # the ids of the SPECIFIC manifest assets to regenerate. Everything not
    # listed is kept — and, via content-addressed output naming, costs
    # nothing to keep on the regenerate round.
    rejected_asset_ids: list[str] | None = None
    # Budget gate only: the user's NEW absolute budget ceiling (CNY). The
    # gate previously re-armed at spent×1.2 — an unbounded ratchet the user
    # never chose. When provided on an approve, it replaces that heuristic.
    new_budget_cny: float | None = None

    @field_validator("new_budget_cny")
    @classmethod
    def _validate_budget(cls, v: float | None) -> float | None:
        if v is not None and (v != v or v <= 0):   # NaN or non-positive
            raise ValueError("new_budget_cny must be a positive number")
        return v


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
    ok = job_store.set_approval(
        job_id, req.action, req.feedback,
        new_budget_cny=req.new_budget_cny,
        rejected_asset_ids=req.rejected_asset_ids,
    )
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


def _stale_stages(job: dict, project_dir: Path) -> list[str]:
    """Stages whose output artifacts are OLDER than an upstream input they
    depend on (roadmap 2.4 — the Hex/DAG model): editing an upstream
    artifact makes every completed downstream stage's output stale.

    Derived purely from artifact file mtimes vs each stage's declared
    required_artifacts_in — no extra bookkeeping to drift.
    """
    stages = _resolve_stages(job.get("pipeline", "cinematic"))
    artifacts_dir = project_dir / "artifacts"
    completed = set(job.get("completed_stages") or [])

    def _mtime(name: str) -> float | None:
        p = artifacts_dir / f"{name}.json"
        try:
            return p.stat().st_mtime
        except OSError:
            return None

    stale: list[str] = []
    for s in stages:
        if s["name"] not in completed:
            continue
        produced = [m for m in (_mtime(n) for n in s.get("produces") or []) if m is not None]
        required = [m for m in (_mtime(n) for n in s.get("required_artifacts_in") or []) if m is not None]
        if produced and required and min(produced) < max(required):
            stale.append(s["name"])
    return stale


@router.get("/{job_id}/artifacts")
async def get_job_artifacts(job_id: str):
    """Read-only view of every stage artifact the pipeline has written.

    The approval panel's preview used to be the ONLY window onto an
    artifact — once a gate resolved, the artifact vanished from the UI
    entirely (roadmap 1.2). This exposes what's already on disk
    (projects/<name>/artifacts/*.json) so the web app can render script /
    scene_plan / asset_manifest / decision_log at any time. `stale_stages`
    lists completed stages whose outputs predate an edited upstream input
    (roadmap 2.4) — the UI offers "仅重做此阶段 / 重做此阶段及后续" there.
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    project_dir = OM_ROOT / "projects" / job.get("project_name", job_id)
    return {
        "artifacts": _load_artifacts(project_dir),
        "stale_stages": _stale_stages(job, project_dir),
    }


class ReviseJobRequest(BaseModel):
    stage: str
    feedback: str = ""
    # "cascade": re-run the stage and everything after it (default — the
    # DAG-honest choice). "single": re-run ONLY this stage; later completed
    # stages stay completed (their outputs will read as stale until re-run).
    mode: str = "cascade"

    @field_validator("stage")
    @classmethod
    def _validate_stage(cls, v: str) -> str:
        if not _SAFE_STAGE_NAME.match(v):
            raise ValueError("stage must contain only letters, numbers, underscores, and hyphens")
        return v

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        if v not in ("cascade", "single"):
            raise ValueError("mode must be 'cascade' or 'single'")
        return v


@router.post("/{job_id}/revise", status_code=201)
async def revise_job(job_id: str, req: ReviseJobRequest):
    """Re-open a finished job at a chosen stage (roadmap 2.2) — success is
    no longer a dead end (previously the only actions on a completed job
    were watching it or deleting it; retry accepts only "failed").

    Clones the job (the original stays as an immutable record), rolls
    completed_stages back per `mode`, records the user's feedback for the
    re-entered stage, and re-enqueues. The clone shares the project
    workspace, so unchanged upstream artifacts — and, via content-addressed
    output naming, unchanged generated assets — are reused rather than
    regenerated.
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") not in TERMINAL_STATUSES:
        raise HTTPException(400, "Only a finished (completed/failed/cancelled) job can be revised")
    stages = _resolve_stages(job.get("pipeline", "cinematic"))
    stage_order = [s["name"] for s in stages]
    if req.stage not in stage_order:
        raise HTTPException(400, f"{req.stage!r} is not a stage of this job's pipeline")
    project_name = job.get("project_name", job_id)
    for other_id, other in job_store.all().items():
        if other.get("project_name") == project_name and other.get("status") in INFLIGHT_STATUSES:
            raise HTTPException(
                409,
                f"another job is already running on this project (job {other_id}); "
                "wait for it to finish before revising",
            )

    old_completed = set(job.get("completed_stages") or [])
    target_idx = stage_order.index(req.stage)
    if req.mode == "single":
        new_completed = sorted(old_completed - {req.stage})
    else:
        new_completed = [s for s in stage_order[:target_idx] if s in old_completed]

    # A new generation begins: archive the current top-level renders so the
    # re-render can't silently clobber them AND stale variants from the
    # previous generation can't confuse the renders/*.mp4 discovery glob
    # into misreading the new run as multi-variant (roadmap 2.5).
    renders_dir = OM_ROOT / "projects" / project_name / "renders"
    if renders_dir.is_dir() and "compose" not in new_completed:
        import time as _time
        history_dir = renders_dir / "history" / _time.strftime("%Y%m%d-%H%M%S")
        for f in renders_dir.glob("*.mp4"):
            try:
                history_dir.mkdir(parents=True, exist_ok=True)
                f.replace(history_dir / f.name)
            except OSError:
                pass

    new_id = str(uuid.uuid4())
    payload = {
        "project_name": project_name,
        "content_type": job.get("content_type", "marketing_film"),
        "pipeline": job.get("pipeline", "cinematic"),
        "brand_info": job.get("brand_info", {}),
        "options": job.get("options", {}),
    }
    job_store.create(new_id, {
        **payload,
        "completed_stages": new_completed,
        "cost_cny": float(job.get("cost_cny", 0.0) or 0.0),
        "revised_from": job_id,
        "revise_feedback": {"stage": req.stage, "feedback": req.feedback, "mode": req.mode},
    })
    get_job_queue().enqueue(run_pipeline_job, new_id, payload)
    return {"job_id": new_id, "status": "queued", "revised_from": job_id,
            "completed_stages": new_completed}


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
