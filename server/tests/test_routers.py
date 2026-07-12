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
    # Confirmed live (deep quality review): no route actually calls
    # AuthProvider.verify() — reporting auth the same way as storage/queue
    # (which genuinely ARE what's running) implied requests are
    # authenticated when they aren't. Must self-report honestly.
    assert b["auth"]["enforced"] is False


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


def test_create_job_rejects_unknown_pipeline(client):
    # Regression: any pipeline string was accepted at creation time and
    # silently fell back to cinematic's stages deep inside _resolve_stages —
    # the job ran, just not the pipeline the caller asked for.
    r = client.post("/jobs", json=_new_job_body(pipeline="not-a-real-pipeline"))
    assert r.status_code == 400


def test_create_job_accepts_pipeline_map_alias(client):
    # "marketing_film" is a real alias (app.runner.stage_runner.PIPELINE_MAP)
    # but not a pipeline_defs/*.yaml manifest — validation must accept it too.
    r = client.post("/jobs", json=_new_job_body(pipeline="marketing_film"))
    assert r.status_code == 201


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


def test_save_artifact_rejects_stage_not_in_jobs_pipeline(client):
    # Regression: any safe-looking identifier was accepted as `stage` and
    # silently written + 200'd, even if it wasn't a real stage of the job's
    # own pipeline (e.g. a typo, or a stage name from a different pipeline).
    jid = client.post("/jobs", json=_new_job_body(project_name="p1b", pipeline="cinematic")).json()["job_id"]
    r = client.post(f"/jobs/{jid}/artifact", json={"stage": "not_a_real_stage", "content": {}})
    assert r.status_code == 400


def test_delete_job_requires_terminal_status(client):
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    # freshly queued → not terminal, cannot delete
    assert client.delete(f"/jobs/{jid}").status_code == 400
    jobs.job_store.update(jid, status="completed")
    r = client.delete(f"/jobs/{jid}")
    assert r.status_code == 204
    assert client.get(f"/jobs/{jid}").status_code == 404
    assert client.delete("/jobs/nope").status_code == 404


# ── security: path traversal via project_name / stage ────────────────────────

def test_create_job_rejects_traversal_project_name(client):
    # Confirmed live (deep quality review): project_name="../../outside_target"
    # let POST /jobs/{id}/artifact write a real file outside the projects/
    # tree. Reject at creation time so the unsafe value never enters the
    # store at all.
    r = client.post("/jobs", json=_new_job_body(project_name="../../outside_target"))
    assert r.status_code == 422


def test_save_artifact_rejects_traversal_stage_name(client, tmp_path):
    jid = client.post("/jobs", json=_new_job_body(project_name="p2")).json()["job_id"]
    r = client.post(f"/jobs/{jid}/artifact", json={"stage": "../../escaped", "content": {}})
    assert r.status_code == 422
    assert not (tmp_path.parent / "escaped.json").exists()


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


def _tiny_png_bytes(mode="RGB", size=(4000, 3000)) -> bytes:
    import io as _io
    from PIL import Image
    buf = _io.BytesIO()
    Image.new(mode, size, (10, 20, 30) if mode == "RGB" else (10, 20, 30, 128)).save(buf, format="PNG")
    return buf.getvalue()


def test_reference_image_upload_resizes_and_records_path(client, tmp_path):
    kid = client.post("/brands", json={"brand_name": "Rabbit TV"}).json()["kit_id"]

    resp = client.post(
        f"/brands/{kid}/reference-image",
        files={"file": ("ref.png", _tiny_png_bytes(), "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reference_image_path"] == "reference.png"
    assert body["reference_image_url"] == f"/brand-media/{kid}/reference.png"
    # Uploaded 4000x3000 — must come back under the cap on both axes.
    assert body["width"] <= 768 and body["height"] <= 768

    kit = client.get(f"/brands/{kid}").json()
    assert kit["reference_image_path"] == "reference.png"

    saved = tmp_path / "brand_kits" / kid / "reference.png"
    assert saved.exists()


def test_delete_brand_kit_removes_entire_directory(client, tmp_path):
    # Regression: DELETE only unlinked kit.json, leaving reference.png (and
    # the kit directory itself) on disk forever — and still publicly
    # servable via the /brand-media static mount, which has no existence
    # check tied to kit.json.
    kid = client.post("/brands", json={"brand_name": "Rabbit TV"}).json()["kit_id"]
    client.post(
        f"/brands/{kid}/reference-image",
        files={"file": ("ref.png", _tiny_png_bytes(), "image/png")},
    )
    kit_dir = tmp_path / "brand_kits" / kid
    assert kit_dir.exists()
    assert (kit_dir / "reference.png").exists()

    assert client.delete(f"/brands/{kid}").status_code == 204
    assert not kit_dir.exists()


def test_reference_image_upload_flattens_transparency_onto_white(client, tmp_path):
    kid = client.post("/brands", json={"brand_name": "Rabbit TV"}).json()["kit_id"]
    client.post(
        f"/brands/{kid}/reference-image",
        files={"file": ("logo.png", _tiny_png_bytes(mode="RGBA", size=(100, 100)), "image/png")},
    )
    from PIL import Image
    saved = Image.open(tmp_path / "brand_kits" / kid / "reference.png")
    assert saved.mode == "RGB"  # no alpha channel left to silently mishandle downstream


def test_reference_image_upload_rejects_non_image(client):
    kid = client.post("/brands", json={"brand_name": "Rabbit TV"}).json()["kit_id"]
    resp = client.post(
        f"/brands/{kid}/reference-image",
        files={"file": ("not-an-image.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400


def test_reference_image_upload_missing_kit(client):
    resp = client.post(
        "/brands/ghost/reference-image",
        files={"file": ("ref.png", _tiny_png_bytes(), "image/png")},
    )
    assert resp.status_code == 404
