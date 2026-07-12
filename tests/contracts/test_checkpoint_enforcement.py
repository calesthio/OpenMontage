"""Contract tests for checkpoint enforcement.

Verifies that checkpoint_required: true stages are actually enforced —
missing checkpoints raise errors and the batch verifier reports correctly.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.checkpoint import write_checkpoint
from lib.checkpoint_enforcer import (
    CheckpointEnforcementError,
    verify_pipeline_checkpoints,
    verify_stage_checkpointed,
)


# --- Fixtures ---

@pytest.fixture
def pipeline_dir(tmp_path):
    """Create a temporary pipeline directory."""
    d = tmp_path / "pipelines"
    d.mkdir()
    return d


def _write_valid_checkpoint(pipeline_dir, project_id, stage, pipeline_type="animated-explainer"):
    """Write a minimal valid checkpoint for a stage."""
    from tests.contracts.test_phase0_contracts import sample_artifact
    artifact_name_map = {
        "research": "research_brief",
        "proposal": "proposal_packet",
        "script": "script",
        "scene_plan": "scene_plan",
        "assets": "asset_manifest",
        "edit": "edit_decisions",
        "compose": "render_report",
        "publish": "publish_log",
    }
    artifact_name = artifact_name_map.get(stage)
    if artifact_name:
        try:
            artifacts = {artifact_name: sample_artifact(artifact_name)}
        except Exception:
            artifacts = {}
    else:
        artifacts = {}

    return write_checkpoint(
        pipeline_dir=pipeline_dir,
        project_id=project_id,
        stage=stage,
        status="completed",
        artifacts=artifacts,
        pipeline_type=pipeline_type,
    )


# --- verify_stage_checkpointed tests ---

class TestVerifyStageCheckpointed:
    """Tests for single-stage checkpoint enforcement."""

    def test_required_stage_missing_checkpoint_raises(self, pipeline_dir):
        """checkpoint_required: true + no checkpoint → error."""
        with pytest.raises(CheckpointEnforcementError, match="checkpoint_required: true"):
            verify_stage_checkpointed(
                pipeline_dir=pipeline_dir,
                project_id="test-project",
                stage="proposal",  # checkpoint_required: true in animated-explainer
                pipeline_type="animated-explainer",
            )

    def test_required_stage_with_checkpoint_passes(self, pipeline_dir):
        """checkpoint_required: true + valid checkpoint → no error."""
        _write_valid_checkpoint(pipeline_dir, "test-project", "proposal", "animated-explainer")
        # Should not raise
        verify_stage_checkpointed(
            pipeline_dir=pipeline_dir,
            project_id="test-project",
            stage="proposal",
            pipeline_type="animated-explainer",
        )

    def test_optional_stage_missing_checkpoint_no_error(self, pipeline_dir):
        """checkpoint_required: false + no checkpoint → no error."""
        # research has checkpoint_required: false in animated-explainer
        verify_stage_checkpointed(
            pipeline_dir=pipeline_dir,
            project_id="test-project",
            stage="research",
            pipeline_type="animated-explainer",
        )

    def test_unknown_pipeline_no_error(self, pipeline_dir):
        """Unknown pipeline → graceful skip (log warning, no error)."""
        verify_stage_checkpointed(
            pipeline_dir=pipeline_dir,
            project_id="test-project",
            stage="proposal",
            pipeline_type="nonexistent-pipeline",
        )


# --- verify_pipeline_checkpoints tests ---

class TestVerifyPipelineCheckpoints:
    """Tests for batch pipeline checkpoint verification."""

    def test_all_required_present_returns_passed(self, pipeline_dir):
        """All checkpoint_required stages have checkpoints → passed."""
        project_id = "full-project"
        # Write checkpoints for all required stages
        for stage in ["proposal", "script", "scene_plan", "assets", "edit", "compose", "publish"]:
            _write_valid_checkpoint(pipeline_dir, project_id, stage, "animated-explainer")

        result = verify_pipeline_checkpoints(
            pipeline_dir, project_id, "animated-explainer"
        )
        assert result["status"] == "passed"
        assert len(result["missing_required"]) == 0

    def test_all_required_missing_returns_blocked(self, pipeline_dir):
        """No checkpoints at all → blocked."""
        result = verify_pipeline_checkpoints(
            pipeline_dir, "empty-project", "animated-explainer"
        )
        assert result["status"] == "blocked"
        assert result["total_present"] == 0
        assert len(result["missing_required"]) > 0

    def test_partial_returns_degraded(self, pipeline_dir):
        """Some required checkpoints missing → degraded."""
        project_id = "partial-project"
        # Only write checkpoint for proposal (skip the rest)
        _write_valid_checkpoint(pipeline_dir, project_id, "proposal", "animated-explainer")

        result = verify_pipeline_checkpoints(
            pipeline_dir, project_id, "animated-explainer",
            completed_stages=["proposal", "script", "scene_plan"],
        )
        assert result["status"] == "degraded"
        assert result["total_present"] == 1
        assert any(m["stage"] == "script" for m in result["missing_required"])
        assert any(m["stage"] == "scene_plan" for m in result["missing_required"])

    def test_nonexistent_pipeline_returns_blocked(self, pipeline_dir):
        """Nonexistent pipeline manifest → blocked with error."""
        result = verify_pipeline_checkpoints(
            pipeline_dir, "any-project", "nonexistent-pipeline"
        )
        assert result["status"] == "blocked"
        assert "not found" in result.get("error", "")

    def test_report_structure(self, pipeline_dir):
        """Verify the report contains all expected fields."""
        result = verify_pipeline_checkpoints(
            pipeline_dir, "test-project", "animated-explainer"
        )
        assert "status" in result
        assert "missing_required" in result
        assert "present" in result
        assert "total_required" in result
        assert "total_present" in result
        assert isinstance(result["missing_required"], list)
        assert isinstance(result["present"], list)
