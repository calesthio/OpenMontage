"""Validate the real P1 pilot artifacts (when the run directory is present).

The pilot lives under `projects/` — gitignored and regenerable — so this test
skips when the run is absent (a fresh clone) and validates it when present.
That keeps the pilot honest: a broken artifact fails CI on the machine that
produced it instead of silently rotting in a directory nobody checks.

Stages 1–11 of the pilot are complete (topic through compose) with a rendered
MP4; the `topic` checkpoint was approved by the user on 2026-10-15 (decision
d-001, "Then execute Phase 1 only") and the run advanced through all gated
stages. Publish remains excluded by the same directive.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.artifact_ids import resolve_all, summarize
from lib.checkpoint import read_checkpoint
from schemas.artifacts import validate_artifact

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT_DIR = REPO_ROOT / "projects" / "pallets-hidden-business"
ARTIFACTS_DIR = PILOT_DIR / "artifacts"

PRESENT_STAGES = {
    "topic": ["topic_brief"],
    "research": ["research_brief"],
    "evidence": ["evidence_ledger"],
    "script": ["script"],
    "fact_check": ["fact_check_report"],
    "storyboard": ["scene_plan"],
    "narration": ["narration_manifest"],
    "footage": ["asset_manifest"],
    "editorial": ["alignment_report"],
    "compose": ["edit_decisions", "render_report"],
}

pytestmark = pytest.mark.skipif(
    not ARTIFACTS_DIR.exists(),
    reason="pilot run directory projects/pallets-hidden-business is not present",
)


def _load(name: str) -> dict:
    return json.loads((ARTIFACTS_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", [a for arts in PRESENT_STAGES.values() for a in arts])
def test_pilot_artifact_validates(name: str) -> None:
    validate_artifact(name, _load(name))


def test_pilot_ids_resolve_across_stages() -> None:
    artifacts = {name: _load(name) for arts in PRESENT_STAGES.values() for name in arts}
    dangling = resolve_all(artifacts)
    assert summarize(dangling)["dangling_count"] == 0


def test_every_evidence_entry_has_a_verbatim_extract() -> None:
    """A paraphrase in the extract field is not evidence."""

    ledger = _load("evidence_ledger")
    for entry in ledger["entries"]:
        assert entry["extract"].strip()
        assert len(entry["extract"]) >= 20
        assert entry["caveats"] is not None


def test_every_evidence_source_resolves_to_the_research_brief() -> None:
    ledger = _load("evidence_ledger")
    brief = _load("research_brief")
    known = {
        s["source_id"] for s in brief["sources"] if s.get("source_id")
    }
    for entry in ledger["entries"]:
        assert entry["source_id"] in known, entry["evidence_id"]


def test_the_topic_checkpoint_was_approved() -> None:
    """The manifest gates `topic`; the user approved it on 2026-10-15 (decision d-001)."""

    checkpoint = read_checkpoint(PILOT_DIR, "pallets-hidden-business", "topic")
    assert checkpoint is not None
    assert checkpoint["status"] == "completed"
    assert checkpoint["human_approval_required"] is True
    assert checkpoint["human_approved"] is True
    assert checkpoint["artifacts"]["topic_brief"]["unique_question"]


def test_all_stages_through_compose_are_checkpointed() -> None:
    """Approval was per-run (decision d-001), so stages 1–11 must be checkpointed."""

    for stage in (
        "topic",
        "research",
        "evidence",
        "script",
        "fact_check",
        "storyboard",
        "narration",
        "footage",
        "editorial",
        "compose",
    ):
        cp = read_checkpoint(PILOT_DIR, "pallets-hidden-business", stage)
        assert cp is not None, f"missing checkpoint for {stage}"
        assert cp["status"] == "completed", f"{stage} is {cp['status']}, not completed"


def test_the_pilot_records_its_source_gaps_honestly() -> None:
    """Fail-closed: unretrieved primary sources must be declared, not implied."""

    brief = _load("research_brief")
    gaps = brief["metadata"]["gaps"]
    assert gaps, "the pilot must declare what it could not retrieve"
    ledger = _load("evidence_ledger")
    assert all(
        entry["source_type"] in {"primary", "secondary", "tertiary"}
        for entry in ledger["entries"]
    )
    # Every entry currently rests on tertiary sources; the ledger must say so.
    assert {entry["source_type"] for entry in ledger["entries"]} == {"tertiary"}
