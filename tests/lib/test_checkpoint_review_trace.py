"""A stage that skipped the reviewer must leave a trace.

`skills/meta/reviewer.md` asks for a self-review after every stage. The
reviewer is advisory, so nothing blocks a checkpoint without one — which is how
a real run (`projects/bangkok-singapore-by-train`, 2026-11) finished seven
stages with no `review` in any checkpoint and nothing anywhere said so.
"""

import json
import logging

from lib.checkpoint import get_unreviewed_stages, init_project, write_checkpoint
from tests.contracts.test_phase0_contracts import sample_artifact

REVIEW = {"round": 1, "decision": "pass", "critical": 0, "suggestions": 1, "nitpicks": 0,
          "summary": "Hook is strong."}
PIPE = "framework-smoke"   # research* > script*  (both gated)


def _project(tmp_path):
    init_project("film", title="Film", pipeline_type=PIPE, pipeline_dir=tmp_path)
    return tmp_path


def _read(tmp_path, stage):
    return json.loads((tmp_path / "film" / f"checkpoint_{stage}.json").read_text())


def test_review_given_at_the_gate_is_kept_when_the_stage_is_approved(tmp_path):
    root = _project(tmp_path)
    brief = sample_artifact("research_brief")
    write_checkpoint(root, "film", "research", "awaiting_human", {"research_brief": brief},
                     review=REVIEW)
    gate_stamp = _read(root, "research")["timestamp"]

    # The approval re-write passes no review — the usual way it went missing.
    write_checkpoint(root, "film", "research", "completed", {"research_brief": brief},
                     human_approved=True)

    review = _read(root, "research")["review"]
    assert review["summary"] == "Hook is strong."
    assert review["carried_from"] == gate_stamp
    assert "artifact_changed_since_review" not in review
    assert get_unreviewed_stages(root, "film") == []


def test_carried_review_says_when_the_artifact_changed_after_it(tmp_path):
    root = _project(tmp_path)
    brief = sample_artifact("research_brief")
    write_checkpoint(root, "film", "research", "awaiting_human", {"research_brief": brief},
                     review=REVIEW)
    revised = dict(brief, topic="A different topic entirely")
    write_checkpoint(root, "film", "research", "completed", {"research_brief": revised},
                     human_approved=True)
    assert _read(root, "research")["review"]["artifact_changed_since_review"] is True


def test_explicit_review_always_wins_over_a_carried_one(tmp_path):
    root = _project(tmp_path)
    brief = sample_artifact("research_brief")
    write_checkpoint(root, "film", "research", "awaiting_human", {"research_brief": brief},
                     review=REVIEW)
    second = dict(REVIEW, round=2, summary="Second pass.")
    write_checkpoint(root, "film", "research", "completed", {"research_brief": brief},
                     human_approved=True, review=second)
    review = _read(root, "research")["review"]
    assert review == second


def test_stage_with_no_review_at_all_is_logged_and_reported(tmp_path, caplog):
    root = _project(tmp_path)
    brief = sample_artifact("research_brief")
    with caplog.at_level(logging.WARNING, logger="lib.checkpoint"):
        write_checkpoint(root, "film", "research", "awaiting_human", {"research_brief": brief})
    assert "without a review" in caplog.text and "research" in caplog.text
    assert "review" not in _read(root, "research")
    assert get_unreviewed_stages(root, "film") == ["research"]

    # Still never blocks: the reviewer is advisory.
    write_checkpoint(root, "film", "research", "completed", {"research_brief": brief},
                     human_approved=True)
    assert get_unreviewed_stages(root, "film") == ["research"]


def test_in_progress_and_failed_checkpoints_need_no_review(tmp_path, caplog):
    root = _project(tmp_path)
    with caplog.at_level(logging.WARNING, logger="lib.checkpoint"):
        write_checkpoint(root, "film", "research", "in_progress", {})
        write_checkpoint(root, "film", "research", "failed", {}, error="boom")
    assert "without a review" not in caplog.text
    assert get_unreviewed_stages(root, "film") == []


def test_a_review_on_an_archived_version_counts(tmp_path):
    """Re-running a reviewed stage without a review is still 'reviewed once'."""
    root = _project(tmp_path)
    brief = sample_artifact("research_brief")
    write_checkpoint(root, "film", "research", "completed", {"research_brief": brief},
                     human_approved=True, review=REVIEW)
    write_checkpoint(root, "film", "research", "in_progress", {})
    write_checkpoint(root, "film", "research", "awaiting_human", {"research_brief": brief})
    # The in_progress heartbeat carries no review, so nothing is carried over,
    # but the archived completed version does have one.
    assert "review" not in _read(root, "research")
    assert get_unreviewed_stages(root, "film") == []
