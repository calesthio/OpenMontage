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
    # Regression: the wizard and the settings page each hardcoded their own
    # independent copy of the model catalog, which could silently drift.
    catalog = r.json()["model_catalog"]
    assert "leapfast/ltx-2.3" in catalog["video_models"]
    assert "leapfast/flux2" in catalog["image_models"]
    assert "qwen3-tts-flash" in catalog["tts_models"]


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


def test_approve_double_submit_gets_409_not_silently_dropped(client):
    # Regression: two near-simultaneous POST /approve calls both used to pass
    # JobStore.set_approval's status check before either was consumed, so the
    # second call's write silently clobbered the first's decision. The second
    # call must now get a clear "already resolved" response instead of either
    # succeeding again or looking identical to a plain 404.
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    jobs.job_store.update(jid, status="awaiting_approval")

    r1 = client.post(f"/jobs/{jid}/approve", json={"action": "approve"})
    assert r1.status_code == 200

    r2 = client.post(f"/jobs/{jid}/approve", json={"action": "reject"})
    assert r2.status_code == 409
    assert "already resolved" in r2.json()["detail"].lower()


def test_save_artifact_writes_file(client, tmp_path):
    jid = client.post("/jobs", json=_new_job_body(project_name="p1")).json()["job_id"]
    r = client.post(f"/jobs/{jid}/artifact", json={"stage": "script", "content": {"k": 1}})
    assert r.status_code == 200
    # cinematic's "script" stage produces an artifact that happens to share
    # its name — the file must land under the produces name.
    written = tmp_path / "projects" / "p1" / "artifacts" / "script.json"
    assert written.exists()
    assert client.post("/jobs/nope/artifact", json={"stage": "s", "content": {}}).status_code == 404


def test_save_artifact_by_stage_resolves_to_produces_name(client, tmp_path):
    # Regression (silent inline-edit discard): 6 of cinematic's 8 stages name
    # their artifact differently from the stage (stage "proposal" produces
    # "proposal_packet"). The endpoint used to write artifacts/<stage>.json
    # verbatim — an orphan file no stage ever reads back — while returning
    # 200 "saved". The edit must land at the PRODUCES name the pipeline's
    # _load_artifacts actually consumes.
    jid = client.post("/jobs", json=_new_job_body(project_name="p2")).json()["job_id"]
    r = client.post(f"/jobs/{jid}/artifact", json={"stage": "proposal", "content": {"edited": True}})
    assert r.status_code == 200
    assert r.json()["saved"] == "proposal_packet"
    artifacts_dir = tmp_path / "projects" / "p2" / "artifacts"
    assert (artifacts_dir / "proposal_packet.json").exists()
    assert not (artifacts_dir / "proposal.json").exists()


def test_save_artifact_by_artifact_name_directly(client, tmp_path):
    jid = client.post("/jobs", json=_new_job_body(project_name="p3")).json()["job_id"]
    r = client.post(f"/jobs/{jid}/artifact", json={"artifact_name": "scene_plan", "content": {"scenes": []}})
    assert r.status_code == 200
    assert r.json()["saved"] == "scene_plan"
    assert (tmp_path / "projects" / "p3" / "artifacts" / "scene_plan.json").exists()
    # An artifact name from a different pipeline / a typo is rejected.
    r2 = client.post(f"/jobs/{jid}/artifact", json={"artifact_name": "not_an_artifact", "content": {}})
    assert r2.status_code == 400
    # Neither field at all is rejected.
    r3 = client.post(f"/jobs/{jid}/artifact", json={"content": {}})
    assert r3.status_code == 400


def test_save_artifact_rejects_stage_not_in_jobs_pipeline(client):
    # Regression: any safe-looking identifier was accepted as `stage` and
    # silently written + 200'd, even if it wasn't a real stage of the job's
    # own pipeline (e.g. a typo, or a stage name from a different pipeline).
    jid = client.post("/jobs", json=_new_job_body(project_name="p1b", pipeline="cinematic")).json()["job_id"]
    r = client.post(f"/jobs/{jid}/artifact", json={"stage": "not_a_real_stage", "content": {}})
    assert r.status_code == 400


