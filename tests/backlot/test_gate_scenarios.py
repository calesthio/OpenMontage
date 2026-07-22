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


def _proposal_artifact() -> dict:
    from tests.contracts.test_phase0_contracts import sample_artifact
    return sample_artifact("proposal_packet")


def _approve_predecessors(tmp_path, project_id, pipeline_type, *stages) -> None:
    """Write each given stage as completed+approved, in order, so a later
    write to a stage past them satisfies the sequence-gate check."""
    from lib.checkpoint import CANONICAL_STAGE_ARTIFACTS
    from tests.contracts.test_phase0_contracts import sample_artifact

    for predecessor in stages:
        write_checkpoint(
            tmp_path, project_id, predecessor, "completed",
            artifacts={CANONICAL_STAGE_ARTIFACTS[predecessor]: sample_artifact(
                CANONICAL_STAGE_ARTIFACTS[predecessor]
            )},
            pipeline_type=pipeline_type,
            human_approved=True,
        )


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
    _approve_predecessors(tmp_path, "film", "cinematic", "proposal", "script", "scene_plan")
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


def test_later_stage_blocked_while_earlier_gated_stage_unapproved(tmp_path):
    """A gated earlier stage sitting unapproved must block advancement to a
    later stage — the sequence gate, not just the same-stage gate."""
    write_checkpoint(
        tmp_path, "film", "proposal", "awaiting_human",
        {"proposal_packet": _proposal_artifact()},
        pipeline_type="cinematic",
    )
    # proposal is still awaiting_human/unapproved — script must be blocked,
    # both as a completed write and as a bare awaiting_human draft.
    with pytest.raises(CheckpointValidationError, match="SEQUENCE GATE VIOLATION"):
        write_checkpoint(
            tmp_path, "film", "script", "completed",
            {"script": _script_artifact()},
            pipeline_type="cinematic",
            human_approved=True,
        )
    with pytest.raises(CheckpointValidationError, match="SEQUENCE GATE VIOLATION"):
        write_checkpoint(
            tmp_path, "film", "script", "awaiting_human",
            {"script": _script_artifact()},
            pipeline_type="cinematic",
        )


def test_in_progress_write_is_not_blocked_by_sequence_gate(tmp_path):
    """in_progress heartbeats/partial-progress refreshes must stay unblocked
    even with an unapproved earlier gated stage — only real stage
    advancement (awaiting_human/completed) is sequence-gated."""
    write_checkpoint(
        tmp_path, "film", "proposal", "awaiting_human",
        {"proposal_packet": _proposal_artifact()},
        pipeline_type="cinematic",
    )
    path = write_checkpoint(
        tmp_path, "film", "assets", "in_progress",
        {},
        pipeline_type="cinematic",
    )
    assert path.exists()


def test_sequence_gate_clears_once_predecessor_is_approved(tmp_path):
    """Approving the blocking predecessor unblocks the later stage."""
    write_checkpoint(
        tmp_path, "film", "proposal", "awaiting_human",
        {"proposal_packet": _proposal_artifact()},
        pipeline_type="cinematic",
    )
    with pytest.raises(CheckpointValidationError, match="SEQUENCE GATE VIOLATION"):
        write_checkpoint(
            tmp_path, "film", "script", "awaiting_human",
            {"script": _script_artifact()},
            pipeline_type="cinematic",
        )
    write_checkpoint(
        tmp_path, "film", "proposal", "completed",
        {"proposal_packet": _proposal_artifact()},
        pipeline_type="cinematic",
        human_approved=True,
    )
    path = write_checkpoint(
        tmp_path, "film", "script", "awaiting_human",
        {"script": _script_artifact()},
        pipeline_type="cinematic",
    )
    assert path.exists()
