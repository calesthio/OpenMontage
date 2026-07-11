from __future__ import annotations

import asyncio
import json

from backlot import mcp
from backlot.state import load_board_state
from lib.checkpoint import init_project, write_checkpoint


def test_mcp_asset_review_returns_in_progress_without_reentering_jobs(monkeypatch, tmp_path):
    project_id = "asset-review-in-progress"
    init_project(project_id, title="Review", pipeline_type="cinematic", pipeline_dir=tmp_path)
    write_checkpoint(tmp_path, project_id, "assets", "in_progress", {}, pipeline_type="cinematic")
    monkeypatch.setattr(mcp, "PROJECTS_DIR", tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("approve_asset_review must not re-enter while assets are in progress")

    monkeypatch.setattr(mcp.jobs, "approve_asset_review", fail_if_called)

    result = asyncio.run(
        mcp._approve_asset_review(
            {"project_id": project_id, "confirm_asset_review_passed": True},
            "https://ray.example",
            None,
        )
    )

    assert result["ok"] is True
    assert result["status"] == "assets_already_in_progress"
    assert result["monitor_tool"] == "ray_get_project_outputs"
    assert result["workflow"]["current_stage"] == "assets"


def test_mcp_asset_review_queues_background_work(monkeypatch, tmp_path):
    project_id = "asset-review-queued"
    init_project(project_id, title="Review", pipeline_type="cinematic", pipeline_dir=tmp_path)
    asset_manifest = {"version": "1.0", "assets": [], "total_cost_usd": 0, "metadata": {}}
    write_checkpoint(
        tmp_path,
        project_id,
        "assets",
        "awaiting_human",
        {"asset_manifest": asset_manifest},
        pipeline_type="cinematic",
    )
    monkeypatch.setattr(mcp, "PROJECTS_DIR", tmp_path)

    created = []

    def fake_create_task(coro):
        created.append(coro)
        return object()

    monkeypatch.setattr(mcp.asyncio, "create_task", fake_create_task)

    result = asyncio.run(
        mcp._approve_asset_review(
            {"project_id": project_id, "confirm_asset_review_passed": True},
            "https://ray.example",
            None,
        )
    )
    for coro in created:
        coro.close()

    assert result["ok"] is True
    assert result["status"] == "asset_review_queued"
    assert result["monitor_arguments"] == {"project_id": project_id}
    assert len(created) == 1


def test_mcp_hides_final_render_until_render_qa_passes(monkeypatch, tmp_path):
    project_id = "compose-final-race"
    project_dir = init_project(project_id, title="Race", pipeline_type="cinematic", pipeline_dir=tmp_path)
    write_checkpoint(tmp_path, project_id, "compose", "in_progress", {}, pipeline_type="cinematic")
    monkeypatch.setattr(mcp, "PROJECTS_DIR", tmp_path)

    render_path = project_dir / "renders" / "final.mp4"
    render_path.write_bytes(b"not-a-real-video")

    state = load_board_state(project_dir)
    workflow = mcp._mcp_workflow(project_id, state, "https://ray.example", include_events=False)

    assert workflow["final_render"] is None
    assert workflow["media_outputs"]["renders"] == []
    assert all(action.get("type") != "download_final_mp4" for action in workflow["next_actions"])

    artifacts_dir = project_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    render_report = {
        "version": "1.0",
        "outputs": [{"path": "renders/final.mp4", "format": "mp4"}],
        "metadata": {"qa_gate_status": "failed"},
    }
    (artifacts_dir / "render_report.json").write_text(json.dumps(render_report), encoding="utf-8")
    state = load_board_state(project_dir)
    workflow = mcp._mcp_workflow(project_id, state, "https://ray.example", include_events=False)

    assert workflow["final_render"] is None
    assert workflow["media_outputs"]["renders"] == []

    render_report["metadata"]["qa_gate_status"] = "passed"
    (artifacts_dir / "render_report.json").write_text(json.dumps(render_report), encoding="utf-8")
    state = load_board_state(project_dir)
    workflow = mcp._mcp_workflow(project_id, state, "https://ray.example", include_events=False)

    assert workflow["final_render"]["url"] == "https://ray.example/media/compose-final-race/renders/final.mp4"
    assert workflow["media_outputs"]["renders"][0]["url"] == workflow["final_render"]["url"]
    assert workflow["next_actions"] == [
        {
            "type": "download_final_mp4",
            "url": "https://ray.example/media/compose-final-race/renders/final.mp4",
            "label": "Final render MP4",
        }
    ]
