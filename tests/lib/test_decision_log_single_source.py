"""One decision log per project: `<project>/decision_log.json`.

Found on a real run (`projects/bangkok-singapore-by-train`, 2026-11): the
project log held 11 decisions while `artifacts/decision_log.json` — a second
copy the agent kept appending to between checkpoints — held 14. The board
preferred the copy, the audit trail was the other file, and neither was whole.
"""

import json
import logging

import pytest

from backlot.state import load_board_state
from lib.checkpoint import (
    CheckpointValidationError,
    append_decisions,
    decision_log_drift,
    init_project,
    read_decision_log,
    write_checkpoint,
)


def decision(decision_id, selected="piper", subject="Narration TTS provider", **extra):
    entry = {
        "decision_id": decision_id,
        "stage": "research",
        "category": "voice_selection",
        "subject": subject,
        "options_considered": [
            {"option_id": "piper", "label": "Piper", "score": 1, "reason": "Local"},
            {"option_id": "chirp", "label": "Chirp", "score": 1, "reason": "Cloud"},
        ],
        "selected": selected,
        "reason": "Fixture",
    }
    entry.update(extra)
    return entry


def log(*decisions):
    return {"version": "1.0", "project_id": "film", "decisions": list(decisions)}


@pytest.fixture
def project(tmp_path):
    init_project("film", title="Film", pipeline_type="cinematic", pipeline_dir=tmp_path)
    return tmp_path


def _stray(root, *decisions):
    path = root / "film" / "artifacts" / "decision_log.json"
    path.write_text(json.dumps(log(*decisions)), encoding="utf-8")
    return path


def _ids(root):
    return [d["decision_id"] for d in read_decision_log(root, "film")["decisions"]]


def test_append_decisions_writes_the_project_log_between_checkpoints(project):
    path = append_decisions(project, "film", [decision("d-1")])
    assert path == project / "film" / "decision_log.json"
    append_decisions(project, "film", [decision("d-2", subject="Music bed")])
    assert _ids(project) == ["d-1", "d-2"]


def test_append_decisions_keeps_the_append_only_rule(project):
    append_decisions(project, "film", [decision("d-1", "piper")])
    with pytest.raises(CheckpointValidationError, match="DECISION LOG VIOLATION"):
        append_decisions(project, "film", [decision("d-1", "chirp")])
    assert read_decision_log(project, "film")["decisions"][0]["selected"] == "piper"


def test_append_decisions_rejects_entries_the_schema_rejects(project):
    with pytest.raises(CheckpointValidationError, match="schema"):
        append_decisions(project, "film", [{"decision_id": "d-1", "selected": "x"}])
    assert not (project / "film" / "decision_log.json").exists()


def test_read_decision_log_of_a_project_without_one_is_empty(project):
    assert read_decision_log(project, "film") == {
        "version": "1.0", "project_id": "film", "decisions": [],
    }


def test_stray_copy_is_folded_into_the_project_log_at_the_next_checkpoint(project, caplog):
    write_checkpoint(project, "film", "research", "in_progress",
                     {"decision_log": log(decision("d-1"))})
    _stray(project, decision("d-1"), decision("d-2", subject="Music bed"),
           decision("d-3", "chirp", subject="Image provider"))
    assert decision_log_drift(project, "film") == {"unlogged": ["d-2", "d-3"], "conflicting": []}

    with caplog.at_level(logging.WARNING, logger="lib.checkpoint"):
        write_checkpoint(project, "film", "research", "in_progress", {})

    assert _ids(project) == ["d-1", "d-2", "d-3"]
    assert decision_log_drift(project, "film") == {"unlogged": [], "conflicting": []}
    assert "append_decisions" in caplog.text  # tells the agent the right way


def test_stray_copy_cannot_rewrite_a_logged_choice_or_block_the_checkpoint(project, caplog):
    write_checkpoint(project, "film", "research", "in_progress",
                     {"decision_log": log(decision("d-1", "piper"))})
    _stray(project, decision("d-1", "chirp"), {"decision_id": "d-9", "selected": "junk"})

    with caplog.at_level(logging.WARNING, logger="lib.checkpoint"):
        path = write_checkpoint(project, "film", "research", "in_progress", {})

    assert path.exists()
    recorded = read_decision_log(project, "film")["decisions"]
    assert [(d["decision_id"], d["selected"]) for d in recorded] == [("d-1", "piper")]
    assert "append-only" in caplog.text and "d-9" in caplog.text
    drift = decision_log_drift(project, "film")
    assert drift["conflicting"] == ["d-1"] and drift["unlogged"] == ["d-9"]


def test_unreadable_stray_copy_is_ignored(project):
    (project / "film" / "artifacts" / "decision_log.json").write_text("{ not json", encoding="utf-8")
    write_checkpoint(project, "film", "research", "in_progress",
                     {"decision_log": log(decision("d-1"))})
    assert _ids(project) == ["d-1"]


# ---- the board reads the same single source ---------------------------------


def _board_decisions(root):
    state = load_board_state(root / "film")
    return state["artifacts"].get("decision_log", {}).get("decisions", []), state["decision_log_drift"]


def test_board_shows_the_project_log_not_the_stray_copy(project):
    append_decisions(project, "film", [decision("d-1", "piper")])
    _stray(project, decision("d-1", "chirp"))  # an in-place edit of a logged choice

    decisions, drift = _board_decisions(project)
    assert [(d["decision_id"], d["selected"]) for d in decisions] == [("d-1", "piper")]
    assert drift == {"unlogged": 0, "conflicting": 1, "stray_only": False}


def test_board_lists_unlogged_decisions_after_the_logged_ones_and_flags_them(project):
    append_decisions(project, "film", [decision("d-1"), decision("d-2", subject="Music bed")])
    _stray(project, decision("d-1"), decision("d-2", subject="Music bed"),
           decision("d-3", "chirp"))  # revises d-1's subject, never checkpointed

    decisions, drift = _board_decisions(project)
    assert [d["decision_id"] for d in decisions] == ["d-1", "d-2", "d-3"]
    assert [d.get("unlogged", False) for d in decisions] == [False, False, True]
    assert drift == {"unlogged": 1, "conflicting": 0, "stray_only": False}


def test_board_reports_no_drift_when_the_two_files_agree_or_only_one_exists(project):
    append_decisions(project, "film", [decision("d-1")])
    assert _board_decisions(project)[1] is None
    _stray(project, decision("d-1"))
    assert _board_decisions(project)[1] is None


def test_board_still_shows_a_legacy_project_that_only_has_the_stray_copy(project):
    _stray(project, decision("d-1"), decision("d-2", subject="Music bed"))
    decisions, drift = _board_decisions(project)
    assert [d["decision_id"] for d in decisions] == ["d-1", "d-2"]
    assert drift == {"unlogged": 2, "conflicting": 0, "stray_only": True}
