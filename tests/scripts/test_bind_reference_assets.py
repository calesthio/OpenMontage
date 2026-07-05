from __future__ import annotations

import json
from pathlib import Path

from scripts import bind_reference_assets


def _pending_package() -> dict:
    return {
        "version": "1.0",
        "source": {
            "input_type": "local_file",
            "input": "reference.mp4",
            "local_video_path": "reference.mp4",
            "duration_seconds": 8.0,
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
                    "script_text": "人工确认后的文案。",
                    "seedance_prompt": "竖屏产品口播，人物面向镜头。",
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


def test_main_imports_and_binds_asset(tmp_path, capsys):
    package_path = tmp_path / "replication-package.json"
    package_path.write_text(json.dumps(_pending_package(), ensure_ascii=False), encoding="utf-8")
    source = tmp_path / "face.png"
    source.write_bytes(b"fake image")

    exit_code = bind_reference_assets.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--asset",
            str(source),
            "s1",
            "subject_or_face_reference",
            "face-ref",
            "--authorized",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    bound_path = Path(payload["replication_package_path"])
    assert bound_path.is_file()
    package = json.loads(bound_path.read_text(encoding="utf-8"))
    assert package["editable_inputs"]["custom_assets"][0]["id"] == "face-ref"
    assert package["scenes"][0]["production_inputs"]["selected_assets"][0]["path"].endswith(
        "face.png"
    )
