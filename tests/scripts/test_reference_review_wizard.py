from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _package() -> dict:
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
                    "asset_slots": [
                        {
                            "slot": "subject_or_face_reference",
                            "type": "image",
                            "description": "团队授权人脸图。",
                        }
                    ],
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


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_wizard_exports_edit_sheet_when_no_sheet_is_provided(tmp_path, capsys):
    wizard = importlib.import_module("scripts.reference_review_wizard")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "reference-prompts" / "sample-prompts-reversed-package.json",
        _package(),
    )

    exit_code = wizard.main([str(project_dir)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    edit_sheet_path = Path(payload["edit_sheet"]["path"])

    assert exit_code == 0
    assert payload["status"]["status"] == "prompts_reversed_needs_edit"
    assert payload["next_step"] == "edit_sheet_ready_for_human"
    assert edit_sheet_path.is_file()
    assert payload["safety"]["paid_generation_started"] is False
    assert payload["safety"]["approved_package_written"] is False


def test_wizard_validates_applies_and_previews_edit_sheet(tmp_path, capsys):
    wizard = importlib.import_module("scripts.reference_review_wizard")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "reference-prompts" / "sample-prompts-reversed-package.json",
        _package(),
    )
    face_path = tmp_path / "face.png"
    face_path.write_bytes(b"fake face")
    edit_sheet_path = _write_json(
        tmp_path / "edit-sheet.json",
        {
            "rewrite_text": "人工确认后的复刻稿。",
            "scene_edits": [
                {
                    "scene_id": "s1",
                    "script_text": "前三秒提出痛点，然后给出解决方案。",
                    "seedance_prompt": "竖屏近景口播，干净背景，轻微推近。",
                }
            ],
            "assets": [
                {
                    "path": str(face_path),
                    "scene_id": "s1",
                    "id": "face-ref",
                    "role": "subject_or_face_reference",
                    "authorized": True,
                }
            ],
        },
    )

    exit_code = wizard.main([str(project_dir), "--edit-sheet", str(edit_sheet_path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    output_package_path = Path(payload["applied_edit_sheet"]["replication_package_path"])
    output_package = json.loads(output_package_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["edit_sheet_validation"]["valid"] is True
    assert payload["approval_preview"]["ready_to_approve"] is True
    assert payload["approval_preview"]["seedance_constraints"]["duration"] == "15"
    assert output_package_path.is_file()
    assert output_package["scenes"][0]["production_inputs"]["selected_assets"][0]["id"] == "face-ref"
    assert payload["safety"]["paid_generation_started"] is False
    assert payload["safety"]["approved_package_written"] is False
    assert not (project_dir / "artifacts" / "reference-review").exists()


def test_wizard_rejects_digital_human_target_mode_in_v1(tmp_path):
    wizard = importlib.import_module("scripts.reference_review_wizard")
    project_dir = tmp_path / "project"
    _write_json(
        project_dir / "artifacts" / "reference-prompts" / "sample-prompts-reversed-package.json",
        _package(),
    )

    with pytest.raises(SystemExit) as exc_info:
        wizard.main([str(project_dir), "--target-mode", "digital_human"])

    assert exc_info.value.code == 2
