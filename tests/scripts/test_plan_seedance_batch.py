from __future__ import annotations

import json
from pathlib import Path

from scripts import plan_seedance_batch
from tools.base_tool import ToolResult


def _production_plan() -> dict:
    return {
        "version": "1.0",
        "status": "ready_for_production",
        "target_mode": "seedance",
        "source": {"input": "reference.mp4", "local_video_path": "reference.mp4"},
        "seedance_constraints": {
            "duration": "10",
            "resolution": "480p",
            "batch_size": 1,
            "max_duration_seconds": 15,
            "max_generations_per_batch": 5,
        },
        "scenes": [
            {
                "scene_id": "s1",
                "script_text": "人工确认文案。",
                "seedance_prompt": "竖屏短视频，人物正面口播。",
                "selected_asset_ids": [],
                "selected_assets": [],
            }
        ],
        "approval": {
            "source_package_status": "approved",
            "team_authorized_assets_checked": True,
            "paid_generation_started": False,
        },
    }


def test_main_writes_seedance_batch_dry_run_from_production_plan(tmp_path, capsys):
    plan_path = tmp_path / "production-plan.json"
    plan_path.write_text(json.dumps(_production_plan(), ensure_ascii=False), encoding="utf-8")

    exit_code = plan_seedance_batch.main(
        [
            str(plan_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--provider",
            "runninghub",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    batch_path = Path(payload["json_path"])
    assert batch_path.is_file()
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    assert batch["status"] == "dry_run_ready"
    assert batch["tasks"][0]["provider_tool"] == "runninghub_seedance_video"


def test_main_refuses_paid_generation_without_approval(tmp_path, capsys):
    plan_path = tmp_path / "production-plan.json"
    plan_path.write_text(json.dumps(_production_plan(), ensure_ascii=False), encoding="utf-8")

    exit_code = plan_seedance_batch.main(
        [
            str(plan_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--execute",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "allow_paid_generation" in captured.err


def test_main_executes_single_sample_with_confirmation_phrase(
    monkeypatch, tmp_path, capsys
):
    calls = []

    class FakeProvider:
        def execute(self, inputs):
            calls.append(inputs)
            return ToolResult(
                success=True,
                data={"task_id": "task-1", "output_path": inputs["output_path"]},
                artifacts=[inputs["output_path"]],
                cost_usd=0.25,
            )

    monkeypatch.setattr(
        "tools.video.seedance_batch._provider_tool",
        lambda provider: FakeProvider(),
    )
    plan_path = tmp_path / "production-plan.json"
    plan_path.write_text(json.dumps(_production_plan(), ensure_ascii=False), encoding="utf-8")

    exit_code = plan_seedance_batch.main(
        [
            str(plan_path),
            "--project-dir",
            str(tmp_path / "project"),
            "--execute",
            "--allow-paid-generation",
            "--approval-phrase",
            "RUN SEEDANCE SAMPLE",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert len(calls) == 1
    payload = json.loads(captured.out)
    assert payload["seedance_batch"]["status"] == "sample_generated"
