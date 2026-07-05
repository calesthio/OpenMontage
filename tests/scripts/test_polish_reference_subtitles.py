from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_plan(project_dir: Path, text: str) -> Path:
    plan = {
        "version": "1.0",
        "status": "ready_for_compose",
        "timeline": [
            {
                "order": 1,
                "scene_id": "s1",
                "timeline_start": 0.0,
                "timeline_end": 8.0,
                "duration": 8.0,
                "subtitle_text": text,
            }
        ],
    }
    path = project_dir / "artifacts" / "reference-final-edit" / "demo-final-edit-plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return path


def test_polish_reference_subtitles_dry_run_writes_review_artifact(tmp_path, capsys):
    polish = importlib.import_module("scripts.polish_reference_subtitles")
    project_dir = tmp_path / "project"
    plan_path = _write_plan(
        project_dir,
        "在这些案子上面，我积累了充足的实战经验。如果你身边刚好缺一位靠谱的律师朋友。",
    )

    exit_code = polish.main([str(plan_path), "--project-dir", str(project_dir)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    artifact_path = Path(payload["subtitle_polish_plan_path"])
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert artifact_path.is_file()
    assert artifact["provider"] == "doubao"
    assert artifact["api_called"] is False
    assert artifact["timeline"][0]["scene_id"] == "s1"
    assert artifact["timeline"][0]["cue_count"] >= 3
    assert artifact["timeline"][0]["cues"][0]["start"] == 0
    assert artifact["timeline"][0]["cues"][-1]["end"] == 8


def test_polish_reference_subtitles_blocks_live_without_paid_approval(tmp_path, capsys):
    polish = importlib.import_module("scripts.polish_reference_subtitles")
    project_dir = tmp_path / "project"
    plan_path = _write_plan(project_dir, "人工确认后的口播文案。")

    exit_code = polish.main([str(plan_path), "--project-dir", str(project_dir), "--live"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "--allow-paid-api" in captured.err
