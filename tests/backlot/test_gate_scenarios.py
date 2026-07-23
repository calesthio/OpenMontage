"""Gate-integrity scenarios for Backlot and checkpoint hardening."""

import json
from pathlib import Path

import pytest

from backlot import state as state_mod
from backlot.state import load_board_state
from lib.checkpoint import CheckpointValidationError, write_checkpoint


def _script_artifact() -> dict:
    return {
        "version": "1.0",
        "title": "Gate Test",
        "total_duration_seconds": 5,
        "sections": [{"id": "s1", "text": "Hello.", "start_seconds": 0, "end_seconds": 5}],
    }


def _manifest_artifact() -> dict:
    return {"version": "1.0", "assets": [], "total_cost_usd": 0.0}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_completed_gated_stage_without_approval_is_rejected(tmp_path):
    with pytest.raises(CheckpointValidationError, match="GATE VIOLATION"):
        write_checkpoint(
            tmp_path,
            "film",
            "script",
            "completed",
            {"script": _script_artifact()},
            pipeline_type="cinematic",
        )


def test_typo_pipeline_type_fails_closed(tmp_path):
    with pytest.raises(CheckpointValidationError, match="Unknown pipeline_type"):
        write_checkpoint(
            tmp_path,
            "film",
            "script",
            "completed",
            {"script": _script_artifact()},
            pipeline_type="cinemtaic",
            human_approved=True,
        )


def test_handwritten_completed_checkpoint_surfaces_gate_skip(tmp_path, monkeypatch):
    monkeypatch.setattr(state_mod, "PROJECTS_DIR", tmp_path)
    project = tmp_path / "film"
    _write(project / "checkpoint_script.json", {
        "version": "1.0",
        "project_id": "film",
        "pipeline_type": "cinematic",
        "stage": "script",
        "status": "completed",
        "timestamp": "2026-07-02T00:00:00Z",
        "artifacts": {"script": _script_artifact()},
    })

    state = load_board_state(project)

    script = next(stage for stage in state["stages"] if stage["name"] == "script")
    assert script["gate_skipped"] is True


def test_awaiting_then_approved_archives_history_without_gate_skip(tmp_path):
    write_checkpoint(
        tmp_path,
        "film",
        "assets",
        "awaiting_human",
        {"asset_manifest": _manifest_artifact()},
        pipeline_type="cinematic",
    )
    write_checkpoint(
        tmp_path,
        "film",
        "assets",
        "completed",
        {"asset_manifest": _manifest_artifact()},
        pipeline_type="cinematic",
        human_approved=True,
    )

    state = load_board_state(tmp_path / "film")

    assets = next(stage for stage in state["stages"] if stage["name"] == "assets")
    assert assets.get("gate_skipped") in (None, False)
    assert assets["versions"] == 2
    assert assets["history_entries"][0]["status"] == "awaiting_human"
