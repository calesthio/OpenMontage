from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import prepare_reference_production


def _approved_package() -> dict:
    return {
        "version": "1.0",
        "source": {
            "input_type": "local_file",
            "input": "reference.mp4",
            "local_video_path": "reference.mp4",
            "duration_seconds": 8.0,
        },
        "editable_inputs": {
            "custom_assets": [
                {
                    "id": "face-ref",
                    "type": "image",
                    "path": "assets/images/face.png",
                    "scene_id": "s1",
                    "role": "subject_or_face_reference",
                    "authorized": True,
                }
            ]
        },
        "scenes": [
            {
                "scene_id": "s1",
                "start": 0.0,
                "end": 8.0,
                "production_inputs": {
                    "script_text": "这是人工确认后的文案。",
                    "seedance_prompt": "竖屏产品口播，人物面向镜头。",
                    "selected_assets": [{"id": "face-ref"}],
                },
            }
        ],
        "approval": {
            "status": "approved",
            "required_before_production": True,
            "requires_team_authorized_face_or_avatar": True,
        },
    }


def test_main_writes_reference_production_plan_from_package_path(tmp_path, capsys):
    package_path = tmp_path / "package.json"
    package_path.write_text(
        json.dumps(_approved_package(), ensure_ascii=False),
        encoding="utf-8",
    )

    exit_code = prepare_reference_production.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--duration",
            "8",
            "--resolution",
            "720p",
            "--batch-size",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    plan_path = Path(payload["json_path"])
    assert plan_path.is_file()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["seedance_constraints"]["duration"] == "8"
    assert plan["seedance_constraints"]["resolution"] == "720p"


def test_main_returns_error_when_package_is_not_approved(tmp_path, capsys):
    package = _approved_package()
    package["approval"]["status"] = "pending_human_review"
    package_path = tmp_path / "package.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")

    exit_code = prepare_reference_production.main(
        [str(package_path), "--project-dir", str(tmp_path / "project")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "approved" in captured.err


def test_main_rejects_digital_human_target_mode_in_v1(tmp_path):
    package_path = tmp_path / "package.json"
    package_path.write_text(json.dumps(_approved_package()), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        prepare_reference_production.main(
            [
                str(package_path),
                "--project-dir",
                str(tmp_path / "project"),
                "--target-mode",
                "digital_human",
            ]
        )

    assert exc_info.value.code == 2
