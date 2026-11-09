"""The artifact schemas must accept the values AGENT_GUIDE mandates.

AGENT_GUIDE.md is binding on the agent, but nothing checked that the artifact
schemas can express what it requires. Where they cannot, the agent has to
either drop the record or file it under an unrelated value — and the audit
trail then says something that did not happen. Reported as calesthio/OpenMontage#493.

Two cases, both grounded in an explicit instruction rather than in taste:

- `decision_log` had no `approval_policy` category, though AGENT_GUIDE.md
  names it as the one mechanism that makes full-run pre-authorization count.
- `proposal_packet` had no `source_type` for a track fetched through a
  `music_search` tool, though AGENT_GUIDE.md requires the music plan to offer
  royalty-free search — and `pixabay_music` serves it with no API key.

The category test derives its expectations from AGENT_GUIDE.md itself, so a
future instruction naming a new category fails here instead of silently
becoming unrecordable.
"""

import json
import re
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SCHEMAS = PROJECT_ROOT / "schemas" / "artifacts"
AGENT_GUIDE = PROJECT_ROOT / "AGENT_GUIDE.md"

# AGENT_GUIDE writes a mandated decision category as `category: "name"`.
_CATEGORY = re.compile(r'category:\s*"([a-z_]+)"')


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def _decision_categories() -> list[str]:
    return _schema("decision_log")["properties"]["decisions"]["items"]["properties"][
        "category"
    ]["enum"]


def _guide_categories() -> list[str]:
    return sorted(set(_CATEGORY.findall(AGENT_GUIDE.read_text(encoding="utf-8"))))


GUIDE_CATEGORIES = _guide_categories()


def test_agent_guide_names_some_categories() -> None:
    """Without this the parametrized test below could pass vacuously."""
    assert GUIDE_CATEGORIES, "no `category: \"...\"` mandates found in AGENT_GUIDE.md"


@pytest.mark.parametrize("category", GUIDE_CATEGORIES)
def test_mandated_category_is_recordable(category: str) -> None:
    assert category in _decision_categories(), (
        f"AGENT_GUIDE.md mandates decision_log category {category!r}, but the "
        f"schema enum rejects it, so the agent cannot record it truthfully"
    )


def test_a_pre_authorization_entry_validates() -> None:
    """The end the defect was visible from: writing the entry the guide asks for."""
    artifact = {
        "version": "1.0",
        "project_id": "probe",
        "decisions": [
            {
                "decision_id": "d1",
                "stage": "idea",
                "category": "approval_policy",
                "subject": "Full-run pre-authorization",
                "options_considered": [
                    {
                        "option_id": "per_gate",
                        "label": "Approve at every gate",
                        "score": 0.4,
                        "reason": "Default; the user stops at each stage.",
                    },
                    {
                        "option_id": "full_run",
                        "label": "Full-run pre-authorization",
                        "score": 1.0,
                        "reason": "The user authorized the whole run up front.",
                    },
                ],
                "selected": "full_run",
                "reason": "User approved the whole run up front.",
            }
        ],
    }

    Draft202012Validator(_schema("decision_log")).validate(artifact)


def _source_types() -> list[str]:
    packet = _schema("proposal_packet")
    return packet["properties"]["production_plan"]["properties"]["music_source"][
        "properties"
    ]["source_type"]["enum"]


def test_a_searched_royalty_free_track_can_be_described() -> None:
    """`user_library` means the user's own music_library/ folder, so a track
    fetched through a music_search tool had no honest value."""
    assert "royalty_free_search" in _source_types()


def test_the_royalty_free_option_is_actually_reachable() -> None:
    """Guard against adding an enum value for a path nothing implements."""
    import logging

    logging.disable(logging.CRITICAL)
    from tools.tool_registry import registry

    registry.discover()
    assert registry.get_by_capability("music_search"), (
        "no tool serves the music_search capability, so royalty_free_search "
        "would describe a path that does not exist"
    )
