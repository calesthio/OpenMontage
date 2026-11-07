"""A pipeline switch must not reuse another pipeline's completed work."""

from lib.checkpoint import get_completed_stages, get_next_stage, write_checkpoint
from tests.contracts.test_phase0_contracts import sample_artifact


def test_pipeline_switch_restarts_shared_stage(tmp_path):
    # Both real manifests begin with research, but its completion belongs to
    # the old cinematic run, not the new framework-smoke run.
    write_checkpoint(
        tmp_path, "film", "research", "completed",
        {"research_brief": sample_artifact("research_brief")},
        pipeline_type="cinematic", human_approved=True,
    )

    assert get_completed_stages(tmp_path, "film", "framework-smoke") == []
    assert get_next_stage(tmp_path, "film", "framework-smoke") == "research"


def test_matching_pipeline_completion_is_retained(tmp_path):
    write_checkpoint(
        tmp_path, "film", "research", "completed",
        {"research_brief": sample_artifact("research_brief")},
        pipeline_type="framework-smoke", human_approved=True,
    )

    assert get_completed_stages(tmp_path, "film", "framework-smoke") == ["research"]
    assert get_next_stage(tmp_path, "film", "framework-smoke") == "script"


def test_unscoped_legacy_resume_still_accepts_completion(tmp_path):
    write_checkpoint(
        tmp_path, "film", "research", "completed",
        {"research_brief": sample_artifact("research_brief")},
        human_approved=True,
    )

    assert get_completed_stages(tmp_path, "film") == ["research"]
    assert get_next_stage(tmp_path, "film") == "proposal"