def test_get_job_artifacts_returns_disk_artifacts(client, tmp_path):
    # Roadmap 1.2: artifacts must stay inspectable after their approval gate
    # resolves — this read-only endpoint exposes what's on disk.
    import json as _json
    jid = client.post("/jobs", json=_new_job_body(project_name="pa")).json()["job_id"]
    art_dir = tmp_path / "projects" / "pa" / "artifacts"
    art_dir.mkdir(parents=True)
    (art_dir / "brief.json").write_text(_json.dumps({"hook": "h"}))
    (art_dir / "scene_plan.json").write_text(_json.dumps({"scenes": [1, 2]}))
    r = client.get(f"/jobs/{jid}/artifacts")
    assert r.status_code == 200
    arts = r.json()["artifacts"]
    assert arts["brief"] == {"hook": "h"}
    assert arts["scene_plan"]["scenes"] == [1, 2]
    assert client.get("/jobs/nope/artifacts").status_code == 404


def test_approve_carries_new_budget_ceiling(client):
    # Roadmap 1.3: the budget gate's approve can carry the user's chosen new
    # absolute ceiling instead of the spent×1.2 ratchet.
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    jobs.job_store.update(jid, status="awaiting_approval")
    r = client.post(f"/jobs/{jid}/approve",
                    json={"action": "approve", "new_budget_cny": 80.5})
    assert r.status_code == 200
    # 未消费的决策还留在 store 里 — 直接读出验证透传。
    decision = jobs.job_store._approval_results[jid]
    assert decision == {"action": "approve", "feedback": "", "new_budget_cny": 80.5}


def test_approve_rejects_nonpositive_budget(client):
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    jobs.job_store.update(jid, status="awaiting_approval")
    r = client.post(f"/jobs/{jid}/approve",
                    json={"action": "approve", "new_budget_cny": -5})
    assert r.status_code == 422


def test_create_job_rejects_duplicate_project_name_while_inflight(client):
    # Regression: project_dir is keyed only by project_name with no
    # uniqueness check — two in-flight jobs sharing the same project_name
    # would concurrently write into the same artifacts/renders/ directory,
    # corrupting whichever wrote last.
    r1 = client.post("/jobs", json=_new_job_body(project_name="shared"))
    assert r1.status_code == 201
    first_id = r1.json()["job_id"]

    r2 = client.post("/jobs", json=_new_job_body(project_name="shared"))
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert first_id in detail
    assert "project name" in detail.lower()


def test_create_job_allows_same_project_name_once_prior_job_terminal(client):
    jid = client.post("/jobs", json=_new_job_body(project_name="reused")).json()["job_id"]
    jobs.job_store.update(jid, status="completed")
    r = client.post("/jobs", json=_new_job_body(project_name="reused"))
    assert r.status_code == 201


def test_create_job_allows_different_project_names_while_both_inflight(client):
    r1 = client.post("/jobs", json=_new_job_body(project_name="p-a"))
    r2 = client.post("/jobs", json=_new_job_body(project_name="p-b"))
    assert r1.status_code == 201
    assert r2.status_code == 201


# ── cancel ───────────────────────────────────────────────────────────────────

def test_cancel_not_found(client):
    assert client.post("/jobs/nope/cancel").status_code == 404


def test_cancel_queued_job_sets_flag_status_unchanged(client):
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    r = client.post(f"/jobs/{jid}/cancel")
    assert r.status_code == 200
    assert r.json() == {"job_id": jid, "status": "queued"}
    assert jobs.job_store.get(jid)["cancel_requested"] is True
    # the actual terminal flip is the runner's job, not this endpoint's
    assert jobs.job_store.get(jid)["status"] == "queued"


def test_cancel_running_job_sets_flag_status_unchanged(client):
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    jobs.job_store.update(jid, status="running")
    r = client.post(f"/jobs/{jid}/cancel")
    assert r.status_code == 200
    assert r.json() == {"job_id": jid, "status": "running"}
    assert jobs.job_store.get(jid)["cancel_requested"] is True


def test_cancel_awaiting_approval_job_rejects_and_marks_cancelled(client):
    # Reuses the existing reject plumbing (set_approval) verbatim, then sets
    # the new terminal "cancelled" status directly so the caller gets a
    # deterministic answer without waiting on the background runner.
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    jobs.job_store.update(jid, status="awaiting_approval")
    r = client.post(f"/jobs/{jid}/cancel")
    assert r.status_code == 200
    assert r.json() == {"job_id": jid, "status": "cancelled"}
    assert jobs.job_store.get(jid)["status"] == "cancelled"


def test_cancel_already_cancelled_job_returns_400(client):
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    jobs.job_store.update(jid, status="cancelled")
    assert client.post(f"/jobs/{jid}/cancel").status_code == 400


