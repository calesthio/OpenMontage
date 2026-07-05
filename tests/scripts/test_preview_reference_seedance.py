from __future__ import annotations

import json
from pathlib import Path

from scripts import preview_reference_seedance


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


def test_main_chains_package_to_production_plan_and_seedance_dry_run(tmp_path, capsys):
    package_path = tmp_path / "replication-package.json"
    package_path.write_text(
        json.dumps(_approved_package(), ensure_ascii=False),
        encoding="utf-8",
    )

    exit_code = preview_reference_seedance.main(
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
            "--provider",
            "runninghub",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["dry_run"] is True
    assert payload["paid_generation_started"] is False

    production_plan_path = Path(payload["production_plan_path"])
    seedance_batch_path = Path(payload["seedance_batch_path"])
    assert production_plan_path.is_file()
    assert seedance_batch_path.is_file()

    plan = json.loads(production_plan_path.read_text(encoding="utf-8"))
    batch = json.loads(seedance_batch_path.read_text(encoding="utf-8"))
    assert plan["seedance_constraints"]["duration"] == "8"
    assert plan["seedance_constraints"]["resolution"] == "720p"
    assert batch["status"] == "dry_run_ready"
    assert batch["tasks"][0]["provider_tool"] == "runninghub_seedance_video"


def test_main_refuses_unapproved_package_before_preview(tmp_path, capsys):
    package = _approved_package()
    package["approval"]["status"] = "pending_human_review"
    package_path = tmp_path / "replication-package.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")

    exit_code = preview_reference_seedance.main(
        [str(package_path), "--project-dir", str(tmp_path / "project")]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "approved" in captured.err
