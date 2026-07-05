from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _ready_package() -> dict:
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
            "custom_assets": [
                {
                    "id": "face-ref",
                    "type": "image",
                    "path": "assets/images/face.png",
                    "scene_id": "s1",
                    "role": "subject_or_face_reference",
                    "authorized": True,
                }
            ],
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


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_main_reports_ready_for_seedance_approval(tmp_path, capsys):
    preview_approval = importlib.import_module("scripts.preview_reference_approval")
    package_path = _write_json(tmp_path / "package.json", _ready_package())

    exit_code = preview_approval.main(
        [
            str(package_path),
            "--target-mode",
            "seedance",
            "--duration",
            "15",
            "--resolution",
            "480p",
            "--batch-size",
            "1",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ready_to_approve"] is True
    assert payload["target_mode"] == "seedance"
    assert payload["summary"]["scene_count"] == 1
    assert payload["summary"]["selected_asset_count"] == 1
    assert payload["errors"] == []
    assert payload["seedance_constraints"]["duration"] == "15"


def test_main_reports_missing_prompt_and_unauthorized_asset(tmp_path, capsys):
    preview_approval = importlib.import_module("scripts.preview_reference_approval")
    package = _ready_package()
    package["scenes"][0]["production_inputs"]["seedance_prompt"] = " "
    package["editable_inputs"]["custom_assets"][0]["authorized"] = False
    package_path = _write_json(tmp_path / "package.json", package)

    exit_code = preview_approval.main(
        [
            str(package_path),
            "--target-mode",
            "seedance",
            "--batch-size",
            "6",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    joined_errors = " ".join(payload["errors"])

    assert exit_code == 1
    assert payload["ready_to_approve"] is False
    assert "seedance_prompt" in joined_errors
    assert "team-authorized" in joined_errors
    assert "at most 5" in joined_errors
    assert payload["summary"]["unauthorized_asset_count"] == 1


def test_main_blocks_when_required_face_asset_is_missing(tmp_path, capsys):
    preview_approval = importlib.import_module("scripts.preview_reference_approval")
    package = _ready_package()
    package["editable_inputs"]["custom_assets"] = [
        {
            "id": "product-ref",
            "type": "image",
            "path": "assets/images/product.png",
            "scene_id": "s1",
            "role": "product_or_brand_reference",
            "authorized": True,
        }
    ]
    package["scenes"][0]["production_inputs"]["selected_assets"] = [
        {"id": "product-ref"}
    ]
    package_path = _write_json(tmp_path / "package.json", package)

    exit_code = preview_approval.main(
        [
            str(package_path),
            "--target-mode",
            "seedance",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["ready_to_approve"] is False
    assert "face/presenter" in " ".join(payload["errors"])


def test_main_does_not_write_approved_package(tmp_path, capsys):
    preview_approval = importlib.import_module("scripts.preview_reference_approval")
    package_path = _write_json(tmp_path / "package.json", _ready_package())
    project_dir = tmp_path / "project"

    exit_code = preview_approval.main(
        [
            str(package_path),
            "--target-mode",
            "seedance",
            "--project-dir",
            str(project_dir),
        ]
    )

    capsys.readouterr()
    assert exit_code == 0
    assert not (project_dir / "artifacts" / "reference-review").exists()


def test_main_rejects_digital_human_target_mode_in_v1(tmp_path):
    preview_approval = importlib.import_module("scripts.preview_reference_approval")
    package_path = _write_json(tmp_path / "package.json", _ready_package())

    with pytest.raises(SystemExit) as exc_info:
        preview_approval.main([str(package_path), "--target-mode", "digital_human"])

    assert exc_info.value.code == 2