def test_cancel_completed_or_failed_job_returns_400(client):
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    jobs.job_store.update(jid, status="completed")
    assert client.post(f"/jobs/{jid}/cancel").status_code == 400

    jid2 = client.post("/jobs", json=_new_job_body(project_name="demo2")).json()["job_id"]
    jobs.job_store.update(jid2, status="failed")
    assert client.post(f"/jobs/{jid2}/cancel").status_code == 400


def test_cancel_awaiting_approval_double_submit_gets_409(client):
    # Mirrors test_approve_double_submit_gets_409_not_silently_dropped: a
    # concurrent approve/reject call that already resolved the gate must not
    # let cancel silently clobber it or look like a plain 404.
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    jobs.job_store.update(jid, status="awaiting_approval")
    assert jobs.job_store.set_approval(jid, "approve", "") is True

    r = client.post(f"/jobs/{jid}/cancel")
    assert r.status_code == 409


# ── retry: on-disk events log ────────────────────────────────────────────────

def test_retry_truncates_on_disk_events_log(client, tmp_path):
    # Regression: create() truncates events.jsonl once, but retry_job never
    # did, so every retry kept appending to the SAME file from the very
    # first attempt onward with no cap on disk.
    jid = client.post("/jobs", json=_new_job_body()).json()["job_id"]
    jobs.job_store.push_event(jid, {"type": "stage_started"})
    jobs.job_store.push_event(jid, {"type": "stage_completed"})
    events_path = tmp_path / "js" / f"{jid}.events.jsonl"
    assert len(events_path.read_text().splitlines()) == 2

    jobs.job_store.update(jid, status="failed")
    r = client.post(f"/jobs/{jid}/retry")
    assert r.status_code == 200
    assert events_path.read_text() == ""


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


def test_reference_image_upload_rejects_oversized_file(client):
    # Regression: the upload was read + decoded in full before any size
    # check, so an arbitrarily large (or decompression-bomb) upload could
    # exhaust memory before the post-decode resize ever ran.
    kid = client.post("/brands", json={"brand_name": "Rabbit TV"}).json()["kit_id"]
    from app.routers.brands import _REFERENCE_IMAGE_MAX_BYTES
    oversized = b"x" * (_REFERENCE_IMAGE_MAX_BYTES + 1)
    resp = client.post(
        f"/brands/{kid}/reference-image",
        files={"file": ("huge.png", oversized, "image/png")},
    )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


def test_reference_image_upload_accepts_file_right_at_the_cap(client):
    # Boundary check: exactly at the cap must still be accepted (only
    # strictly-over is rejected) as long as it's a valid image.
    kid = client.post("/brands", json={"brand_name": "Rabbit TV"}).json()["kit_id"]
    resp = client.post(
        f"/brands/{kid}/reference-image",
        files={"file": ("ref.png", _tiny_png_bytes(), "image/png")},
    )
    assert resp.status_code == 200


# ── brand slug: unicode-aware kit_id ─────────────────────────────────────────

def test_slug_keeps_non_latin_scripts_recognizable():
    from app.routers.brands import _slug
    # Korean
    assert _slug("한글 브랜드") == "한글-브랜드"
    # Japanese
    assert _slug("ブランド名") == "ブランド名"
    # Cyrillic
    assert _slug("Бренд Имя") == "бренд-имя"
    # Arabic
    assert _slug("علامة تجارية") not in ("", "-")
    # Latin still lowercases and collapses punctuation as before
    assert _slug("Acme, Inc.!") == "acme-inc"


def test_brand_kit_id_stays_recognizable_for_korean_name(client):
    # Regression: _slug only allowed [a-z0-9] plus the CJK Unified Ideographs
    # block, so a Korean/Japanese/Cyrillic/Arabic/emoji brand name collapsed
    # entirely to hyphens, leaving a kit_id that's just a random hex suffix
    # with no trace of the brand name.
    created = client.post("/brands", json={"brand_name": "한글 브랜드"})
    assert created.status_code == 201
    kit_id = created.json()["kit_id"]
    assert kit_id.startswith("한글-브랜드-")


# ── CORS origins ──────────────────────────────────────────────────────────────

def test_cors_origins_defaults_to_localhost_3000(monkeypatch):
    monkeypatch.delenv("OM_CORS_ORIGINS", raising=False)
    assert main._cors_origins() == ["http://localhost:3000"]


