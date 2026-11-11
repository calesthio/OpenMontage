"""A pipeline name with no manifest must fail loudly, not resume the wrong run.

`get_pipeline_stages` used to catch every exception and hand back the
canonical stage list. A misspelled pipeline (`animated-explaner`) therefore
resumed against stages the real pipeline does not have (`idea`) and without the
ones it adds, and nothing said so.
"""

import json
import logging

import pytest

from lib import checkpoint
from lib.checkpoint import (
    STAGES,
    CheckpointValidationError,
    UnknownPipelineError,
    get_completed_stages,
    get_next_stage,
    get_pipeline_stages,
    get_stale_stages,
    read_checkpoint,
    write_checkpoint,
)


def test_unknown_pipeline_name_raises_and_lists_the_real_ones():
    with pytest.raises(UnknownPipelineError) as exc:
        get_pipeline_stages("animated-explaner")
    message = str(exc.value)
    assert "animated-explaner" in message
    assert "animated-explainer" in message  # the list of known pipelines
    # Callers that already catch the checkpoint error keep working.
    assert isinstance(exc.value, CheckpointValidationError)


@pytest.mark.parametrize("fn", [get_next_stage, get_completed_stages, get_stale_stages])
def test_resume_helpers_reject_a_misspelled_pipeline(tmp_path, fn):
    (tmp_path / "film").mkdir()
    with pytest.raises(UnknownPipelineError):
        fn(tmp_path, "film", "animated-explaner")


def test_write_rejects_a_misspelled_pipeline(tmp_path):
    with pytest.raises(UnknownPipelineError):
        write_checkpoint(tmp_path, "film", "research", "in_progress", {},
                         pipeline_type="animated-explaner")
    assert not (tmp_path / "film" / "checkpoint_research.json").exists()


@pytest.mark.parametrize("pipeline_type", [None, "unknown"])
def test_no_pipeline_keeps_the_canonical_order(pipeline_type, caplog):
    with caplog.at_level(logging.WARNING, logger="lib.checkpoint"):
        assert get_pipeline_stages(pipeline_type) == list(STAGES)
    assert "canonical fallback" in caplog.text


def test_unloadable_manifest_falls_back_with_a_warning(monkeypatch, caplog):
    """A manifest that exists but is broken must not strand a run — but the
    degradation has to be visible (same policy as the gate lookup)."""
    from lib import pipeline_loader

    def broken(name, defs_dir=None):
        raise ValueError("schema says no")

    monkeypatch.setattr(pipeline_loader, "load_pipeline_readonly", broken)
    with caplog.at_level(logging.WARNING, logger="lib.checkpoint"):
        assert get_pipeline_stages("cinematic") == list(STAGES)
    assert "cinematic" in caplog.text and "schema says no" in caplog.text


def test_a_checkpoint_of_a_removed_pipeline_can_still_be_read(tmp_path, caplog):
    project = tmp_path / "old-film"
    project.mkdir()
    (project / "checkpoint_script.json").write_text(json.dumps({
        "version": "1.0",
        "project_id": "old-film",
        "pipeline_type": "pipeline-that-was-renamed",
        "stage": "script",
        "status": "in_progress",
        "timestamp": "2026-01-01T00:00:00Z",
        "artifacts": {},
    }), encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="lib.checkpoint"):
        loaded = read_checkpoint(tmp_path, "old-film", "script")
    assert loaded["stage"] == "script"
    assert "pipeline-that-was-renamed" in caplog.text


def test_module_exports_the_error():
    assert checkpoint.UnknownPipelineError is UnknownPipelineError
