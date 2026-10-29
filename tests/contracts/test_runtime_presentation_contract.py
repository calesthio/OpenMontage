"""Enforce the 'present both composition runtimes' governance contract.

For every pipeline in `pipeline_defs/`, the planning-stage skill (proposal
or idea) MUST instruct the agent about runtime selection — either by
presenting both runtimes to the user when they are a real choice, or by
surfacing the constraint when the pipeline is locked to one runtime.

This test prevents a new pipeline from being added without the conversation
contract. A fresh-session agent that reads a pipeline's planning skill and
finds no runtime guidance will silently default to Remotion — which is the
exact failure mode this contract prevents.

See:
- AGENT_GUIDE.md → "Present Both Composition Runtimes (HARD RULE)"
- skills/core/hyperframes.md → "Hard rule: present both runtimes"
- skills/meta/reviewer.md → finding #6
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_DIR = ROOT / "pipeline_defs"
SKILLS_DIR = ROOT / "skills"

# Tokens we expect in any compliant planning-stage skill. A skill needs AT
# LEAST one from each group to pass. The groups are intentionally loose —
# this test is a tripwire, not a style enforcer.
_REQUIRED_RUNTIME_TOKENS = [
    "render_runtime",      # the field name must appear
    "hyperframes",         # the alternative runtime must be named
]
# And at least one of these phrases showing the conversation-not-default contract.
_CONVERSATION_TOKENS = [
    "present both",
    "Present Both",
    "PRESENT BOTH",
    "render_runtime_selection",  # pointing at the decision_log category
]


def _planning_stages(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every 'proposal' or 'idea' stage (a pipeline may have one or both)."""
    out: list[dict[str, Any]] = []
    for stage in manifest.get("stages", []):
        if stage.get("name") in {"proposal", "idea"}:
            out.append(stage)
    return out


