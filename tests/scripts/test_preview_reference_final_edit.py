from __future__ import annotations

import importlib
import json
from pathlib import Path


def _seedance_batch(project_dir: Path, output_path: Path) -> dict:
    return {
        "version": "1.0",
        "status": "dry_run_ready",
        "dry_run": True,
        "source": {
            "input": "reference.mp4",
            "local_video_path": "reference.mp4",
        },
        "provider": "runninghub",
        "provider_tool": "runninghub_seedance_video",
        "duration": "8",
        "resolution": "480p",
        "tasks": [
            {
                "task_id": "seedance-s1",
                "scene_id": "s1",
                "provider_tool": "runninghub_seedance_video",
                "prompt": "竖屏产品口播，人物面向镜头。",
                "script_text": "人工确认后的文案。",
                "duration": "8",
                "resolution": "480p",
                "output_path": str(output_path),
            }
        ],
        "approval": {
            "paid_generation_started": False,
            "requires_explicit_generation_approval": True,
        },
    }


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_final_edit_preview_reports_missing_generated_clips(tmp_path, capsys):
    final_edit = importlib.import_module("scripts.preview_reference_final_edit")
    project_dir = tmp_path / "project"
    missing_clip = project_dir / "assets" / "video" / "s1-seedance.mp4"
    batch_path = _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        _seedance_batch(project_dir, missing_clip),
    )

    exit_code = final_edit.main([str(batch_path), "--project-dir", str(project_dir)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    markdown = Path(payload["markdown_path"]).read_text(encoding="utf-8")

    assert exit_code == 0
    assert payload["final_edit_plan"]["status"] == "waiting_for_generated_clips"
    assert payload["final_edit_plan"]["missing_clip_count"] == 1
    assert payload["final_edit_plan"]["ready_clip_count"] == 0
    assert "waiting_for_generated_clips" in markdown
    assert str(missing_clip) in markdown


def test_final_edit_preview_reports_ready_when_all_clips_exist(tmp_path, capsys):
    final_edit = importlib.import_module("scripts.preview_reference_final_edit")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1-seedance.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    batch_path = _write_json(
        project_dir / "artifacts" / "sample-seedance-batch-dry-run.json",
        _seedance_batch(project_dir, clip_path),
    )

    exit_code = final_edit.main([str(batch_path), "--project-dir", str(project_dir)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    plan = payload["final_edit_plan"]

    assert exit_code == 0
    assert plan["status"] == "ready_for_compose"
    assert plan["missing_clip_count"] == 0
    assert plan["ready_clip_count"] == 1
    assert plan["timeline"][0]["clip_path"] == str(clip_path)
    assert plan["timeline"][0]["script_text"] == "人工确认后的文案。"
    assert Path(payload["json_path"]).is_file()
    assert Path(payload["markdown_path"]).is_file()


def test_final_edit_preview_resolves_repo_relative_output_path(tmp_path):
    final_edit = importlib.import_module("scripts.preview_reference_final_edit")
    project_dir = tmp_path / "project"
    clip_path = project_dir / "assets" / "video" / "s1-seedance.mp4"
    clip_path.parent.mkdir(parents=True, exist_ok=True)
    clip_path.write_bytes(b"fake mp4")
    batch = _seedance_batch(
        project_dir,
        Path(project_dir.name) / "assets" / "video" / "s1-seedance.mp4",
    )

    plan = final_edit.build_final_edit_plan(
        seedance_batch=batch,
        project_dir=project_dir,
    )

    assert plan["status"] == "ready_for_compose"
    assert plan["missing_clip_count"] == 0
    assert plan["timeline"][0]["clip_path"] == str(clip_path.resolve())
