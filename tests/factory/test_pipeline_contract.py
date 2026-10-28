"""The business-documentary manifest must load and stay internally consistent.

A manifest that fails its schema is silently ignored by
``lib.checkpoint.get_pipeline_stages`` (it falls back to the canonical
stage list), which means the run executes against the WRONG stage order
without its approval gates. These tests catch that by loading the manifest
for real and cross-checking every declaration against the repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lib.checkpoint import _stage_requires_approval, get_pipeline_stages
from lib.pipeline_loader import get_stage_skill, load_pipeline
from tools.tool_registry import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = "business-documentary"
SKILLS_ROOT = REPO_ROOT / "skills"

# Master Plan section 4 — the twelve stages, in order.
EXPECTED_STAGES = [
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
    "qa",
    "publish",
]

# Executive producer + one director per stage.
EXPECTED_SKILL_COUNT = 13


@pytest.fixture(scope="module")
def manifest() -> dict:
    loaded = load_pipeline(PIPELINE)
    assert loaded, "manifest did not load"
    return loaded


def _registry_tool_names() -> set[str]:
    registry.discover()
    return set(registry._tools.keys())


def test_manifest_declares_the_twelve_planned_stages(manifest) -> None:
    assert [stage["name"] for stage in manifest["stages"]] == EXPECTED_STAGES


def test_effective_stage_order_matches_the_manifest() -> None:
    # A manifest that fails to load makes get_pipeline_stages fall back to
    # the canonical 9-stage list; that fallback would silently hide here.
    assert get_pipeline_stages(PIPELINE) == EXPECTED_STAGES


def test_strict_zero_cost_is_the_default_budget(manifest) -> None:
    assert manifest["orchestration"]["budget_default_usd"] == 0.0


def test_thirteen_director_skills_are_referenced(manifest) -> None:
    skills = set(manifest["required_skills"])
    stage_skills = {
        skill
        for skill in (get_stage_skill(manifest, stage) for stage in EXPECTED_STAGES)
        if skill
    }
    factory_skills = {
        s for s in skills if s.startswith("pipelines/business-documentary/")
    }
    assert len(factory_skills) == EXPECTED_SKILL_COUNT
    assert stage_skills <= skills


@pytest.mark.parametrize("skill", sorted({
    "executive-producer",
    "topic-director",
    "research-director",
    "evidence-director",
    "script-director",
    "factcheck-director",
    "storyboard-director",
    "narration-director",
    "footage-director",
    "editorial-director",
    "compose-director",
    "qa-director",
    "publish-director",
}))
def test_director_skill_file_exists(skill: str) -> None:
    path = SKILLS_ROOT / "pipelines" / PIPELINE / f"{skill}.md"
    assert path.exists(), f"missing director skill: {path}"
    text = path.read_text(encoding="utf-8")
    assert len(text.splitlines()) > 20, f"{skill}.md is too thin to direct a stage"


def test_every_stage_declares_a_skill_and_an_artifact(manifest) -> None:
    for stage in manifest["stages"]:
        name = stage["name"]
        assert stage.get("skill"), f"{name} has no director skill"
        assert stage.get("produces"), f"{name} produces no artifact"


def test_every_declared_tool_is_a_real_registry_tool(manifest) -> None:
    """A typo in a stage's tool list would surface as a missing tool at
    runtime, mid-run. Fail here instead."""

    known = _registry_tool_names()
    declared: set[str] = set()
    for stage in manifest["stages"]:
        for key in ("required_tools", "optional_tools", "tools_available"):
            declared.update(stage.get(key) or [])

    unknown = sorted(declared - known)
    assert not unknown, f"manifest declares tools that are not registered: {unknown}"


def test_declared_approval_gates_are_enforceable(manifest) -> None:
    raw = yaml.safe_load(
        (REPO_ROOT / "pipeline_defs" / f"{PIPELINE}.yaml").read_text(encoding="utf-8")
    )
    for stage in raw["stages"]:
        if "human_approval_default" not in stage:
            continue
        resolved = _stage_requires_approval(PIPELINE, stage["name"])
        assert resolved == stage["human_approval_default"]


def test_publish_and_fact_check_are_gated_on_a_human(manifest) -> None:
    # Master Plan: publication is manual; fact-check failures block the run.
    assert manifest["stages"][-1]["name"] == "publish"
    assert _stage_requires_approval(PIPELINE, "publish") is True
    assert _stage_requires_approval(PIPELINE, "fact_check") is True


def test_no_required_tool_is_paid_only(manifest) -> None:
    """Required tools must be usable at $0 on a default machine.

    `video_compose` (ffmpeg) and `direct_clip_search` (no-key archives) are
    the two required tools; both are local/zero-cost paths.
    """

    required: set[str] = set()
    for stage in manifest["stages"]:
        required.update(stage.get("required_tools") or [])
    assert required == {"video_compose", "direct_clip_search"}
    registry.discover()
    for name in sorted(required):
        info = registry._tools[name].get_info()
        assert info.get("status") == "available", (
            f"{name} must be available on a default machine, got {info.get('status')}"
        )
        assert str(info.get("runtime")).lower() in {"local", "hybrid"}, (
            f"{name} must be a local/hybrid zero-cost path, got {info.get('runtime')}"
        )
