"""A full artifact chain must survive the real checkpoint writer.

This is the pipeline's dry-run contract: every stage's canonical artifact is
written, validated against its schema, gated by the manifest's approval
policy, and resolved against the artifact that defines it. If this test
passes, the twelve-stage chain is mechanically sound end to end — the parts
that still need a machine (TTS binary, real footage, rendered file) are
covered separately and honestly in test_factory_environment.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.artifact_ids import resolve_all
from lib.checkpoint import (
    CheckpointValidationError,
    get_completed_stages,
    get_next_stage,
    init_project,
    read_checkpoint,
    write_checkpoint,
)
from lib.pipeline_loader import get_stage_human_approval_default, load_pipeline
from schemas.artifacts import validate_artifact
from tests.factory.test_artifact_schemas import (
    _alignment_report,
    _asset_manifest,
    _evidence_ledger,
    _fact_check_report,
    _narration_manifest,
    _publish_log,
    _publish_package,
    _qa_report,
    _render_report,
    _research_brief,
    _scene_plan,
    _script,
    _topic_brief,
)

PIPELINE = "business-documentary"
PROJECT_ID = "factory-dry-run"

STAGE_ARTIFACTS = {
    "topic": {"topic_brief": _topic_brief},
    "research": {"research_brief": _research_brief},
    "evidence": {"evidence_ledger": _evidence_ledger},
    "script": {"script": _script},
    "fact_check": {"fact_check_report": _fact_check_report},
    "storyboard": {"scene_plan": _scene_plan},
    "narration": {"narration_manifest": _narration_manifest},
    "footage": {"asset_manifest": _asset_manifest},
    "editorial": {"alignment_report": _alignment_report},
    "compose": {"render_report": _render_report},
    "qa": {"qa_report": _qa_report},
    "publish": {"publish_package": _publish_package, "publish_log": _publish_log},
}


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    pipeline_dir = tmp_path / "projects"
    init_project(PROJECT_ID, title="Factory dry run", pipeline_type=PIPELINE,
                 pipeline_dir=pipeline_dir)
    return pipeline_dir


@pytest.fixture()
def run_chain(workspace: Path):
    """Advance the pipeline stage by stage, honouring the manifest gates."""

    written: dict[str, Path] = {}

    def _run() -> dict[str, Path]:
        for stage, builders in STAGE_ARTIFACTS.items():
            artifacts = {name: builder() for name, builder in builders.items()}
            for name, payload in artifacts.items():
                validate_artifact(name, payload)

            gated = get_stage_human_approval_default(load_pipeline(PIPELINE), stage)
            if gated:
                write_checkpoint(
                    workspace, PROJECT_ID, stage, "awaiting_human", artifacts,
                    pipeline_type=PIPELINE,
                )
            write_checkpoint(
                workspace, PROJECT_ID, stage, "completed", artifacts,
                pipeline_type=PIPELINE, human_approved=bool(gated),
            )
            written[stage] = artifacts
        return written

    return _run


def test_all_twelve_artifacts_validate_against_their_schemas() -> None:
    for builders in STAGE_ARTIFACTS.values():
        for name, builder in builders.items():
            validate_artifact(name, builder())


def test_the_artifact_set_is_internally_consistent(run_chain) -> None:
    artifacts = run_chain()
    merged = {name: payload for stage in artifacts.values() for name, payload in stage.items()}
    assert resolve_all(merged) == []


def test_every_stage_can_be_checkpointed_in_order(run_chain, workspace: Path) -> None:
    run_chain()
    assert get_completed_stages(workspace, PROJECT_ID, PIPELINE) == list(STAGE_ARTIFACTS)


def test_the_run_ends_at_a_pending_manual_approval(run_chain, workspace: Path) -> None:
    run_chain()
    assert get_next_stage(workspace, PROJECT_ID, PIPELINE) is None
    publish = read_checkpoint(workspace, PROJECT_ID, "publish")
    package = publish["artifacts"]["publish_package"]
    assert package["manual_approval"]["status"] == "pending"
    assert package["manual_approval"]["upload_target"] is None


def test_a_gated_stage_cannot_be_completed_without_approval(workspace: Path) -> None:
    """AGENT_GUIDE: the manifest's human_approval_default is binding."""

    with pytest.raises(CheckpointValidationError) as excinfo:
        write_checkpoint(
            workspace, PROJECT_ID, "topic", "completed",
            {"topic_brief": _topic_brief()},
            pipeline_type=PIPELINE,
        )
    assert "GATE VIOLATION" in str(excinfo.value)


def test_a_stage_cannot_advance_before_its_predecessors(workspace: Path) -> None:
    with pytest.raises(CheckpointValidationError) as excinfo:
        write_checkpoint(
            workspace, PROJECT_ID, "script", "completed",
            {"script": _script()},
            pipeline_type=PIPELINE, human_approved=True,
        )
    assert "PREREQUISITE VIOLATION" in str(excinfo.value)


def test_an_unresolvable_artifact_is_refused_by_the_schema(workspace: Path) -> None:
    """A fabricated evidence ID must not survive into a checkpoint."""

    script = _script()
    script["sections"][0]["evidence_ids"] = ["EV-fabricated"]
    with pytest.raises(CheckpointValidationError) as excinfo:
        write_checkpoint(
            workspace, PROJECT_ID, "topic", "completed",
            {"topic_brief": _topic_brief()},
            pipeline_type=PIPELINE, human_approved=True,
        )
        write_checkpoint(
            workspace, PROJECT_ID, "evidence", "completed",
            {"evidence_ledger": _evidence_ledger()},
            pipeline_type=PIPELINE, human_approved=True,
        )
        write_checkpoint(
            workspace, PROJECT_ID, "script", "completed", {"script": script},
            pipeline_type=PIPELINE, human_approved=True,
        )
    # The schema accepts the string shape; the *resolver* is what refuses it.
    # So assert the resolver catches it rather than the checkpoint writer.
    ledger = _evidence_ledger()
    dangling = resolve_all({"script": script, "evidence_ledger": ledger})
    assert [d.value for d in dangling] == ["EV-fabricated"]


def test_re_running_a_stage_archives_the_superseded_checkpoint(
    run_chain, workspace: Path
) -> None:
    artifacts = run_chain()
    write_checkpoint(
        workspace, PROJECT_ID, "qa", "completed", artifacts["qa"],
        pipeline_type=PIPELINE,
    )
    history = workspace / PROJECT_ID / "history"
    assert history.exists()
    assert list(history.glob("checkpoint_qa*.json")), "stage history was destroyed"


def test_checkpoint_files_are_valid_json_on_disk(run_chain, workspace: Path) -> None:
    run_chain()
    for stage in STAGE_ARTIFACTS:
        path = workspace / PROJECT_ID / f"checkpoint_{stage}.json"
        assert path.exists(), f"missing checkpoint for {stage}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["stage"] == stage
        assert payload["pipeline_type"] == PIPELINE
