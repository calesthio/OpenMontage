"""Output-profile choices are part of the approved proposal contract."""

import pytest
from jsonschema import ValidationError

from schemas.artifacts import validate_artifact


def _proposal() -> dict:
    return {
        "version": "1.0",
        "concept_options": [
            {
                "id": f"c{i}",
                "title": f"Concept {i}",
                "hook": "A sourced question.",
                "narrative_structure": "data_narrative",
                "visual_approach": "Evidence-led motion graphics.",
                "target_duration_seconds": 60,
                "why_this_works": "It explains one sourced finding.",
            }
            for i in range(1, 4)
        ],
        "selected_concept": {"concept_id": "c1", "rationale": "Best fit."},
        "production_plan": {
            "pipeline": "animated-explainer",
            "stages": [],
            "render_runtime": "remotion",
        },
        "cost_estimate": {
            "total_estimated_usd": 0,
            "line_items": [],
            "budget_verdict": "no_budget_set",
        },
        "approval": {"status": "pending"},
    }


def test_legacy_proposal_without_output_profiles_remains_valid():
    validate_artifact("proposal_packet", _proposal())


def test_proposal_accepts_either_or_both_output_profiles():
    for profiles in (
        ["social_vertical"],
        ["youtube_landscape"],
        ["social_vertical", "youtube_landscape"],
    ):
        proposal = _proposal()
        proposal["production_plan"]["output_profiles"] = profiles
        validate_artifact("proposal_packet", proposal)


def test_proposal_rejects_empty_duplicate_or_unknown_output_profiles():
    for profiles in ([], ["social_vertical", "social_vertical"], ["tiktok"]):
        proposal = _proposal()
        proposal["production_plan"]["output_profiles"] = profiles
        with pytest.raises(ValidationError):
            validate_artifact("proposal_packet", proposal)
