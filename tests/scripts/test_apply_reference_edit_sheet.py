from __future__ import annotations

import importlib
import json
from pathlib import Path


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
        },
    }


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_main_applies_text_and_asset_edit_sheet(tmp_path, capsys):
    apply_edit_sheet = importlib.import_module("scripts.apply_reference_edit_sheet")
    project_dir = tmp_path / "project"
    package_path = _write_json(tmp_path / "package.json", _package())
    face_path = tmp_path / "face.png"
    face_path.write_bytes(b"fake face")
    sheet_path = _write_json(
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

    exit_code = apply_edit_sheet.main(
        [
            str(package_path),
            "--project-dir",
            str(project_dir),
            "--edit-sheet",
            str(sheet_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    output_path = Path(payload["replication_package_path"])
    package = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.is_file()
    assert payload["applied"]["text_edits"] is True
    assert payload["applied"]["assets"] is True
    assert payload["next_step"] == "approve_reference_package"
    assert package["rewrite_draft"]["text"] == "人工确认后的复刻稿。"
    assert package["scenes"][0]["production_inputs"]["seedance_prompt"] == "竖屏近景口播，干净背景，轻微推近。"
    assert package["scenes"][0]["production_inputs"]["selected_assets"][0]["id"] == "face-ref"
    assert package["approval"]["status"] == "pending_human_review"


def test_main_applies_text_only_edit_sheet(tmp_path, capsys):
    apply_edit_sheet = importlib.import_module("scripts.apply_reference_edit_sheet")
    package_path = _write_json(tmp_path / "package.json", _package())
    sheet_path = _write_json(
        tmp_path / "edit-sheet.json",
        {
            "scene_edits": [
                {
                    "scene_id": "s1",
                    "script_text": "只改脚本。",
                }
            ]
        },
    )

    exit_code = apply_edit_sheet.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--edit-sheet",
            str(sheet_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    package = json.loads(Path(payload["replication_package_path"]).read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["applied"]["text_edits"] is True
    assert payload["applied"]["assets"] is False
    assert payload["next_step"] == "bind_reference_assets_or_approve"
    assert package["scenes"][0]["production_inputs"]["script_text"] == "只改脚本。"


def test_main_validate_only_reports_valid_sheet_without_writing(tmp_path, capsys):
    apply_edit_sheet = importlib.import_module("scripts.apply_reference_edit_sheet")
    project_dir = tmp_path / "project"
    package_path = _write_json(tmp_path / "package.json", _package())
    face_path = tmp_path / "face.png"
    face_path.write_bytes(b"fake face")
    sheet_path = _write_json(
        tmp_path / "edit-sheet.json",
        {
            "scene_edits": [
                {
                    "scene_id": "s1",
                    "script_text": "预检脚本。",
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

    exit_code = apply_edit_sheet.main(
        [
            str(package_path),
            "--project-dir",
            str(project_dir),
            "--edit-sheet",
            str(sheet_path),
            "--validate-only",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["errors"] == []
    assert payload["would_apply"]["text_edits"] is True
    assert payload["would_apply"]["assets"] is True
    assert not (project_dir / "artifacts").exists()


def test_main_validate_only_reports_sheet_errors(tmp_path, capsys):
    apply_edit_sheet = importlib.import_module("scripts.apply_reference_edit_sheet")
    package_path = _write_json(tmp_path / "package.json", _package())
    sheet_path = _write_json(
        tmp_path / "edit-sheet.json",
        {
            "scene_edits": [
                {
                    "scene_id": "missing",
                    "script_text": "错误场景。",
                }
            ],
            "assets": [
                {
                    "path": str(tmp_path / "missing.png"),
                    "scene_id": "missing",
                    "id": "face-ref",
                    "role": "subject_or_face_reference",
                    "authorized": False,
                }
            ],
        },
    )

    exit_code = apply_edit_sheet.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--edit-sheet",
            str(sheet_path),
            "--validate-only",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["valid"] is False
    joined_errors = " ".join(payload["errors"])
    assert "Unknown scene_id" in joined_errors
    assert "Asset file not found" in joined_errors
    assert "authorized=true" in joined_errors


def test_main_rejects_empty_edit_sheet(tmp_path, capsys):
    apply_edit_sheet = importlib.import_module("scripts.apply_reference_edit_sheet")
    package_path = _write_json(tmp_path / "package.json", _package())
    sheet_path = _write_json(tmp_path / "edit-sheet.json", {})

    exit_code = apply_edit_sheet.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--edit-sheet",
            str(sheet_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "at least one" in captured.err
