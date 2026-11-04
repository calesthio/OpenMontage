"""Rejected stage writes must not append to the accepted decision history."""

import json

import pytest

from lib.checkpoint import CheckpointValidationError, read_checkpoint, write_checkpoint


def decision_log(decision_id):
    return {
        "version": "1.0", "project_id": "film",
        "decisions": [{
            "decision_id": decision_id, "stage": "research",
            "category": "provider_selection", "subject": "narration",
            "options_considered": [{
                "option_id": "local", "label": "Local", "score": 1,
                "reason": "No external call needed",
            }],
            "selected": "local", "reason": "Local fixture",
        }],
    }


@pytest.mark.parametrize("invalid_kwargs", [
    {"metadata": "not an object"},
    {"artifacts": {"script": {"version": "1.0"}}},
])
def test_rejected_checkpoint_keeps_prior_decisions(tmp_path, invalid_kwargs):
    write_checkpoint(tmp_path, "film", "research", "in_progress",
                     {"decision_log": decision_log("accepted")})
    log_path = tmp_path / "film" / "decision_log.json"
    original = log_path.read_bytes()
    kwargs = dict(invalid_kwargs)
    artifacts = kwargs.pop("artifacts", {})
    artifacts["decision_log"] = decision_log("rejected")

    with pytest.raises(CheckpointValidationError):
        write_checkpoint(tmp_path, "film", "research", "in_progress", artifacts, **kwargs)

    assert log_path.read_bytes() == original
    assert read_checkpoint(tmp_path, "film", "research")["artifacts"]["decision_log"] == decision_log("accepted")


def test_rejected_first_write_does_not_create_a_decision_log(tmp_path):
    with pytest.raises(CheckpointValidationError):
        write_checkpoint(tmp_path, "film", "research", "in_progress",
                         {"decision_log": decision_log("rejected")}, metadata=[])
    assert not (tmp_path / "film" / "decision_log.json").exists()


def test_accepted_write_merges_new_decisions_and_deduplicates_replay(tmp_path):
    for name in ("first", "second", "second"):
        write_checkpoint(tmp_path, "film", "research", "in_progress",
                         {"decision_log": decision_log(name)})
    log = json.loads((tmp_path / "film" / "decision_log.json").read_text())
    assert [d["decision_id"] for d in log["decisions"]] == ["first", "second"]
