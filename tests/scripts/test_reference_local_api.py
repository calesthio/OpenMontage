from __future__ import annotations

import importlib
import json
from pathlib import Path
from urllib.parse import urlencode


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_reference_local_api_health_route():
    api = importlib.import_module("scripts.reference_local_api")

    response = api.route_request("GET", "/api/reference/health")

    assert response.status_code == 200
    assert response.payload == {"status": "ok", "service": "reference_local_api"}


def test_reference_local_api_console_route_serves_static_ui():
    api = importlib.import_module("scripts.reference_local_api")

    response = api.route_request("GET", "/")

    assert response.status_code == 200
    assert response.content_type == "text/html; charset=utf-8"
    assert "OpenMontage Reference Console" in response.payload
    assert "/api/reference/state" in response.payload
    assert "/api/reference/actions/prepare" in response.payload
    assert "/api/reference/actions/execute" in response.payload
    assert "/api/reference/jobs/status" in response.payload
    assert "/api/reference/jobs/list" in response.payload
    assert "/api/reference/projects/create" in response.payload
    assert "/api/reference/projects/import-source" in response.payload
    assert "operator_guidance" in response.payload
    assert "renderActionGuidance" in response.payload
    assert "renderPreparedCommand" in response.payload
    assert "copyPreparedCommand" in response.payload
    assert "downloadPreparedCommand" in response.payload
    assert "navigator.clipboard.writeText" in response.payload
    assert "prepared-command-copy" in response.payload
    assert "prepared-command-download" in response.payload
    assert "blocked_reason" in response.payload
    assert "执行安全动作" in response.payload
    assert "查看复核要求" in response.payload
    assert "复制命令" in response.payload
    assert "下载 .sh" in response.payload
    assert "pollJobStatus" in response.payload
    assert "renderJobs" in response.payload
    assert ".venv/bin/python" not in response.payload


