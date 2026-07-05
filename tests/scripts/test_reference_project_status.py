from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_project_status_reports_empty_project_next_command(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")

    status = project_status.inspect_project(tmp_path / "project")

    assert status["status"] == "empty_project"
    assert status["current_artifact_path"] is None
    assert status["next_commands"][0]["script"] == "scripts/reference_preview_pipeline.py"


def test_project_status_reports_imported_source_next_command(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")
    project_dir = tmp_path / "project"
    source_video = project_dir / "source" / "reference.mp4"
    source_video.parent.mkdir(parents=True, exist_ok=True)
    source_video.write_bytes(b"fake mp4")
    manifest = _write_json(
        project_dir / "artifacts" / "reference-source" / "reference-source-import.json",
        {
            "status": "imported",
            "source_type": "reference_video",
            "local_video_path": str(source_video),
        },
    )

    status = project_status.inspect_project(project_dir)

    assert status["status"] == "source_imported_needs_analysis"
    assert status["current_artifact_path"] == str(manifest)
    assert status["next_commands"][0]["name"] == "analyze_imported_reference"
    assert status["next_commands"][0]["script"] == "scripts/reference_preview_pipeline.py"
    assert str(source_video) in status["next_commands"][0]["command"]


def test_project_status_prefers_prompt_reversed_package_for_human_edit(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")
    project_dir = tmp_path / "project"
    base = _write_json(
        project_dir / "artifacts" / "sample-replication-package.json",
        {"approval": {"status": "pending_human_review"}},
    )
    reversed_package = _write_json(
        project_dir / "artifacts" / "reference-prompts" / "sample-prompts-reversed-package.json",
        {"approval": {"status": "pending_human_review"}},
    )

    status = project_status.inspect_project(project_dir)

    assert base.exists()
    assert status["status"] == "prompts_reversed_needs_edit"
    assert status["current_artifact_path"] == str(reversed_package)
    assert status["next_commands"][0]["script"] == "scripts/reference_review_wizard.py"
    assert [command["script"] for command in status["next_commands"][1:5]] == [
        "scripts/edit_reference_package.py",
        "scripts/bind_reference_assets.py",
        "scripts/preview_reference_approval.py",
        "scripts/approve_reference_package.py",
    ]


def test_project_status_previews_approval_before_approve_command(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")
    project_dir = tmp_path / "project"
    assets_bound = _write_json(
        project_dir
        / "artifacts"
        / "reference-assets"
        / "sample-assets-bound-package.json",
        {"approval": {"status": "pending_human_review"}},
    )

    status = project_status.inspect_project(project_dir)

    assert status["status"] == "assets_bound_needs_approval"
    assert status["current_artifact_path"] == str(assets_bound)
    assert [command["script"] for command in status["next_commands"][:3]] == [
        "scripts/reference_review_wizard.py",
        "scripts/preview_reference_approval.py",
        "scripts/approve_reference_package.py",
    ]
    preview_command = status["next_commands"][1]["command"]
    assert "--duration 15" in preview_command
    assert "--resolution 480p" in preview_command
    assert "--batch-size 1" in preview_command


def test_project_status_recommends_demo_report_for_approved_package(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")
    project_dir = tmp_path / "project"
    approved = _write_json(
        project_dir
        / "artifacts"
        / "reference-review"
        / "sample-seedance-approved-package.json",
        {"approval": {"status": "approved", "target_mode": "seedance"}},
    )

    status = project_status.inspect_project(project_dir)

    assert status["status"] == "approved_for_production"
    assert status["current_artifact_path"] == str(approved)
    assert [command["script"] for command in status["next_commands"][:2]] == [
        "scripts/reference_demo_report.py",
        "scripts/preview_reference_seedance.py",
    ]


def test_project_status_reports_seedance_dry_run_ready(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")
    project_dir = tmp_path / "project"
    plan = _write_json(
        project_dir / "artifacts" / "sample-seedance-production-plan.json",
        {"status": "ready_for_production", "target_mode": "seedance"},
    )
    dry_run = _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        {"status": "dry_run_ready", "dry_run": True},
    )

    status = project_status.inspect_project(project_dir)

    assert plan.exists()
    assert status["status"] == "seedance_dry_run_ready"
    assert status["current_artifact_path"] == str(dry_run)
    assert status["production_plan_path"] == str(plan)
    assert [command["script"] for command in status["next_commands"][:2]] == [
        "scripts/preview_reference_final_edit.py",
        "scripts/plan_seedance_batch.py",
    ]
    assert "--allow-paid-generation" in status["next_commands"][1]["command"]


def test_project_status_recommends_compose_when_final_edit_is_ready(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")
    project_dir = tmp_path / "project"
    final_edit = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "sample-final-edit-plan.json",
        {
            "status": "ready_for_compose",
            "compose_handoff": {
                "output_path": str(project_dir / "renders" / "reference-final.mp4")
            },
        },
    )
    _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        {"status": "dry_run_ready", "dry_run": True},
    )

    status = project_status.inspect_project(project_dir)

    assert status["status"] == "final_edit_ready_for_compose"
    assert status["current_artifact_path"] == str(final_edit)
    assert status["next_commands"][0]["script"] == "scripts/compose_reference_final.py"
    assert "--dry-run" in status["next_commands"][0]["command"]
    assert status["next_commands"][1]["script"] == "scripts/compose_reference_final.py"
    assert "--burn-subtitles" in status["next_commands"][1]["command"]
    assert "--dry-run" not in status["next_commands"][1]["command"]


def test_project_status_recommends_audio_mix_when_final_edit_has_valid_audio_tracks(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")
    project_dir = tmp_path / "project"
    audio_path = project_dir / "assets" / "audio" / "voice.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"fake wav")
    final_edit = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "sample-final-edit-plan.json",
        {
            "status": "ready_for_compose",
            "compose_handoff": {
                "output_path": str(project_dir / "renders" / "reference-final.mp4"),
                "audio_tracks": [{"path": str(audio_path), "role": "speech"}],
            },
        },
    )

    status = project_status.inspect_project(project_dir)

    assert status["status"] == "final_edit_ready_for_compose"
    assert status["current_artifact_path"] == str(final_edit)
    formal_command = status["next_commands"][1]["command"]
    assert "--burn-subtitles" in formal_command
    assert "--mix-audio" in formal_command


def test_project_status_reports_final_render_ready_when_rendered_output_exists(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")
    project_dir = tmp_path / "project"
    output_path = project_dir / "renders" / "reference-final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake mp4")
    final_edit = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "sample-final-edit-plan.json",
        {"status": "ready_for_compose"},
    )
    report = _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {
            "status": "rendered",
            "dry_run": False,
            "final_edit_plan_path": str(final_edit),
            "output_path": str(output_path),
            "burned_subtitles": True,
            "mixed_audio": True,
            "mixed_audio_path": str(project_dir / "assets" / "audio" / "mix.wav"),
        },
    )

    status = project_status.inspect_project(project_dir)

    assert status["status"] == "final_render_ready"
    assert status["current_artifact_path"] == str(report)
    assert status["render_output_path"] == str(output_path)
    assert status["render_output_exists"] is True
    assert status["burned_subtitles"] is True
    assert status["mixed_audio"] is True
    assert status["next_commands"][0]["name"] == "review_final_render"
    assert status["next_commands"][0]["script"] == "scripts/review_reference_final.py"
    assert str(report) in status["next_commands"][0]["command"]
    assert str(project_dir) in status["next_commands"][0]["command"]
    assert status["next_commands"][1]["name"] == "export_delivery_package"
    assert status["next_commands"][1]["script"] == "scripts/export_reference_delivery.py"
    assert "--approval-phrase 'APPROVE FINAL DELIVERY'" in status["next_commands"][1]["command"]
    assert str(report) in status["next_commands"][1]["command"]


def test_project_status_reports_final_review_ready_for_delivery(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")
    project_dir = tmp_path / "project"
    output_path = project_dir / "renders" / "reference-final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake mp4")
    render_report = _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {
            "status": "rendered",
            "dry_run": False,
            "output_path": str(output_path),
            "burned_subtitles": True,
            "mixed_audio": True,
        },
    )
    review_report = _write_json(
        project_dir / "artifacts" / "reference-final-review" / "sample-final-review.json",
        {
            "status": "final_review_ready_for_delivery",
            "source_render_report_path": str(render_report),
            "render": {
                "output_path": str(output_path),
                "burned_subtitles": True,
                "mixed_audio": True,
            },
        },
    )

    status = project_status.inspect_project(project_dir)

    assert status["status"] == "final_review_ready_for_delivery"
    assert status["current_artifact_path"] == str(review_report)
    assert status["render_output_path"] == str(output_path)
    assert status["render_output_exists"] is True
    assert status["burned_subtitles"] is True
    assert status["mixed_audio"] is True
    assert status["next_commands"][0]["name"] == "export_delivery_package"
    assert status["next_commands"][0]["script"] == "scripts/export_reference_delivery.py"
    assert str(render_report) in status["next_commands"][0]["command"]
    assert "--approval-phrase 'APPROVE FINAL DELIVERY'" in status["next_commands"][0]["command"]


def test_project_status_reports_delivery_exported_when_manifest_exists(tmp_path):
    project_status = importlib.import_module("scripts.reference_project_status")
    project_dir = tmp_path / "project"
    manifest = _write_json(
        project_dir / "deliveries" / "reference-final" / "delivery-manifest.json",
        {
            "status": "ready_for_distribution",
            "delivery_dir": str(project_dir / "deliveries" / "reference-final"),
            "video_path": str(project_dir / "deliveries" / "reference-final" / "reference-final.mp4"),
        },
    )

    status = project_status.inspect_project(project_dir)

    assert status["status"] == "delivery_exported"
    assert status["current_artifact_path"] == str(manifest)
    assert status["delivery_dir"] == str(project_dir / "deliveries" / "reference-final")
    assert status["next_commands"] == [
        {
            "name": "archive_or_upload_delivery",
            "script": "manual_review",
            "command": "Archive or upload the delivery folder after final business approval.",
        }
    ]
