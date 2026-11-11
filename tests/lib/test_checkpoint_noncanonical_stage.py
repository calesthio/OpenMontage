"""Regression test: checkpoint validation must not crash on manifest-only stages.

`_validate_artifacts_for_stage` looked up `CANONICAL_STAGE_ARTIFACTS[stage]`
unconditionally. Valid stages, however, come from the pipeline manifest
(`get_pipeline_stages`), which declares stages beyond the 9 canonical ones —
e.g. `character-animation` adds `character_design` / `rig_plan`. Those pass the
`stage in valid_stages` guard, then raised an unhandled `KeyError` on the
canonical lookup, so those stages could never be checkpointed. The lookup is now
defensive (`.get`).

Changed on purpose in the 2026-11-11 audit: a missing canonical entry used to
mean "no required artifact", so the gated `character_design` stage could be
presented for approval — and approved — with nothing in it. A manifest-declared
stage now has to hand over the first artifact of its `produces` list, the same
contract the nine canonical stages have always had.
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


CHARACTER_DESIGN = {
    "version": "1.0",
    "characters": [{
        "id": "ada",
        "display_name": "Ada",
        "role": "explorer",
        "body_type": "round",
        "style": "flat graphic",
        "silhouette_notes": "Round explorer with a bright orange field jacket",
        "required_emotions": ["curious"],
        "required_actions": ["wave"],
    }],
}


def test_noncanonical_stage_does_not_raise_keyerror():
    # A stage outside the canonical table validates without a KeyError: with
    # its artifact when it is done, with nothing while it is still running.
    validate_checkpoint(
        _checkpoint(
            "character_design", "completed",
            {"character_design": CHARACTER_DESIGN}, "character-animation",
        )
    )
    validate_checkpoint(
        _checkpoint("rig_plan", "in_progress", {}, "character-animation")
    )
    validate_checkpoint(
        _checkpoint("character_design", "failed", {}, "character-animation")
    )


@pytest.mark.parametrize("status", ["completed", "awaiting_human"])
@pytest.mark.parametrize(
    ("stage", "artifact"),
    [("character_design", "character_design"), ("rig_plan", "rig_plan")],
)
def test_manifest_declared_stage_requires_its_produced_artifact(stage, artifact, status):
    with pytest.raises(CheckpointValidationError, match=artifact) as exc:
        validate_checkpoint(_checkpoint(stage, status, {}, "character-animation"))
    assert "manifest-declared" in str(exc.value)


def test_manifest_declared_stage_artifact_is_schema_checked():
    broken = {"version": "1.0", "characters": [{"id": "ada"}]}
    with pytest.raises(CheckpointValidationError, match="character_design"):
        validate_checkpoint(
            _checkpoint(
                "character_design", "awaiting_human",
                {"character_design": broken}, "character-animation",
            )
        )


def test_without_a_known_pipeline_a_custom_stage_has_no_contract_to_check():
    # No manifest means no `produces` to read; the stage name itself is then
    # rejected by the stage check, not by a missing artifact.
    with pytest.raises(CheckpointValidationError, match="Invalid stage"):
        validate_checkpoint(_checkpoint("character_design", "completed", {}, "unknown"))


def test_canonical_stage_still_requires_its_artifact():
    # The fix must not weaken enforcement for canonical stages.
    with pytest.raises(CheckpointValidationError):
        validate_checkpoint(
            _checkpoint("compose", "completed", {}, "character-animation")
        )
