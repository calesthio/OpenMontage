from __future__ import annotations

import importlib
import json
from pathlib import Path


def _pending_package() -> dict:
    return {
        "version": "1.0",
        "source": {
            "input_type": "local_file",
            "input": "reference.mp4",
            "local_video_path": "reference.mp4",
            "duration_seconds": 8.0,
        },
        "rewrite_draft": {
            "status": "needs_human_edit",
            "text": "原始复刻稿。",
        },
        "editable_inputs": {
            "status": "needs_human_edit",
            "custom_assets": [],
        },
        "scenes": [
            {
                "scene_id": "s1",
                "start": 0.0,
                "end": 8.0,
                "visual_summary": "人物口播开场。",
                "production_inputs": {
                    "status": "needs_human_edit",
                    "script_text": "旧脚本。",
                    "seedance_prompt": "旧提示词。",
                    "selected_assets": [],
                },
            }
        ],
        "approval": {
            "status": "pending_human_review",
            "required_before_production": True,
            "requires_team_authorized_face_or_avatar": True,
            "paid_generation_started": False,
        },
    }


def _approved_package() -> dict:
    package = _pending_package()
    package["editable_inputs"]["status"] = "approved_for_production"
    package["editable_inputs"]["custom_assets"] = [
        {
            "id": "face-ref",
            "type": "image",
            "path": "assets/images/face.png",
            "scene_id": "s1",
            "role": "subject_or_face_reference",
            "authorized": True,
        }
    ]
    package["scenes"][0]["production_inputs"]["script_text"] = "人工确认后的文案。"
    package["scenes"][0]["production_inputs"]["seedance_prompt"] = "竖屏产品口播，人物面向镜头。"
    package["scenes"][0]["production_inputs"]["selected_assets"] = [{"id": "face-ref"}]
    package["approval"]["status"] = "approved"
    package["approval"]["target_mode"] = "seedance"
    return package


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_demo_report_exports_edit_sheet_and_blocks_seedance_until_approval(tmp_path, capsys):
    demo_report = importlib.import_module("scripts.reference_demo_report")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "reference-prompts" / "sample-prompts-reversed-package.json",
        _pending_package(),
    )

    exit_code = demo_report.main([str(project_dir)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    report_path = Path(payload["markdown_report_path"])
    report = report_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert report_path.is_file()
    assert Path(payload["json_report_path"]).is_file()
    assert payload["status"]["status"] == "prompts_reversed_needs_edit"
    assert payload["review_wizard"]["next_step"] == "edit_sheet_ready_for_human"
    assert payload["seedance_preview"]["status"] == "blocked_until_approval"
    assert "Seedance dry-run: blocked until approval" in report
    assert "Paid generation: not started" in report


def test_demo_report_generates_seedance_dry_run_for_approved_package(tmp_path, capsys):
    demo_report = importlib.import_module("scripts.reference_demo_report")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir
        / "artifacts"
        / "reference-review"
        / "sample-seedance-approved-package.json",
        _approved_package(),
    )

    exit_code = demo_report.main(
        [
            str(project_dir),
            "--duration",
            "8",
            "--resolution",
            "720p",
            "--batch-size",
            "1",
            "--provider",
            "runninghub",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    report = Path(payload["markdown_report_path"]).read_text(encoding="utf-8")
    batch_path = Path(payload["seedance_preview"]["seedance_batch_path"])

    assert exit_code == 0
    assert payload["status"]["status"] == "approved_for_production"
    assert payload["seedance_preview"]["dry_run"] is True
    assert payload["seedance_preview"]["paid_generation_started"] is False
    assert payload["final_edit_preview"]["final_edit_plan"]["status"] == "waiting_for_generated_clips"
    assert batch_path.is_file()
    assert "Seedance dry-run: ready" in report
    assert "Final edit: waiting_for_generated_clips" in report
    assert "runninghub_seedance_video" in report
