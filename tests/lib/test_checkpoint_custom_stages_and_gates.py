"""Regression tests for two audit findings (2026-07-15).

BUG-1: pipeline-specific stages (character-animation's character_design /
rig_plan) crashed _validate_artifacts_for_stage with a raw KeyError because
the canonical-artifact lookup used a hardcoded 9-stage dict instead of the
manifest's `produces` declarations.

BUG-2: pipeline_type="unknown" bypassed gate enforcement — the marker
backfill only ran for falsy values, and "unknown" is exempted from manifest
gate lookup. Since checkpoints written without a type are persisted AS
"unknown", echoing that field back silently disabled gating.
"""

import pytest

from lib.checkpoint import (
    CheckpointValidationError,
    init_project,
    write_checkpoint,
)


def _script_artifact() -> dict:
    return {
        "version": "1.0",
        "title": "Gate Test",
        "total_duration_seconds": 5,
        "sections": [{"id": "s1", "text": "Hello.", "start_seconds": 0, "end_seconds": 5}],
    }


class TestCustomStageArtifactLookup:
    """BUG-1: manifest-declared stages must not KeyError at write time."""

    def test_in_progress_checkpoint_at_custom_stage_succeeds(self, tmp_path):
        # Old behavior: raw KeyError('character_design') before the status
        # check ever ran — the pipeline died on its first in_progress write.
        path = write_checkpoint(
            tmp_path,
            "toon",
            "character_design",
            "in_progress",
            {},
            pipeline_type="character-animation",
        )
        assert path.exists()

    def test_completed_custom_stage_requires_manifest_canonical_artifact(self, tmp_path):
        # The canonical artifact is the stage's first `produces` entry in the
        # manifest (rig_plan produces [rig_plan, pose_library]). A completed
        # checkpoint missing it must fail with a clear validation error, not
        # a KeyError. rig_plan is ungated (human_approval_default: false).
        with pytest.raises(CheckpointValidationError, match="rig_plan"):
            write_checkpoint(
                tmp_path,
                "toon",
                "rig_plan",
                "completed",
                {},
                pipeline_type="character-animation",
            )


class TestUnknownPipelineTypeGateBypass:
    """BUG-2: "unknown" must backfill from the project marker, not skip gating."""

    def test_unknown_pipeline_type_backfills_marker_and_enforces_gate(self, tmp_path):
        init_project("film", title="Film", pipeline_type="cinematic", pipeline_dir=tmp_path)
        # cinematic gates `script`; the marker knows the real type, so the
        # caller's "unknown" must not disable enforcement.
        with pytest.raises(CheckpointValidationError, match="GATE VIOLATION"):
            write_checkpoint(
                tmp_path,
                "film",
                "script",
                "completed",
                {"script": _script_artifact()},
                pipeline_type="unknown",
                human_approved=False,
            )

    def test_unknown_pipeline_type_with_marker_still_allows_approved_write(self, tmp_path):
        init_project("film", title="Film", pipeline_type="cinematic", pipeline_dir=tmp_path)
        path = write_checkpoint(
            tmp_path,
            "film",
            "script",
            "completed",
            {"script": _script_artifact()},
            pipeline_type="unknown",
            human_approved=True,
        )
        assert path.exists()
