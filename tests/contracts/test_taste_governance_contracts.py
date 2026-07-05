"""Contract tests for taste-direction governance.

The taste-direction meta skill is an agent-facing contract: it must be easy to
discover, and its output must fit the canonical proposal/style artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parent.parent.parent


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _taste_profile() -> dict:
    return {
        "design_read": "Premium expert explainer: calm authority, high trust, low ornament.",
        "visual_variance": 4,
        "motion_intensity": 3,
        "information_density": 5,
        "palette_discipline": "Neutral base, one blue accent, no decorative gradients.",
        "layout_variation": "Alternate editorial split frames with data-forward full-frame scenes.",
        "reference_strategy": "One reference still per scene family before asset generation.",
        "anti_patterns": [
            "generic AI-purple gradient backgrounds",
            "reusing the same transition on every cut",
        ],
        "quality_gates": [
            "Each scene carries the design read without needing explanatory labels.",
            "Motion stays purposeful and never outruns narration comprehension.",
        ],
    }


def test_style_playbook_schema_accepts_taste_profile():
    schema = _load_json(ROOT / "schemas" / "styles" / "playbook.schema.json")
    assert "taste_profile" in schema["properties"]
    playbook = yaml.safe_load((ROOT / "styles" / "clean-professional.yaml").read_text(encoding="utf-8"))
    playbook["taste_profile"] = _taste_profile()

    jsonschema.validate(instance=playbook, schema=schema)


def test_proposal_packet_schema_accepts_taste_profile():
    schema = _load_json(ROOT / "schemas" / "artifacts" / "proposal_packet.schema.json")
    proposal = {
        "version": "1.0",
        "concept_options": [
            {
                "id": f"c{i}",
                "title": f"Concept {i}",
                "hook": "A precise hook under twenty words.",
                "narrative_structure": "problem_solution",
                "visual_approach": "Premium minimalist scenes with data-led visual proof.",
                "target_duration_seconds": 60,
                "why_this_works": "It ties the audience problem to a visible payoff.",
            }
            for i in range(1, 4)
        ],
        "selected_concept": {"concept_id": "c1", "rationale": "Best fit for the brief."},
        "production_plan": {
            "pipeline": "animated-explainer",
            "stages": [{"stage": "proposal", "tools": [], "approach": "Plan the production."}],
            "render_runtime": "remotion",
            "taste_profile": _taste_profile(),
        },
        "cost_estimate": {
            "total_estimated_usd": 0,
            "line_items": [],
            "budget_verdict": "no_budget_set",
        },
        "approval": {"status": "pending"},
    }

    jsonschema.validate(instance=proposal, schema=schema)


def test_taste_direction_is_discoverable_to_new_agents():
    skill_path = ROOT / "skills" / "meta" / "taste-direction.md"
    assert skill_path.is_file(), "Missing Layer 2 taste-direction meta skill"

    index = (ROOT / "skills" / "INDEX.md").read_text(encoding="utf-8")
    assert "Taste Direction" in index
    assert "meta/taste-direction.md" in index

    guide = (ROOT / "AGENT_GUIDE.md").read_text(encoding="utf-8")
    assert "taste-direction.md" in guide


def test_premium_minimalist_playbook_exists_and_validates():
    from styles.playbook_loader import load_playbook, list_playbooks

    assert "premium-minimalist" in list_playbooks()
    playbook = load_playbook("premium-minimalist")
    assert playbook["taste_profile"]["motion_intensity"] <= 4
    assert playbook["taste_profile"]["information_density"] >= 4