def _load_manifest(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_skill(skill_ref: str) -> tuple[Path, str]:
    """Resolve a manifest `skill:` string to its markdown path + contents."""
    candidate = SKILLS_DIR / f"{skill_ref}.md"
    assert candidate.is_file(), (
        f"Manifest references skill {skill_ref!r} but {candidate} does not exist."
    )
    return candidate, candidate.read_text(encoding="utf-8")


ALL_MANIFESTS = sorted(PIPELINE_DIR.glob("*.yaml"))
assert ALL_MANIFESTS, "No pipeline manifests found"

# Test-only pipelines that don't compose final video go on this list with
# an explicit reason. Everything else is required to follow the contract.
_EXCLUDED_PIPELINES = {
    "framework-smoke": "minimal 2-stage smoke test, no compose stage",
    "hermes-flywheel": "evolutionary engine: renders THROUGH base pipelines "
                       "(animated-explainer/cinematic/clip-factory/talking-head), "
                       "which carry the runtime contract; the flywheel itself has "
                       "no compose stage of its own",
}


@pytest.mark.parametrize(
    "manifest_path",
    [p for p in ALL_MANIFESTS if p.stem not in _EXCLUDED_PIPELINES],
    ids=lambda p: p.stem,
)
def test_planning_skill_mentions_runtime_contract(manifest_path: Path):
    """Every pipeline that reaches compose must have runtime guidance in its
    planning-stage skill."""
    manifest = _load_manifest(manifest_path)
    planning = _planning_stages(manifest)
    assert planning, (
        f"Pipeline {manifest_path.stem} has no 'proposal' or 'idea' stage. "
        f"Add one, or add this pipeline to _EXCLUDED_PIPELINES with a reason."
    )

    # At least ONE of the planning skills in this pipeline must cover the
    # contract (pipelines with both proposal+idea only need one to carry it).
    matched_skill: str | None = None
    matched_why: dict[str, bool] = {}
    for stage in planning:
        skill_ref = stage.get("skill")
        if not skill_ref:
            continue
        _, body = _load_skill(skill_ref)
        covers_required = all(token in body for token in _REQUIRED_RUNTIME_TOKENS)
        covers_conversation = any(token in body for token in _CONVERSATION_TOKENS)
        if covers_required and covers_conversation:
            matched_skill = skill_ref
            matched_why = {
                "mentions_render_runtime": "render_runtime" in body,
                "mentions_hyperframes": "hyperframes" in body,
                "conversation_token_found": covers_conversation,
            }
            break

    assert matched_skill, (
        f"Pipeline {manifest_path.stem}: no planning-stage skill covers the "
        f"runtime-selection contract. Each pipeline's proposal- or idea-director "
        f"must discuss render_runtime, name hyperframes, and either 'Present both' "
        f"or a `render_runtime_selection` decision. A fresh-session agent reading "
        f"this pipeline's plan would silently default to Remotion. Fix the skill "
        f"that drives the planning stage."
    )


@pytest.mark.parametrize(
    "manifest_path",
    [p for p in ALL_MANIFESTS if p.stem not in _EXCLUDED_PIPELINES],
    ids=lambda p: p.stem,
)
def test_compose_stage_references_runtime_routing(manifest_path: Path):
    """Compose stage's director skill must also cover runtime routing, so
    that even a pipeline whose planning skill somehow misses the contract
    cannot silently render under the wrong runtime."""
    manifest = _load_manifest(manifest_path)
    compose_stage = next(
        (s for s in manifest.get("stages", []) if s.get("name") == "compose"),
        None,
    )
    if compose_stage is None:
        # Some pipelines use alternate terminal stages; skip.
        pytest.skip(f"{manifest_path.stem} has no 'compose' stage")

    skill_ref = compose_stage.get("skill")
    assert skill_ref, f"{manifest_path.stem} compose stage has no skill reference"
    _, body = _load_skill(skill_ref)
    # Compose-directors must at minimum mention render_runtime AND either
    # route by runtime or surface a hard constraint (HyperFrames deferred).
    assert "render_runtime" in body, (
        f"{skill_ref} does not mention render_runtime. Compose MUST route by "
        f"render_runtime; without this instruction the agent will fall back to "
        f"the tool's legacy behavior (silently pick Remotion)."
    )
    # Must also mention HyperFrames explicitly so a reviewer can tell the
    # author considered it and either enabled or rejected it with reason.
    assert re.search(r"hyperframes|HyperFrames", body), (
        f"{skill_ref} does not mention HyperFrames at all. Even on deferred "
        f"pipelines, the compose-director must name HyperFrames so the agent "
        f"can surface the constraint to the user rather than silently pick "
        f"Remotion. See documentary-montage or talking-head compose-director "
        f"for the deferred-pipeline template."
    )


def test_agent_guide_carries_hard_rule():
    """The top-level agent contract must carry the HARD RULE banner so every
    fresh-session agent reads it before picking a pipeline."""
    guide = (ROOT / "AGENT_GUIDE.md").read_text(encoding="utf-8")
    assert "Present Both Composition Runtimes" in guide
    assert "HARD RULE" in guide
    # The rule must explicitly forbid the failure mode.
    assert "silently" in guide.lower()


def test_reviewer_has_critical_finding_for_single_option_runtime():
    """The reviewer meta-skill must treat a single-option render_runtime_selection
    as CRITICAL — otherwise the governance rule has no enforcement at review
    time and a bypass slips through unnoticed."""
    body = (SKILLS_DIR / "meta" / "reviewer.md").read_text(encoding="utf-8")
    # Locate the critical-severity rule explicitly.
    assert "render_runtime_selection" in body
    # The section must carry CRITICAL severity language tied to single-option.
    assert re.search(
        r"render_runtime_selection.{0,800}(CRITICAL|critical)",
        body,
        re.DOTALL,
    ), (
        "Reviewer skill doesn't flag single-option render_runtime_selection "
        "as CRITICAL — the conversation contract has no teeth."
    )