def test_reference_local_api_state_route_hides_commands(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    project_dir = tmp_path / "project"
    path = "/api/reference/state?" + urlencode({"project_dir": str(project_dir)})

    response = api.route_request("GET", path)
    serialized = json.dumps(response.payload, ensure_ascii=False)

    assert response.status_code == 200
    assert response.payload["phase"] == "start"
    assert response.payload["actions"][0]["id"] == "analyze_reference"
    assert "command" not in response.payload["actions"][0]
    assert ".venv/bin/python" not in serialized


def test_reference_local_api_create_project_route(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    projects_root = tmp_path / "projects"

    response = api.route_request(
        "POST",
        "/api/reference/projects/create",
        {
            "project_name": "Reference Demo",
            "projects_root": str(projects_root),
        },
    )

    payload = response.payload
    project_dir = Path(payload["project_dir"])

    assert response.status_code == 201
    assert payload["status"] == "created"
    assert payload["project_slug"] == "reference-demo"
    assert project_dir == projects_root / "reference-demo"
    assert (project_dir / "project.json").is_file()
    assert (project_dir / "source").is_dir()
    assert (project_dir / "assets" / "images").is_dir()
    assert "command" not in payload


def test_reference_local_api_import_source_route_updates_next_state(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    project_dir = tmp_path / "projects" / "reference-demo"
    source_video = tmp_path / "reference.mp4"
    source_video.write_bytes(b"fake mp4")

    create_response = api.route_request(
        "POST",
        "/api/reference/projects/create",
        {
            "project_name": "Reference Demo",
            "projects_root": str(tmp_path / "projects"),
        },
    )
    assert create_response.status_code == 201

    import_response = api.route_request(
        "POST",
        "/api/reference/projects/import-source",
        {
            "project_dir": str(project_dir),
            "source_path": str(source_video),
        },
    )

    payload = import_response.payload
    local_video = Path(payload["local_video_path"])
    artifact_path = Path(payload["artifact_path"])
    state_response = api.route_request(
        "GET",
        "/api/reference/state?" + urlencode({"project_dir": str(project_dir)}),
    )

    assert import_response.status_code == 200
    assert payload["status"] == "imported"
    assert local_video == project_dir / "source" / "reference.mp4"
    assert local_video.read_bytes() == b"fake mp4"
    assert artifact_path.is_file()
    assert payload["next_step"] == "analyze_reference"
    assert "command" not in payload
    assert state_response.payload["status"]["status"] == "source_imported_needs_analysis"
    assert state_response.payload["actions"][0]["id"] == "analyze_imported_reference"
    assert "command" not in state_response.payload["actions"][0]


def test_reference_local_api_prepare_route_blocks_missing_confirmation(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "sample-seedance-production-plan.json",
        {"status": "ready_for_production", "target_mode": "seedance"},
    )
    _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        {"status": "dry_run_ready", "dry_run": True},
    )

    response = api.route_request(
        "POST",
        "/api/reference/actions/prepare",
        {
            "project_dir": str(project_dir),
            "action_id": "run_one_paid_seedance_sample",
        },
    )

    assert response.status_code == 409
    assert response.payload["status"] == "blocked"
    assert "RUN SEEDANCE SAMPLE" in response.payload["error"]
    assert "command" not in response.payload


def test_reference_local_api_prepare_route_returns_command_after_confirmation(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "sample-seedance-production-plan.json",
        {"status": "ready_for_production", "target_mode": "seedance"},
    )
    _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        {"status": "dry_run_ready", "dry_run": True},
    )

    response = api.route_request(
        "POST",
        "/api/reference/actions/prepare",
        {
            "project_dir": str(project_dir),
            "action_id": "run_one_paid_seedance_sample",
            "confirmation_phrase": "RUN SEEDANCE SAMPLE",
        },
    )

    assert response.status_code == 200
    assert response.payload["status"] == "ready_to_execute"
    assert "--allow-paid-generation" in response.payload["command"]


def test_reference_local_api_execute_route_starts_safe_local_action(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    project_dir = tmp_path / "project"

    response = api.route_request(
        "POST",
        "/api/reference/actions/execute",
        {
            "project_dir": str(project_dir),
            "action_id": "analyze_reference",
        },
    )

    payload = response.payload
    status_response = api.route_request(
        "GET",
        "/api/reference/jobs/status?" + urlencode(
            {"project_dir": str(project_dir), "job_id": payload["job_id"]}
        ),
    )

    assert response.status_code == 202
    assert payload["action_id"] == "analyze_reference"
    assert payload["status"] in {"running", "succeeded", "failed"}
    assert Path(payload["job_path"]).is_file()
    assert Path(payload["log_path"]).is_file()
    assert "command" not in payload
    assert status_response.status_code == 200
    assert status_response.payload["job_id"] == payload["job_id"]
    assert "command" not in status_response.payload


def test_reference_local_api_job_list_route_returns_project_jobs_without_commands(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    queue = importlib.import_module("scripts.reference_job_queue")
    project_dir = tmp_path / "project"
    first = queue.start_prepared_action(
        {
            "version": "1.0",
            "status": "ready_to_execute",
            "project_dir": str(project_dir),
            "phase": "start",
            "action_id": "doctor",
            "label": "Doctor",
            "script": "scripts/reference_console_doctor.py",
            "command": ".venv/bin/python scripts/reference_console_doctor.py --timeout 0.01",
            "risk": "local",
            "paid_generation": False,
            "requires_confirmation": False,
        },
        wait=True,
    )

    response = api.route_request(
        "GET",
        "/api/reference/jobs/list?" + urlencode({"project_dir": str(project_dir)}),
    )
    serialized = json.dumps(response.payload, ensure_ascii=False)

    assert response.status_code == 200
    assert response.payload["status"] == "ok"
    assert response.payload["project_dir"] == str(project_dir.resolve())
    assert response.payload["jobs"][0]["job_id"] == first["job_id"]
    assert Path(response.payload["jobs"][0]["job_path"]).is_file()
    assert Path(response.payload["jobs"][0]["log_path"]).is_file()
    assert "command" not in serialized
    assert ".venv/bin/python" not in serialized


def test_reference_local_api_execute_route_blocks_paid_action(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "sample-seedance-production-plan.json",
        {"status": "ready_for_production", "target_mode": "seedance"},
    )
    _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        {"status": "dry_run_ready", "dry_run": True},
    )

    response = api.route_request(
        "POST",
        "/api/reference/actions/execute",
        {
            "project_dir": str(project_dir),
            "action_id": "run_one_paid_seedance_sample",
            "confirmation_phrase": "RUN SEEDANCE SAMPLE",
        },
    )

    assert response.status_code == 409
    assert response.payload["status"] == "blocked"
    assert response.payload["blocked_reason"] == "paid_generation_prepare_only"
    assert "safe local actions" in response.payload["error"]
    assert "command" not in response.payload


def test_reference_local_api_execute_route_blocks_production_approval(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir
        / "artifacts"
        / "reference-assets"
        / "sample-assets-bound-package.json",
        {"approval": {"status": "pending_human_review"}},
    )

    response = api.route_request(
        "POST",
        "/api/reference/actions/execute",
        {
            "project_dir": str(project_dir),
            "action_id": "approve_for_seedance",
            "confirmation_phrase": "APPROVE REFERENCE PACKAGE",
        },
    )

    assert response.status_code == 409
    assert response.payload["status"] == "blocked"
    assert response.payload["blocked_reason"] == "production_approval_prepare_only"
    assert "Production approval actions" in response.payload["error"]
    assert "command" not in response.payload
    assert "job_path" not in response.payload


def test_reference_local_api_execute_route_blocks_delivery_export(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    project_dir = tmp_path / "project"
    output_path = project_dir / "renders" / "reference-final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake mp4")
    _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {
            "status": "rendered",
            "dry_run": False,
            "output_path": str(output_path),
        },
    )

    response = api.route_request(
        "POST",
        "/api/reference/actions/execute",
        {
            "project_dir": str(project_dir),
            "action_id": "export_delivery_package",
            "confirmation_phrase": "APPROVE FINAL DELIVERY",
        },
    )

    assert response.status_code == 409
    assert response.payload["status"] == "blocked"
    assert response.payload["blocked_reason"] == "delivery_export_prepare_only"
    assert "Delivery export actions" in response.payload["error"]
    assert "command" not in response.payload
    assert "job_path" not in response.payload


def test_reference_local_api_execute_route_blocks_manual_review(tmp_path):
    api = importlib.import_module("scripts.reference_local_api")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "sample-seedance-sample-result.json",
        {"status": "generated", "output_path": "sample.mp4"},
    )

    response = api.route_request(
        "POST",
        "/api/reference/actions/execute",
        {
            "project_dir": str(project_dir),
            "action_id": "review_sample_before_more_generation",
        },
    )

    assert response.status_code == 409
    assert response.payload["status"] == "blocked"
    assert response.payload["blocked_reason"] == "manual_review_required"
    assert "Manual-review actions" in response.payload["error"]
    assert "command" not in response.payload
    assert "job_path" not in response.payload


def test_reference_local_api_rejects_unknown_route():
    api = importlib.import_module("scripts.reference_local_api")

    response = api.route_request("GET", "/api/reference/missing")

    assert response.status_code == 404
    assert response.payload["status"] == "not_found"
