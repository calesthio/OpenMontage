"""Render API — on-demand tutorial-video rendering on Kubernetes.

POST /renders {tutorial, base_url?, ref?, offline?, music?}
    -> creates a Job (worker container + native ttsd sidecar) and returns a render_id.
GET  /renders/{id}
    -> Job status; when succeeded, a presigned download URL from object storage.

The worker container renders and uploads renders/final.mp4 to MinIO under
"<render_id>/final.mp4"; this API presigns a GET for that key.

Config via env (see deploy/k8s/configmap.yaml + secrets):
  NAMESPACE, WORKER_IMAGE, TTSD_IMAGE, SECRET_TTSD_NAME, SECRET_MINIO_NAME,
  RESULT_BUCKET, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE,
  MAX_CONCURRENT, JOB_TTL_SECONDS, JOB_DEADLINE_SECONDS, WORKER_MEM_REQUEST,
  WORKER_MEM_LIMIT, WORKER_CPU_REQUEST, WORKER_CPU_LIMIT, SERVICE_ACCOUNT,
  CLIENT_REF (optional default).
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from kubernetes import client, config

NAMESPACE = os.environ.get("NAMESPACE", "tutorial-render")
WORKER_IMAGE = os.environ.get("WORKER_IMAGE", "tutorial-worker:latest")
TTSD_IMAGE = os.environ.get("TTSD_IMAGE", "circuit-ttsd:latest")
SECRET_TTSD_NAME = os.environ.get("SECRET_TTSD_NAME", "ttsd-secret")
SECRET_MINIO_NAME = os.environ.get("SECRET_MINIO_NAME", "minio-secret")
RESULT_BUCKET = os.environ.get("RESULT_BUCKET", "tutorials")
SERVICE_ACCOUNT = os.environ.get("SERVICE_ACCOUNT", "render-api")
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "2"))
JOB_TTL = int(os.environ.get("JOB_TTL_SECONDS", "3600"))
JOB_DEADLINE = int(os.environ.get("JOB_DEADLINE_SECONDS", "1800"))
WORKER_MEM_REQUEST = os.environ.get("WORKER_MEM_REQUEST", "4Gi")
WORKER_MEM_LIMIT = os.environ.get("WORKER_MEM_LIMIT", "8Gi")
WORKER_CPU_REQUEST = os.environ.get("WORKER_CPU_REQUEST", "1")
WORKER_CPU_LIMIT = os.environ.get("WORKER_CPU_LIMIT", "4")
CLIENT_REF = os.environ.get("CLIENT_REF", "")
RENDER_RUNTIME = os.environ.get("RENDER_RUNTIME", "remotion")

LABEL_APP = "tutorial-render"
_SLUG = re.compile(r"[^a-z0-9-]+")

app = FastAPI(title="Tutorial Render API")


def _load_kube():
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()


_load_kube()


class RenderRequest(BaseModel):
    tutorial: str
    base_url: Optional[str] = None
    ref: Optional[str] = None
    offline: bool = False
    music: Optional[str] = None
    render_runtime: Optional[str] = None  # "remotion" (default) | "ffmpeg"


def _slug(s: str) -> str:
    return _SLUG.sub("-", s.lower()).strip("-")[:24] or "tutorial"


def _minio():
    from minio import Minio

    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() in ("1", "true", "yes"),
    )


def _active_job_count(batch: client.BatchV1Api) -> int:
    jobs = batch.list_namespaced_job(NAMESPACE, label_selector=f"app={LABEL_APP}")
    n = 0
    for j in jobs.items:
        st = j.status
        done = (st.succeeded or 0) > 0 or (st.failed or 0) > 0
        if not done:
            n += 1
    return n


def _build_job(render_id: str, req: RenderRequest) -> dict:
    labels = {"app": LABEL_APP, "render-id": render_id}

    worker_env = [
        {"name": "TUTORIAL", "value": req.tutorial},
        {"name": "PROJECT_ID", "value": render_id},
        {"name": "NARRATION_URL", "value": "http://127.0.0.1:5557"},
        {"name": "RESULT_BUCKET", "value": RESULT_BUCKET},
        {"name": "OPENMONTAGE_PROJECTS_DIR", "value": "/work/projects"},
        {"name": "CLIENT_DIR", "value": "/app/client"},
        {"name": "RENDER_RUNTIME", "value": req.render_runtime or RENDER_RUNTIME},
    ]
    if req.base_url:
        worker_env.append({"name": "BASE_URL", "value": req.base_url})
    if req.offline:
        worker_env.append({"name": "OFFLINE", "value": "1"})
    if req.music:
        worker_env.append({"name": "MUSIC", "value": req.music})
    ref = req.ref or CLIENT_REF
    if ref:
        worker_env.append({"name": "CLIENT_REF", "value": ref})

    ttsd_sidecar = {
        "name": "ttsd",
        "image": TTSD_IMAGE,
        "restartPolicy": "Always",  # native sidecar (k8s >= 1.28): won't block Job completion
        "envFrom": [{"secretRef": {"name": SECRET_TTSD_NAME}}],
        "env": [
            {"name": "TTSD_PORT", "value": "5557"},
            {"name": "NARRATION_CLIP_DIR", "value": "/clips"},
        ],
        "ports": [{"containerPort": 5557}],
        "volumeMounts": [{"name": "clips", "mountPath": "/clips"}],
        "readinessProbe": {"httpGet": {"path": "/health", "port": 5557}, "periodSeconds": 5},
    }

    worker = {
        "name": "worker",
        "image": WORKER_IMAGE,
        "env": worker_env,
        "envFrom": [{"secretRef": {"name": SECRET_MINIO_NAME}}],
        "resources": {
            "requests": {"memory": WORKER_MEM_REQUEST, "cpu": WORKER_CPU_REQUEST},
            "limits": {"memory": WORKER_MEM_LIMIT, "cpu": WORKER_CPU_LIMIT},
        },
        "volumeMounts": [
            {"name": "work", "mountPath": "/work"},
            {"name": "clips", "mountPath": "/clips"},
        ],
    }

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": f"render-{render_id}", "namespace": NAMESPACE, "labels": labels},
        "spec": {
            "ttlSecondsAfterFinished": JOB_TTL,
            "activeDeadlineSeconds": JOB_DEADLINE,
            "backoffLimit": 0,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "Never",
                    "serviceAccountName": SERVICE_ACCOUNT,
                    "volumes": [
                        {"name": "work", "emptyDir": {}},
                        {"name": "clips", "emptyDir": {}},
                    ],
                    "initContainers": [ttsd_sidecar],
                    "containers": [worker],
                },
            },
        },
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/renders")
def create_render(req: RenderRequest):
    if not req.offline and not req.base_url:
        raise HTTPException(400, "base_url is required unless offline=true")
    batch = client.BatchV1Api()
    if _active_job_count(batch) >= MAX_CONCURRENT:
        raise HTTPException(429, f"at capacity ({MAX_CONCURRENT} concurrent renders)")

    render_id = f"{_slug(req.tutorial)}-{uuid.uuid4().hex[:8]}"
    job = _build_job(render_id, req)
    try:
        batch.create_namespaced_job(NAMESPACE, job)
    except client.exceptions.ApiException as e:
        raise HTTPException(500, f"failed to create Job: {e.reason}") from e
    return {"render_id": render_id, "status": "queued"}


@app.get("/renders/{render_id}")
def get_render(render_id: str):
    batch = client.BatchV1Api()
    try:
        job = batch.read_namespaced_job_status(f"render-{render_id}", NAMESPACE)
    except client.exceptions.ApiException:
        raise HTTPException(404, "render not found")

    st = job.status
    if (st.succeeded or 0) > 0:
        status = "succeeded"
    elif (st.failed or 0) > 0:
        status = "failed"
    elif (st.active or 0) > 0:
        status = "running"
    else:
        status = "queued"

    out = {"render_id": render_id, "status": status}
    if status == "succeeded":
        try:
            url = _minio().presigned_get_object(
                RESULT_BUCKET, f"{render_id}/final.mp4", expires=timedelta(hours=24)
            )
            out["download_url"] = url
        except Exception as e:  # noqa: BLE001
            out["download_error"] = str(e)
    return out
