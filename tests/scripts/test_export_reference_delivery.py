from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_export_reference_delivery_copies_final_assets_and_manifest(tmp_path):
    delivery = importlib.import_module("scripts.export_reference_delivery")
    project_dir = tmp_path / "project"
    final_video = project_dir / "renders" / "reference-final.mp4"
    final_video.parent.mkdir(parents=True, exist_ok=True)
    final_video.write_bytes(b"fake mp4")
    subtitle = project_dir / "assets" / "subtitles" / "reference-final.srt"
    subtitle.parent.mkdir(parents=True, exist_ok=True)
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
    final_edit = _write_json(
        project_dir / "artifacts" / "reference-final-edit" / "sample-final-edit-plan.json",
        {"status": "ready_for_compose", "total_duration": 15},
    )
    report = _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {
            "status": "rendered",
            "dry_run": False,
            "output_path": str(final_video),
            "final_edit_plan_path": str(final_edit),
            "subtitle_path": str(subtitle),
            "burned_subtitles": True,
            "mixed_audio": False,
            "clip_count": 1,
            "total_duration": 15,
        },
    )
    report.with_suffix(".md").write_text("# Render Report\n", encoding="utf-8")

    result = delivery.export_delivery_package(
        project_dir=project_dir,
        render_report_path=report,
        reviewer="operator",
        approval_phrase="APPROVE FINAL DELIVERY",
    )

    delivery_dir = Path(result["delivery_dir"])
    assert result["status"] == "ready_for_distribution"
    assert (delivery_dir / "reference-final.mp4").read_bytes() == b"fake mp4"
    assert (delivery_dir / "render-report.json").is_file()
    assert (delivery_dir / "render-report.md").is_file()
    assert (delivery_dir / "final-edit-plan.json").is_file()
    assert (delivery_dir / "subtitles.srt").is_file()
    assert (delivery_dir / "README.md").is_file()
    manifest = json.loads((delivery_dir / "delivery-manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "ready_for_distribution"
    assert manifest["human_review"]["reviewer"] == "operator"
    assert manifest["render"]["output_path"] == str(final_video)
    assert manifest["render"]["burned_subtitles"] is True
    assert "reference-final.mp4" in {item["filename"] for item in manifest["included_files"]}


def test_export_reference_delivery_requires_human_approval_phrase(tmp_path):
    delivery = importlib.import_module("scripts.export_reference_delivery")
    project_dir = tmp_path / "project"
    final_video = project_dir / "renders" / "reference-final.mp4"
    final_video.parent.mkdir(parents=True, exist_ok=True)
    final_video.write_bytes(b"fake mp4")
    report = _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {
            "status": "rendered",
            "dry_run": False,
            "output_path": str(final_video),
        },
    )

    with pytest.raises(ValueError, match="APPROVE FINAL DELIVERY"):
        delivery.export_delivery_package(
            project_dir=project_dir,
            render_report_path=report,
            reviewer="operator",
            approval_phrase="not approved",
        )


def test_export_reference_delivery_rejects_missing_final_video(tmp_path):
    delivery = importlib.import_module("scripts.export_reference_delivery")
    project_dir = tmp_path / "project"
    report = _write_json(
        project_dir / "artifacts" / "reference-render" / "sample-render-report.json",
        {
            "status": "rendered",
            "dry_run": False,
            "output_path": str(project_dir / "renders" / "missing.mp4"),
        },
    )

    with pytest.raises(ValueError, match="final MP4"):
        delivery.export_delivery_package(
            project_dir=project_dir,
            render_report_path=report,
            reviewer="operator",
            approval_phrase="APPROVE FINAL DELIVERY",
        )
