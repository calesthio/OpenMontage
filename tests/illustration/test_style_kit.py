#!/usr/bin/env python3
"""Red/green tests for the niche style kit and the creature-sheet kit (P2).

Covers:
  * every niche profile has a finalized STYLE_BIBLE.md and a machine-readable
    style.json (palette, line style, camera vocabulary, constraints, label rule),
  * the locked model builds a prompt whose constraints are written POSITIVELY
    (the locked model has no negative prompt),
  * a model that does accept a negative prompt gets the negative forms,
  * anatomy counts are ALWAYS in the prompt,
  * spec -> prompt -> deterministic job file (byte-identical across runs),
  * the reference-image workflow is only declared for a model whose official
    card supports it (with the citation).

No network, no Kaggle, no GPU, no paid route.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.illustration.creature_sheet import (  # noqa: E402
    CANONICAL_VIEWS,
    build_creature_sheet,
    build_sheet_job,
    build_sheet_plan,
    creature_spec_from_yaml,
    load_creature_specs,
)
from tools.illustration.model_registry import (  # noqa: E402
    active_adapter,
    adapter_for,
    load_engine,
)
from tools.illustration.style_kit import (  # noqa: E402
    NICHES,
    REFERENCE_IMAGE_SUPPORT,
    StyleError,
    constraint_fragments,
    load_style,
    validate_style,
)

CREATURE_DIR = ROOT / "docs/openmontage/niches/speculative_evolution/creatures"
BIBLE_DIR = ROOT / "docs/openmontage/niches"


# ------------------------------------------------------------- style files
@pytest.mark.parametrize("niche", sorted(NICHES))
def test_every_niche_has_a_style_file_and_a_final_style_bible(niche):
    style = load_style(niche)
    assert style.niche_id == niche
    bible = BIBLE_DIR / niche / "STYLE_BIBLE.md"
    assert bible.is_file(), f"{bible} is missing"
    text = bible.read_text(encoding="utf-8")
    assert "Status: FINAL" in text
    assert "style.json" in text


@pytest.mark.parametrize("niche", sorted(NICHES))
def test_style_files_pass_validation(niche):
    validate_style(load_style(niche))


def test_style_file_carries_the_required_sections():
    style = load_style("speculative_evolution")
    assert style.palette and all(
        len(v) == 7 and v.startswith("#") for v in style.palette.values())
    assert style.line_style["prompt_phrase"]
    for view in CANONICAL_VIEWS:
        assert style.camera_vocabulary.get(view), f"camera vocabulary lacks {view}"
    assert style.label_rule.get("label")
    assert style.anatomy_rule.get("required") is True
    assert style.seed_policy.get("range")


def test_loader_fails_closed_on_a_missing_style(tmp_path):
    with pytest.raises(StyleError):
        load_style("not_a_niche")


# ---------------------------------------------------------- prompt rules
def test_locked_model_gets_positive_constraints_and_no_negative_prompt():
    engine = load_engine()
    adapter = active_adapter(engine)
    frags = constraint_fragments(load_style("speculative_evolution"), adapter)
    assert frags["supports_negative_prompt"] is False
    assert frags["negative"] == []
    assert frags["positive"]


def test_a_negative_prompt_model_gets_the_negative_forms():
    engine = load_engine()
    adapter = adapter_for(engine, "sdxl-lightning")
    frags = constraint_fragments(load_style("speculative_evolution"), adapter)
    assert frags["supports_negative_prompt"] is True
    assert frags["negative"]


def test_the_locked_model_prompt_carries_the_positive_constraints():
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    creature = load_creature_specs(CREATURE_DIR)[0]
    sheet = build_creature_sheet(creature, style, adapter)
    frags = constraint_fragments(style, adapter)
    for render in sheet:
        for phrase in frags["positive"]:
            assert phrase in render["prompt"], f"{phrase!r} missing from the prompt"
        assert render["negative_prompt"] is None


# ------------------------------------------------------------- anatomy rule
def test_anatomy_counts_are_always_in_the_prompt():
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    for creature in load_creature_specs(CREATURE_DIR):
        if not creature.get("anatomy"):
            continue
        anatomy = creature["anatomy"]
        counts = (f"{anatomy['limb_count']} limbs, {anatomy['eye_count']} eyes, "
                  f"{anatomy['horn_count']} horns")
        for render in build_creature_sheet(creature, style, adapter):
            assert counts in render["prompt"], \
                f"{creature['name']}: anatomy counts missing from the prompt"


def test_habitat_sheets_carry_the_canonical_silhouette():
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    habitats = [c for c in load_creature_specs(CREATURE_DIR) if not c.get("anatomy")]
    assert habitats
    for creature in habitats:
        sheet = build_creature_sheet(creature, style, adapter)
        assert creature["canonical_silhouette"].split(";")[0][:40] in sheet[0]["prompt"]


# ------------------------------------------------------ deterministic job
def test_spec_to_prompt_to_job_file_is_deterministic(tmp_path):
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    creature = load_creature_specs(CREATURE_DIR)[0]

    job_a = build_sheet_job("speculative_evolution", creature,
                            build_creature_sheet(creature, style, adapter),
                            adapter)
    job_b = build_sheet_job("speculative_evolution", creature,
                            build_creature_sheet(creature, style, adapter),
                            adapter)
    assert json.dumps(job_a, sort_keys=True) == json.dumps(job_b, sort_keys=True)

    out = tmp_path / "job.json"
    out.write_text(json.dumps(job_a, indent=2), encoding="utf-8")
    again = tmp_path / "job2.json"
    again.write_text(json.dumps(job_b, indent=2), encoding="utf-8")
    assert out.read_bytes() == again.read_bytes()


def test_job_file_carries_the_model_contract_and_the_prompts():
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    creature = load_creature_specs(CREATURE_DIR)[0]
    job = build_sheet_job("speculative_evolution", creature,
                          build_creature_sheet(creature, style, adapter), adapter)
    assert job["model"] == adapter.key
    assert job["model_id"] == adapter.model_id
    assert job["model_config"]["pipeline_candidates"] == \
        list(adapter.pipeline_candidates)
    assert len(job["renders"]) == len(CANONICAL_VIEWS)
    assert all(r["prompt"] for r in job["renders"])
    assert all(r["seed"] for r in job["renders"])
    assert job["style"]["niche_id"] == "speculative_evolution"


def test_sheet_has_the_three_canonical_views_and_unique_seeds():
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    plan = build_sheet_plan("speculative_evolution", adapter)
    assert plan["creatures"]
    seeds = []
    for entry in plan["creatures"]:
        views = [r["view"] for r in entry["renders"]]
        assert views == list(CANONICAL_VIEWS)
        seeds.extend(r["seed"] for r in entry["renders"])
    assert len(seeds) == len(set(seeds)), "a seed is reused inside the batch"


# -------------------------------------------------------- reference policy
def test_reference_workflow_is_declared_only_with_a_card_citation():
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    creature = load_creature_specs(CREATURE_DIR)[0]
    job = build_sheet_job("speculative_evolution", creature,
                          build_creature_sheet(creature, style, adapter), adapter)
    support = REFERENCE_IMAGE_SUPPORT[adapter.key]
    if support["supported"]:
        assert support["card"].startswith("http")
        assert support["accessed"]
        refs = [r.get("reference_render_id") for r in job["renders"]]
        assert any(refs), "the reference workflow must be declared"
        front = job["renders"][0]["render_id"]
        assert refs[1:] == [front, front]
    else:
        assert all(r.get("reference_render_id") is None for r in job["renders"])


def test_the_locked_model_card_supports_multi_reference():
    support = REFERENCE_IMAGE_SUPPORT["klein"]
    assert support["supported"] is True
    assert "FLUX.2-klein-4B" in support["card"]
    assert support["accessed"] == "2026-10-22"


def test_klein_without_card_support_falls_back_to_seed_anchoring(monkeypatch):
    """No card evidence -> no reference workflow, seed + prompt anchoring only."""
    from tools.illustration import style_kit

    monkeypatch.setitem(style_kit.REFERENCE_IMAGE_SUPPORT, "klein",
                        {"supported": False, "reason": "no card evidence"})
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    creature = load_creature_specs(CREATURE_DIR)[0]
    job = build_sheet_job("speculative_evolution", creature,
                          build_creature_sheet(creature, style, adapter), adapter)
    assert all(r.get("reference_render_id") is None for r in job["renders"])
    assert all(r["seed"] for r in job["renders"])


# ------------------------------------------------------ creature spec bridge
def test_creature_spec_from_yaml_uses_the_style_file():
    style = load_style("speculative_evolution")
    data = load_creature_specs(CREATURE_DIR)[0]
    spec = creature_spec_from_yaml(data, style)
    assert spec.subject
    assert spec.palette == style.palette
    assert spec.style.startswith(style.line_style["prompt_phrase"])
    assert any("silhouette" in f for f in spec.anatomy.dominant_features)


def test_creature_specs_are_read_only_inputs():
    """The OpenCode YAML specs must not be modified by the kit."""
    before = {p.name: p.read_bytes()
              for p in sorted(CREATURE_DIR.glob("*.yaml"))}
    engine = load_engine()
    adapter = active_adapter(engine)
    style = load_style("speculative_evolution")
    for creature in load_creature_specs(CREATURE_DIR):
        build_creature_sheet(creature, style, adapter)
    after = {p.name: p.read_bytes()
             for p in sorted(CREATURE_DIR.glob("*.yaml"))}
    assert before == after
