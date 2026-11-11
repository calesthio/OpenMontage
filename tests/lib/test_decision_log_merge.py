"""The project decision log is an append-only audit trail.

Regression tests for three defects in ``_merge_decision_log``:

- a decision re-written under its original ``decision_id`` with a different
  ``selected`` was dropped without a word, so the project log (and the board
  that reads it) kept the superseded choice;
- the log was written in place, so a crash mid-write truncated it;
- a truncated or hand-broken log surfaced as a bare ``JSONDecodeError`` on
  every later checkpoint that carried decisions.
"""

import json

import pytest

from lib.checkpoint import CheckpointValidationError, write_checkpoint


def decision(decision_id, selected, **extra):
    entry = {
        "decision_id": decision_id,
        "stage": "research",
        "category": "voice_selection",
        "subject": "Narration TTS provider",
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


def write(tmp_path, decision_log):
    return write_checkpoint(
        tmp_path, "film", "research", "in_progress", {"decision_log": decision_log}
    )


def recorded(tmp_path):
    return json.loads((tmp_path / "film" / "decision_log.json").read_text())["decisions"]


def test_changed_choice_under_the_same_id_is_rejected_not_dropped(tmp_path):
    write(tmp_path, log(decision("voice", "piper")))
    log_path = tmp_path / "film" / "decision_log.json"
    checkpoint_path = tmp_path / "film" / "checkpoint_research.json"
    before = (log_path.read_bytes(), checkpoint_path.read_bytes())

    with pytest.raises(CheckpointValidationError, match="DECISION LOG VIOLATION") as exc:
        write(tmp_path, log(decision("voice", "chirp")))

    # The message has to tell the agent how to re-log the change.
    assert "same category" in str(exc.value)
    assert "'Narration TTS provider'" in str(exc.value)
    # Neither the audit trail nor the stage checkpoint moved.
    assert (log_path.read_bytes(), checkpoint_path.read_bytes()) == before


def test_revision_appended_under_a_new_id_is_recorded(tmp_path):
    write(tmp_path, log(decision("voice", "piper")))
    write(tmp_path, log(decision("voice", "piper"), decision("voice-v2", "chirp")))

    assert [(d["decision_id"], d["selected"]) for d in recorded(tmp_path)] == [
        ("voice", "piper"),
        ("voice-v2", "chirp"),
    ]


def test_same_choice_with_refreshed_details_updates_the_log(tmp_path):
    write(tmp_path, log(decision("voice", "piper", user_approved=False)))
    write(tmp_path, log(decision("voice", "piper", user_approved=True)))

    entries = recorded(tmp_path)
    assert len(entries) == 1
    assert entries[0]["user_approved"] is True


def test_duplicate_ids_in_one_payload_are_recorded_once(tmp_path):
    write(tmp_path, log(decision("voice", "piper"), decision("voice", "piper")))

    assert [d["decision_id"] for d in recorded(tmp_path)] == ["voice"]


def test_unreadable_log_is_reported_by_path_and_left_alone(tmp_path):
    write(tmp_path, log(decision("voice", "piper")))
    log_path = tmp_path / "film" / "decision_log.json"
    torn = '{"version": "1.0", "decisions": [{"decision_id": "vo'
    log_path.write_text(torn, encoding="utf-8")

    with pytest.raises(CheckpointValidationError, match="decision_log.json") as exc:
        write(tmp_path, log(decision("music", "piper")))

    assert "repair it or move it aside" in str(exc.value)
    assert log_path.read_text(encoding="utf-8") == torn


def test_log_is_swapped_in_atomically(tmp_path, monkeypatch):
    write(tmp_path, log(decision("voice", "piper")))
    log_path = tmp_path / "film" / "decision_log.json"
    original = log_path.read_bytes()

    import lib.checkpoint as checkpoint_module

    def failing_dump(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(checkpoint_module.json, "dump", failing_dump)
    with pytest.raises(OSError):
        write(tmp_path, log(decision("voice", "piper"), decision("music", "chirp")))

    # A failed write must leave the previous log whole.
    assert log_path.read_bytes() == original