def test_cors_origins_env_override(monkeypatch):
    # Regression: allow_origins was hardcoded to localhost:3000 with no env
    # override, so any non-default deployment origin (NEXT_PUBLIC_SERVER_URL
    # pointed elsewhere) had every browser API call rejected by CORS.
    monkeypatch.setenv("OM_CORS_ORIGINS", "https://example.com, https://foo.bar ")
    assert main._cors_origins() == ["https://example.com", "https://foo.bar"]


# ── revise: success is no longer a dead end (roadmap 2.2/2.4) ────────────────

def test_revise_clones_and_rolls_back_cascade(client, tmp_path):
    jid = client.post("/jobs", json=_new_job_body(project_name="rv1")).json()["job_id"]
    jobs.job_store.update(
        jid, status="completed", cost_cny=12.5,
        completed_stages=["research", "proposal", "script", "scene_plan", "assets", "edit", "compose", "publish"],
    )
    r = client.post(f"/jobs/{jid}/revise", json={"stage": "scene_plan", "feedback": "分镜太平淡"})
    assert r.status_code == 201
    body = r.json()
    assert body["revised_from"] == jid
    assert body["completed_stages"] == ["research", "proposal", "script"]
    clone = jobs.job_store.get(body["job_id"])
    assert clone["status"] == "queued"
    assert clone["cost_cny"] == 12.5        # spend carries across generations
    assert clone["revise_feedback"] == {"stage": "scene_plan", "feedback": "分镜太平淡", "mode": "cascade"}
    # The original job is untouched — an immutable record.
    assert jobs.job_store.get(jid)["status"] == "completed"


def test_revise_single_mode_keeps_later_stages(client):
    jid = client.post("/jobs", json=_new_job_body(project_name="rv2")).json()["job_id"]
    jobs.job_store.update(
        jid, status="completed",
        completed_stages=["research", "proposal", "script", "scene_plan"],
    )
    r = client.post(f"/jobs/{jid}/revise", json={"stage": "proposal", "mode": "single"})
    assert r.status_code == 201
    assert r.json()["completed_stages"] == ["research", "scene_plan", "script"]


def test_revise_rejects_live_or_unknown(client):
    jid = client.post("/jobs", json=_new_job_body(project_name="rv3")).json()["job_id"]
    # queued (in-flight) → 400
    assert client.post(f"/jobs/{jid}/revise", json={"stage": "script"}).status_code == 400
    jobs.job_store.update(jid, status="completed")
    # unknown stage → 400; unknown job → 404
    assert client.post(f"/jobs/{jid}/revise", json={"stage": "not_a_stage"}).status_code == 400
    assert client.post("/jobs/nope/revise", json={"stage": "script"}).status_code == 404


def test_revise_archives_previous_renders(client, tmp_path):
    jid = client.post("/jobs", json=_new_job_body(project_name="rv4")).json()["job_id"]
    jobs.job_store.update(jid, status="completed",
                          completed_stages=["research", "compose"])
    renders = tmp_path / "projects" / "rv4" / "renders"
    renders.mkdir(parents=True)
    (renders / "final.mp4").write_bytes(b"gen1")
    (renders / "final_ltx.mp4").write_bytes(b"gen1-variant")
    r = client.post(f"/jobs/{jid}/revise", json={"stage": "compose"})
    assert r.status_code == 201
    # Top level is clean (no stale-variant glob confusion); both archived.
    assert list(renders.glob("*.mp4")) == []
    archived = sorted(p.name for p in (renders / "history").rglob("*.mp4"))
    assert archived == ["final.mp4", "final_ltx.mp4"]


def test_artifacts_endpoint_reports_stale_stages(client, tmp_path):
    import os as _os, json as _json
    jid = client.post("/jobs", json=_new_job_body(project_name="st1")).json()["job_id"]
    jobs.job_store.update(jid, status="completed",
                          completed_stages=["research", "proposal", "script"])
    art = tmp_path / "projects" / "st1" / "artifacts"
    art.mkdir(parents=True)
    now = 1_700_000_000
    # proposal consumed research_brief; script consumed proposal_packet.
    for name, mtime in [("research_brief", now), ("proposal_packet", now + 10), ("script", now + 20)]:
        p = art / f"{name}.json"
        p.write_text(_json.dumps({}))
        _os.utime(p, (mtime, mtime))
    assert client.get(f"/jobs/{jid}/artifacts").json()["stale_stages"] == []
    # The user edits the proposal — script's output now predates its input.
    _os.utime(art / "proposal_packet.json", (now + 30, now + 30))
    assert client.get(f"/jobs/{jid}/artifacts").json()["stale_stages"] == ["script"]
