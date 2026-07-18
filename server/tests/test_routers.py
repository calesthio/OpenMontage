"""API contract tests for the FastAPI routers (via TestClient, no pipeline run)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
from app.routers import jobs, events, brands
from app.store import JobStore


class _NoQueue:
    """Swallows enqueue so POST /jobs doesn't actually run the pipeline."""
    def enqueue(self, *args, **kwargs):
        pass


@pytest.fixture
def client(tmp_path, monkeypatch):
    ts = JobStore(persist_dir=tmp_path / "js")
    monkeypatch.setattr(jobs, "job_store", ts)
    monkeypatch.setattr(events, "job_store", ts)
    monkeypatch.setattr(jobs, "OM_ROOT", tmp_path)                 # isolate artifact writes
    monkeypatch.setattr(brands, "BRAND_KITS_DIR", tmp_path / "brand_kits")
    monkeypatch.setattr(jobs, "get_job_queue", lambda: _NoQueue())
    return TestClient(main.app)


def _new_job_body(**over):
    body = {
        "project_name": "demo",
        "content_type": "marketing_film",
        "pipeline": "cinematic",
        "brand_info": {"brand_name": "Acme"},
        "options": {},
    }
    body.update(over)
    return body


# ── health / system ──────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_system_capabilities(client):
    r = client.get("/system/capabilities")
    assert r.status_code == 200
    b = r.json()["backends"]
    assert b["queue"]["active"] == "asyncio"
    assert b["storage"]["active"] == "local"
    assert b["auth"]["active"] == "passphrase"


# ── jobs ─────────────────────────────────────────────────────────────────────

def test_job_create_list_get(client):
    r = client.post("/jobs", json=_new_job_body())
    assert r.status_code == 201
    jid = r.json()["job_id"]

    listed = client.get("/jobs").json()["jobs"]
    assert any(j["job_id"] == jid for j in listed)

    got = client.get(f"/jobs/{jid}")
    assert got.status_code == 200
    assert got.json()["project_name"] == "demo"

    assert client.get("/jobs/does-not-exist").status_code == 404


def test_retry_requires_failed(client):
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    # freshly queued → cannot retry
    assert client.post(f"/jobs/{jid}/retry").status_code == 400
    # mark failed → retry allowed
    jobs.job_store.update(jid, status="failed")
    r = client.post(f"/jobs/{jid}/retry")
    assert r.status_code == 200
    assert r.json()["status"] == "queued"
    assert client.post("/jobs/nope/retry").status_code == 404


def test_retry_rejects_a_live_running_job(client):
    # Regression: "running" used to be accepted too (meant for a job orphaned
    # by a crash), but a genuinely orphaned job is always flipped to "failed"
    # by JobStore._load_all on startup — so "running" only ever means a job is
    # actually, currently being driven. Retrying it would enqueue a SECOND
    # concurrent run_pipeline_job for the same job_id, racing the live one.
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    jobs.job_store.update(jid, status="running")
    r = client.post(f"/jobs/{jid}/retry")
    assert r.status_code == 400


def test_approve_requires_awaiting(client):
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    # not awaiting approval → 404
    assert client.post(f"/jobs/{jid}/approve", json={"action": "approve"}).status_code == 404


def test_save_artifact_writes_file(client, tmp_path):
    jid = client.post("/jobs", json=_new_job_body(project_name="p1")).json()["job_id"]
    r = client.post(f"/jobs/{jid}/artifact", json={"stage": "script", "content": {"k": 1}})
    assert r.status_code == 200
    written = tmp_path / "projects" / "p1" / "artifacts" / "script.json"
    assert written.exists()
    assert client.post("/jobs/nope/artifact", json={"stage": "s", "content": {}}).status_code == 404


# ── brands CRUD ──────────────────────────────────────────────────────────────

def test_brand_kit_crud(client):
    created = client.post("/brands", json={"brand_name": "Nova", "slogan": "shine"})
    assert created.status_code == 201
    kit = created.json()
    kid = kit["kit_id"]
    assert kit["brand_name"] == "Nova"

    assert any(k["kit_id"] == kid for k in client.get("/brands").json()["brand_kits"])
    assert client.get(f"/brands/{kid}").json()["slogan"] == "shine"

    patched = client.patch(f"/brands/{kid}", json={"slogan": "brighter"})
    assert patched.status_code == 200
    assert patched.json()["slogan"] == "brighter"

    assert client.delete(f"/brands/{kid}").status_code == 204
    assert client.get(f"/brands/{kid}").status_code == 404


def test_brand_kit_missing(client):
    assert client.get("/brands/ghost").status_code == 404
    assert client.patch("/brands/ghost", json={"slogan": "x"}).status_code == 404
    assert client.delete("/brands/ghost").status_code == 404
