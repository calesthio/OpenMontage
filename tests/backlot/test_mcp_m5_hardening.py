from __future__ import annotations

import json
import time

import pytest

from backlot import jobs, mcp
from backlot.state import load_board_state
from lib.checkpoint import init_project, write_checkpoint


def _write_artifact(project_dir, filename: str, data: dict) -> None:
    path = project_dir / "artifacts" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_mcp_workflow_surfaces_spend_status_and_cancel_action(monkeypatch, tmp_path):
    project_id = "m5-progress"
    project_dir = init_project(project_id, title="M5", pipeline_type="cinematic", pipeline_dir=tmp_path)
    monkeypatch.setattr(mcp, "PROJECTS_DIR", tmp_path)

    _write_artifact(project_dir, "job_request.json", {"version": "1.0", "project_id": project_id, "budget_cap_usd": 5.0})
    _write_artifact(project_dir, "cost_log.json", {"version": "1.0", "budget_total_usd": 5.0, "budget_spent_usd": 0.04})
    _write_artifact(project_dir, "scene_plan.json", {
        "version": "1.0",
        "scenes": [
            {"id": "scene1", "description": "One"},
            {"id": "scene2", "description": "Two"},
            {"id": "scene3", "description": "Three"},
        ],
    })
    _write_artifact(project_dir, "asset_manifest.json", {
        "version": "1.0",
        "assets": [],
        "total_cost_usd": 0.7,
        "metadata": {"generation_runs": [{"scene_id": "scene1", "selected_provider": "grok"}]},
    })
    write_checkpoint(
        tmp_path,
        project_id,
        "assets",
        "in_progress",
        {},
        pipeline_type="cinematic",
        metadata={"partial_progress": {"completed_scene_ids": ["scene1"]}},
    )
    (project_dir / "events.jsonl").write_text(
        json.dumps({"event": "finish", "success": True, "tool": "music_gen", "cost_usd": 0.05}) + "\n",
        encoding="utf-8",
    )

    workflow = mcp._mcp_workflow(project_id, load_board_state(project_dir), "https://ray.example", include_events=True)

    assert workflow["status"] == "in_progress"
    assert workflow["spend_summary"]["orchestration_llm_usd"] == 0.04
    assert workflow["spend_summary"]["media_generation_usd"] == 0.7
    assert workflow["spend_summary"]["post_production_usd"] == 0.05
    assert workflow["spend_summary"]["total_observed_usd"] == 0.79
    assert "Generating assets: 1/3 clips complete" in workflow["status_message"]
    assert any(action.get("tool") == "ray_cancel_project" for action in workflow["next_actions"])


def test_mcp_cancel_project_writes_cancel_artifact_and_failed_checkpoint(monkeypatch, tmp_path):
    project_id = "m5-cancel"
    project_dir = init_project(project_id, title="M5", pipeline_type="cinematic", pipeline_dir=tmp_path)
    monkeypatch.setattr(mcp, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(mcp.jobs, "PROJECTS_DIR", tmp_path)
    write_checkpoint(tmp_path, project_id, "assets", "in_progress", {}, pipeline_type="cinematic")

    result = mcp._cancel_project({"project_id": project_id, "reason": "client stopped"}, "https://ray.example", None)

    assert result["status"] == "cancel_requested"
    assert result["workflow"]["status"] == "failed"
    assert result["workflow"]["current_stage"] == "assets"
    cancel_request = json.loads((project_dir / "artifacts" / jobs.CANCEL_REQUEST_ARTIFACT).read_text(encoding="utf-8"))
    assert cancel_request["reason"] == "client stopped"
    checkpoint = json.loads((project_dir / "checkpoint_assets.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "failed"
    assert checkpoint["metadata"]["blocker"] == "cancelled_by_user"


def test_video_selector_watchdog_times_out():
    class SlowSelector:
        def execute(self, _inputs):
            time.sleep(0.2)
            return object()

    with pytest.raises(jobs.ProviderCallTimeout):
        jobs._run_video_selector_with_watchdog(SlowSelector(), {"scene_id": "scene1"}, 0.01)
