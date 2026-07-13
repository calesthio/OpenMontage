"""Regression test: checkpoint validation must not crash on manifest-only stages.

`_validate_artifacts_for_stage` looked up `CANONICAL_STAGE_ARTIFACTS[stage]`
unconditionally. Valid stages, however, come from the pipeline manifest
(`get_pipeline_stages`), which declares stages beyond the 9 canonical ones —
e.g. `character-animation` adds `character_design` / `rig_plan`. Those pass the
`stage in valid_stages` guard, then raised an unhandled `KeyError` on the
canonical lookup, so those stages could never be checkpointed. The lookup is now
defensive (`.get`), treating a missing entry as "no required artifact".
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.checkpoint import (  # noqa: E402
    CheckpointValidationError,
    get_pipeline_stages,
    validate_checkpoint,
)


def _checkpoint(stage, status, artifacts, pipeline_type):
    return {
        "version": "1.0",
        "project_id": "proj",
        "pipeline_type": pipeline_type,
        "stage": stage,
        "status": status,
        "timestamp": "2026-01-01T00:00:00Z",
        "artifacts": artifacts,
    }


def test_manifest_declares_noncanonical_stage():
    # Guard the premise: the manifest really does add stages the canonical map
    # doesn't know about.
    stages = get_pipeline_stages("character-animation")
    assert "character_design" in stages


def test_noncanonical_stage_does_not_raise_keyerror():
    # character_design has no canonical artifact; completing it with no
    # artifacts must validate cleanly rather than crash.
    validate_checkpoint(
        _checkpoint("character_design", "completed", {}, "character-animation")
    )
    validate_checkpoint(
        _checkpoint("rig_plan", "in_progress", {}, "character-animation")
    )


def test_canonical_stage_still_requires_its_artifact():
    # The fix must not weaken enforcement for canonical stages.
    with pytest.raises(CheckpointValidationError):
        validate_checkpoint(
            _checkpoint("compose", "completed", {}, "character-animation")
        )
