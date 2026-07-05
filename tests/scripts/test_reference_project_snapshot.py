from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_reference_project_snapshot_reports_empty_project_for_web_ui(tmp_path):
    snapshot = importlib.import_module("scripts.reference_project_snapshot")
    project_dir = tmp_path / "project"

    payload = snapshot.build_snapshot(project_dir)

    assert payload["version"] == "1.0"
    assert payload["project_dir"] == str(project_dir.resolve())
    assert payload["status"]["status"] == "empty_project"
    assert payload["phase"] == "start"
    assert payload["artifacts"]["replication_package"] is None
    assert payload["next_actions"][0]["script"] == "scripts/reference_preview_pipeline.py"
    assert payload["safety"]["secrets_redacted"] is True
    assert payload["safety"]["paid_generation_started"] is False


def test_reference_project_snapshot_collects_delivery_and_media_paths(tmp_path):
    snapshot = importlib.import_module("scripts.reference_project_snapshot")
    project_dir = tmp_path / "project"
    final_video = project_dir / "deliveries" / "reference-final" / "reference-final.mp4"
    final_video.parent.mkdir(parents=True, exist_ok=True)
    final_video.write_bytes(b"fake mp4")
    manifest = _write_json(
        project_dir / "deliveries" / "reference-final" / "delivery-manifest.json",
        {
            "status": "ready_for_distribution",
            "delivery_dir": str(final_video.parent),
            "video_path": str(final_video),
            "included_files": [{"filename": "reference-final.mp4", "role": "final_video"}],
        },
    )
    _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {"status": "rendered", "dry_run": False, "output_path": str(final_video)},
    )

    payload = snapshot.build_snapshot(project_dir)

    assert payload["phase"] == "delivery"
    assert payload["status"]["status"] == "delivery_exported"
    assert payload["artifacts"]["delivery_manifest"] == str(manifest)
    assert payload["media"]["delivery_video_path"] == str(final_video)
    assert payload["media"]["delivery_video_exists"] is True
    assert payload["delivery"]["included_files"][0]["filename"] == "reference-final.mp4"


def test_reference_project_snapshot_does_not_leak_env_values(monkeypatch, tmp_path):
    snapshot = importlib.import_module("scripts.reference_project_snapshot")
    secret = "do-not-print-this-key"
    monkeypatch.setenv("RUNNINGHUB_API_KEY", secret)
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "sample-replication-package.json",
        {"approval": {"status": "pending_human_review"}},
    )

    payload = snapshot.build_snapshot(project_dir)

    assert secret not in json.dumps(payload, ensure_ascii=False)
    assert payload["safety"]["secrets_redacted"] is True


def test_reference_project_snapshot_marks_paid_actions_for_ui(tmp_path):
    snapshot = importlib.import_module("scripts.reference_project_snapshot")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "sample-seedance-production-plan.json",
        {"status": "ready_for_production", "target_mode": "seedance"},
    )
    _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        {"status": "dry_run_ready", "dry_run": True},
    )

    payload = snapshot.build_snapshot(project_dir)

    paid_action = next(
        action for action in payload["ui_actions"] if action["id"] == "run_one_paid_seedance_sample"
    )
    assert paid_action["paid_generation"] is True
    assert paid_action["requires_confirmation"] is True
    assert paid_action["confirmation_phrase"] == "RUN SEEDANCE SAMPLE"
    assert paid_action["risk"] == "paid_generation"
    assert paid_action["enabled"] is True


def test_reference_project_snapshot_marks_delivery_export_confirmation_for_ui(tmp_path):
    snapshot = importlib.import_module("scripts.reference_project_snapshot")
    project_dir = tmp_path / "project"
    output_path = project_dir / "renders" / "reference-final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake mp4")
    report = _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {
            "status": "rendered",
            "dry_run": False,
            "output_path": str(output_path),
        },
    )

    payload = snapshot.build_snapshot(project_dir)

    review_action = next(
        action for action in payload["ui_actions"] if action["id"] == "review_final_render"
    )
    assert review_action["script"] == "scripts/review_reference_final.py"
    assert review_action["risk"] == "local"
    assert review_action["requires_confirmation"] is False
    assert str(report) in review_action["command"]
    action = next(
        action for action in payload["ui_actions"] if action["id"] == "export_delivery_package"
    )
    assert action["paid_generation"] is False
    assert action["requires_confirmation"] is True
    assert action["confirmation_phrase"] == "APPROVE FINAL DELIVERY"
    assert action["risk"] == "delivery_export"
    assert str(report) in action["command"]


def test_reference_project_snapshot_collects_final_review_report(tmp_path):
    snapshot = importlib.import_module("scripts.reference_project_snapshot")
    project_dir = tmp_path / "project"
    output_path = project_dir / "renders" / "reference-final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake mp4")
    render_report = _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {"status": "rendered", "dry_run": False, "output_path": str(output_path)},
    )
    review_report = _write_json(
        project_dir / "artifacts" / "reference-final-review" / "sample-final-review.json",
        {
            "status": "final_review_ready_for_delivery",
            "source_render_report_path": str(render_report),
            "render": {"output_path": str(output_path)},
        },
    )

    payload = snapshot.build_snapshot(project_dir)

    assert payload["phase"] == "final_review"
    assert payload["status"]["status"] == "final_review_ready_for_delivery"
    assert payload["artifacts"]["final_review_report"] == str(review_report)
    assert payload["media"]["render_output_path"] == str(output_path)
    action = next(
        action for action in payload["ui_actions"] if action["id"] == "export_delivery_package"
    )
    assert str(render_report) in action["command"]
    assert action["confirmation_phrase"] == "APPROVE FINAL DELIVERY"


def test_reference_project_snapshot_main_prints_json(tmp_path, capsys):
    snapshot = importlib.import_module("scripts.reference_project_snapshot")
    project_dir = tmp_path / "project"

    exit_code = snapshot.main([str(project_dir)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["project_dir"] == str(project_dir.resolve())
