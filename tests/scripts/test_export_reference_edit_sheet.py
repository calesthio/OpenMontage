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
        },
        "rewrite_draft": {
            "status": "needs_human_edit",
            "text": "原始复刻稿。",
        },
        "scenes": [
            {
                "scene_id": "s1",
                "start": 0.0,
                "end": 4.0,
                "visual_summary": "人物口播开场。",
                "production_inputs": {
                    "script_text": "旧脚本 1。",
                    "seedance_prompt": "旧提示词 1。",
                    "asset_slots": [
                        {
                            "slot": "subject_or_face_reference",
                            "type": "image",
                            "scene_id": "s1",
                            "description": "团队授权人脸图。",
                        }
                    ],
                },
            },
            {
                "scene_id": "s2",
                "start": 4.0,
                "end": 8.0,
                "visual_summary": "产品展示。",
                "production_inputs": {
                    "script_text": "旧脚本 2。",
                    "seedance_prompt": "旧提示词 2。",
                    "asset_slots": [],
                },
            },
        ],
        "approval": {
            "status": "pending_human_review",
            "required_before_production": True,
        },
    }


def _write_package(path: Path) -> Path:
    path.write_text(json.dumps(_package(), ensure_ascii=False), encoding="utf-8")
    return path


def test_main_exports_edit_sheet_template(tmp_path, capsys):
    export_edit_sheet = importlib.import_module("scripts.export_reference_edit_sheet")
    package_path = _write_package(tmp_path / "package.json")
    project_dir = tmp_path / "project"

    exit_code = export_edit_sheet.main(
        [
            str(package_path),
            "--project-dir",
            str(project_dir),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    sheet_path = Path(payload["edit_sheet_path"])
    sheet = json.loads(sheet_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert sheet_path.is_file()
    assert payload["next_step"] == "apply_reference_edit_sheet"
    assert sheet["rewrite_text"] == "原始复刻稿。"
    assert sheet["scene_edits"][0]["scene_id"] == "s1"
    assert sheet["scene_edits"][0]["script_text"] == "旧脚本 1。"
    assert sheet["scene_edits"][1]["seedance_prompt"] == "旧提示词 2。"
    assert sheet["assets"] == []
    assert sheet["asset_placeholders"][0]["scene_id"] == "s1"
    assert sheet["asset_placeholders"][0]["role"] == "subject_or_face_reference"


def test_main_can_write_to_explicit_output_path(tmp_path, capsys):
    export_edit_sheet = importlib.import_module("scripts.export_reference_edit_sheet")
    package_path = _write_package(tmp_path / "package.json")
    output_path = tmp_path / "team-edit-sheet.json"

    exit_code = export_edit_sheet.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--output-path",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert Path(payload["edit_sheet_path"]) == output_path
    assert output_path.is_file()


def test_main_rejects_approved_package(tmp_path, capsys):
    export_edit_sheet = importlib.import_module("scripts.export_reference_edit_sheet")
    package = _package()
    package["approval"]["status"] = "approved"
    package_path = tmp_path / "approved-package.json"
    package_path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")

    exit_code = export_edit_sheet.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "approved package" in captured.err
