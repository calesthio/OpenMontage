from pathlib import Path

from tools.base_tool import ToolResult
from tools.base_tool import ToolStatus
from tools.video.seedance_batch import SeedanceBatch


def _production_plan(scene_count: int = 2, batch_size: int = 2) -> dict:
    return {
        "version": "1.0",
        "status": "ready_for_production",
        "target_mode": "seedance",
        "source": {
            "input": "reference.mp4",
            "local_video_path": "reference.mp4",
        },
        "seedance_constraints": {
            "duration": "12",
            "resolution": "720p",
            "batch_size": batch_size,
            "max_duration_seconds": 15,
            "max_generations_per_batch": 5,
        },
        "scenes": [
            {
                "scene_id": f"s{index}",
                "script_text": f"第 {index} 条人工确认文案。",
                "seedance_prompt": f"竖屏短视频，第 {index} 条镜头，人物面向镜头。",
                "selected_asset_ids": ["face-ref"],
                "selected_assets": [
                    {
                        "id": "face-ref",
                        "type": "image",
                        "path": "assets/images/face.png",
                        "authorized": True,
                    }
                ],
                "source_timing": {"start": float(index - 1), "end": float(index)},
            }
            for index in range(1, scene_count + 1)
        ],
        "approval": {
            "source_package_status": "approved",
            "team_authorized_assets_checked": True,
            "paid_generation_started": False,
        },
    }


def test_seedance_batch_dry_run_builds_provider_tasks(tmp_path):
    project_dir = tmp_path / "project"
    result = SeedanceBatch().execute(
        {
            "project_dir": str(project_dir),
            "production_plan": _production_plan(scene_count=2, batch_size=2),
            "dry_run": True,
        }
    )

    assert result.success, result.error
    batch = result.data["seedance_batch"]
    assert batch["status"] == "dry_run_ready"
    assert batch["dry_run"] is True
    assert batch["provider_tool"] == "runninghub_seedance_video"
    assert len(batch["tasks"]) == 2

    first_task = batch["tasks"][0]
    assert first_task["scene_id"] == "s1"
    assert first_task["prompt"].startswith("竖屏短视频，第 1 条")
    assert first_task["duration"] == "12"
    assert first_task["resolution"] == "720p"
    assert first_task["aspect_ratio"] == "9:16"
    assert first_task["image_paths"] == [str(project_dir / "assets/images/face.png")]
    assert first_task["output_path"] == str(project_dir / "assets/video/s1-seedance.mp4")
    assert Path(result.data["json_path"]).is_file()
    assert result.artifacts == [result.data["json_path"]]


def test_seedance_batch_respects_single_batch_limit_and_reports_skipped_scenes(tmp_path):
    result = SeedanceBatch().execute(
        {
            "project_dir": str(tmp_path / "project"),
            "production_plan": _production_plan(scene_count=3, batch_size=2),
        }
    )

    assert result.success, result.error
    batch = result.data["seedance_batch"]
    assert [task["scene_id"] for task in batch["tasks"]] == ["s1", "s2"]
    assert batch["skipped_scene_ids"] == ["s3"]
    assert batch["batch_size"] == 2


def test_seedance_batch_rejects_invalid_seedance_constraints(tmp_path):
    plan = _production_plan(batch_size=6)

    result = SeedanceBatch().execute(
        {
            "project_dir": str(tmp_path),
            "production_plan": plan,
        }
    )

    assert not result.success
    assert "at most 5" in result.error


def test_seedance_batch_rejects_non_seedance_plan(tmp_path):
    plan = _production_plan()
    plan["target_mode"] = "digital_human"

    result = SeedanceBatch().execute(
        {
            "project_dir": str(tmp_path),
            "production_plan": plan,
        }
    )

    assert not result.success
    assert "seedance" in result.error


def test_seedance_batch_rejects_hybrid_plan_in_reference_v1(tmp_path):
    plan = _production_plan()
    plan["target_mode"] = "hybrid"

    result = SeedanceBatch().execute(
        {
            "project_dir": str(tmp_path),
            "production_plan": plan,
        }
    )

    assert not result.success
    assert "seedance-only" in result.error


def test_seedance_batch_refuses_paid_generation_without_explicit_approval(tmp_path):
    result = SeedanceBatch().execute(
        {
            "project_dir": str(tmp_path),
            "production_plan": _production_plan(),
            "dry_run": False,
        }
    )

    assert not result.success
    assert "allow_paid_generation" in result.error


def test_seedance_batch_refuses_sample_execution_without_confirmation_phrase(tmp_path):
    result = SeedanceBatch().execute(
        {
            "project_dir": str(tmp_path / "project"),
            "production_plan": _production_plan(),
            "dry_run": False,
            "allow_paid_generation": True,
            "sample_only": True,
        }
    )

    assert not result.success
    assert "approval_phrase" in result.error


def test_seedance_batch_executes_one_sample_after_explicit_approval(
    monkeypatch, tmp_path
):
    calls = []

    class FakeProvider:
        def execute(self, inputs):
            calls.append(inputs)
            return ToolResult(
                success=True,
                data={
                    "provider": "runninghub",
                    "task_id": "task-1",
                    "output_path": inputs["output_path"],
                    "cost_usd": 0.25,
                },
                artifacts=[inputs["output_path"]],
                cost_usd=0.25,
                model=inputs["model_variant"],
            )

    monkeypatch.setattr(
        "tools.video.seedance_batch._provider_tool",
        lambda provider: FakeProvider(),
    )

    project_dir = tmp_path / "project"
    result = SeedanceBatch().execute(
        {
            "project_dir": str(project_dir),
            "production_plan": _production_plan(scene_count=3, batch_size=3),
            "dry_run": False,
            "allow_paid_generation": True,
            "sample_only": True,
            "approval_phrase": "RUN SEEDANCE SAMPLE",
        }
    )

    assert result.success, result.error
    assert len(calls) == 1
    assert calls[0]["prompt"].startswith("竖屏短视频，第 1 条")
    assert calls[0]["duration"] == "12"
    assert calls[0]["resolution"] == "720p"
    assert calls[0]["output_path"] == str(project_dir / "assets/video/s1-seedance.mp4")

    batch = result.data["seedance_batch"]
    assert batch["status"] == "sample_generated"
    assert batch["dry_run"] is False
    assert batch["executed_task"]["scene_id"] == "s1"
    assert batch["execution_result"]["task_id"] == "task-1"
    assert batch["approval"]["paid_generation_started"] is True
    assert Path(result.data["json_path"]).is_file()
    assert result.artifacts == [
        result.data["json_path"],
        str(project_dir / "assets/video/s1-seedance.mp4"),
    ]


def test_seedance_batch_tool_is_available_without_external_dependencies():
    assert SeedanceBatch().get_status() == ToolStatus.AVAILABLE
