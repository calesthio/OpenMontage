from __future__ import annotations

import json
from pathlib import Path

from scripts import edit_reference_package


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
            "text": "旧复刻稿。",
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


def test_main_edits_rewrite_and_scene_text(tmp_path, capsys):
    package_path = tmp_path / "replication-package.json"
    package_path.write_text(json.dumps(_pending_package(), ensure_ascii=False), encoding="utf-8")

    exit_code = edit_reference_package.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--rewrite-text",
            "人工修改后的复刻稿。",
            "--scene-edit",
            "s1",
            "人工确认后的场景脚本。",
            "竖屏产品口播，人物面向镜头，干净背景。",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    edited_path = Path(payload["replication_package_path"])
    assert edited_path.is_file()
    package = json.loads(edited_path.read_text(encoding="utf-8"))
    assert package["rewrite_draft"]["text"] == "人工修改后的复刻稿。"
    assert package["scenes"][0]["production_inputs"]["script_text"] == "人工确认后的场景脚本。"
    assert package["scenes"][0]["production_inputs"]["seedance_prompt"].startswith("竖屏产品口播")
    assert payload["next_step"] == "bind_reference_assets_or_approve"
