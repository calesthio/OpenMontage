"""Job API: create, query, approve pipeline jobs."""

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.store import job_store
from app.runner.stage_runner import run_pipeline_job

router = APIRouter()


class CreateJobRequest(BaseModel):
    project_name: str
    content_type: str          # e.g. "marketing_film"
    pipeline: str              # e.g. "cinematic"
    brand_info: dict[str, Any]
    options: dict[str, Any] = {}


class ApproveStageRequest(BaseModel):
    action: str               # "approve" | "reject"
    feedback: str = ""


@router.post("", status_code=201)
async def create_job(req: CreateJobRequest, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())
    job_store.create(job_id, req.model_dump())
    bg.add_task(run_pipeline_job, job_id, req.model_dump())
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
        raise HTTPException(404, "Job not found or not awaiting approval")
    return {"job_id": job_id, "action": req.action}
