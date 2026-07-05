from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import approve_reference_package
from tools.analysis.reference_review_approval import APPROVAL_PHRASE


def _edited_package() -> dict:
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
                    "script_text": "人工确认后的文案。",
                    "seedance_prompt": "竖屏产品口播，人物面向镜头。",
                    "selected_assets": [{"id": "face-ref"}],
                },
            }
        ],
        "approval": {
            "status": "pending_human_review",
            "required_before_production": True,
            "requires_team_authorized_face_or_avatar": True,
        },
    }


def test_main_writes_approved_reference_package(tmp_path, capsys):
    package_path = tmp_path / "replication-package.json"
    package_path.write_text(json.dumps(_edited_package(), ensure_ascii=False), encoding="utf-8")

    exit_code = approve_reference_package.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--target-mode",
            "seedance",
            "--reviewer",
            "operator",
            "--approval-phrase",
            APPROVAL_PHRASE,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    approved_path = Path(payload["approved_package_path"])
    assert approved_path.is_file()
    assert payload["approved_package"]["approval"]["status"] == "approved"


def test_main_refuses_invalid_review(tmp_path, capsys):
    package = _edited_package()
    package["scenes"][0]["production_inputs"]["script_text"] = ""
    package_path = tmp_path / "replication-package.json"
    package_path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")

    exit_code = approve_reference_package.main(
        [
            str(package_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--reviewer",
            "operator",
            "--approval-phrase",
            APPROVAL_PHRASE,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "script_text" in captured.err


def test_main_rejects_digital_human_target_mode_in_v1(tmp_path):
    package_path = tmp_path / "replication-package.json"
    package_path.write_text(json.dumps(_edited_package(), ensure_ascii=False), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        approve_reference_package.main(
            [
                str(package_path),
                "--project-dir",
                str(tmp_path / "project"),
                "--target-mode",
                "digital_human",
                "--reviewer",
                "operator",
                "--approval-phrase",
                APPROVAL_PHRASE,
            ]
        )

    assert exc_info.value.code == 2
