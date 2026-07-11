from __future__ import annotations

import asyncio

from backlot import mcp
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
