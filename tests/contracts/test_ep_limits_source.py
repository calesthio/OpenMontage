"""Executive-producer limits come from the pipeline manifest, not the skill.

Each manifest's ``orchestration`` block holds the run's limits
(``max_revisions_per_stage``, ``max_send_backs``, ``max_wall_time_minutes``,
``budget_default_usd``). The executive-producer (EP) skill it points to must
name those fields instead of hard-coding numbers of its own: a number in the
skill drifts from the manifest the moment either one is edited, and the agent
then follows whichever it read last.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from lib.pipeline_loader import list_pipelines, load_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

LIMIT_FIELDS = (
    "max_revisions_per_stage",
    "max_send_backs",
    "max_wall_time_minutes",
)

# Table row label -> manifest field the row must name.
LIMIT_ROWS = {
    "Max revisions per stage": "orchestration.max_revisions_per_stage",
    "Max total send-backs": "orchestration.max_send_backs",
    "Max total wall-time": "orchestration.max_wall_time_minutes",
}


def _ep_skills() -> list[tuple[str, str]]:
    out = []
    for name in sorted(list_pipelines()):
        skill = (load_pipeline(name).get("orchestration") or {}).get("skill")
        if skill:
            out.append((name, skill))
    return out


EP_SKILLS = _ep_skills()


def _ep_text(skill: str) -> str:
    path = SKILLS_DIR / f"{skill}.md"
    assert path.is_file(), f"orchestration.skill {skill!r} has no file at {path}"
    return path.read_text(encoding="utf-8")


def _row(text: str, label: str) -> str | None:
    """The cells after ``label`` on its table row, or None if there is no row."""
    match = re.search(
        rf"^\|\s*{re.escape(label)}\s*\|(.*)$", text, flags=re.MULTILINE
    )
    return match.group(1) if match else None


def test_some_pipeline_has_an_ep_skill() -> None:
    assert EP_SKILLS, "no manifest declares orchestration.skill; the test checks nothing"


@pytest.mark.parametrize(("pipeline", "skill"), EP_SKILLS)
def test_ep_manifest_sets_each_limit_field(pipeline: str, skill: str) -> None:
    # The EP skill names these fields instead of numbers, so a manifest that
    # leaves one unset silently removes that limit from the run.
    orchestration = load_pipeline(pipeline).get("orchestration") or {}
    missing = [field for field in LIMIT_FIELDS if field not in orchestration]
    assert not missing, f"pipeline_defs/{pipeline}.yaml orchestration lacks {missing}"


@pytest.mark.parametrize(("pipeline", "skill"), EP_SKILLS)
def test_ep_skill_names_each_limit_field(pipeline: str, skill: str) -> None:
    text = _ep_text(skill)
    missing = [field for field in LIMIT_FIELDS if field not in text]
    assert not missing, (
        f"{pipeline}: {skill}.md never names manifest field(s) {missing}; "
        f"the EP must read its limits from pipeline_defs/{pipeline}.yaml"
    )


@pytest.mark.parametrize(("pipeline", "skill"), EP_SKILLS)
def test_ep_limit_rows_name_the_field_not_a_number(pipeline: str, skill: str) -> None:
    text = _ep_text(skill)
    problems = []
    for label, field in LIMIT_ROWS.items():
        row = _row(text, label)
        if row is None:
            problems.append(f"no table row labelled {label!r}")
            continue
        if re.search(r"\d", row):
            problems.append(f"{label!r} row hard-codes a number: |{row.strip()}")
        if field not in row:
            problems.append(f"{label!r} row does not name `{field}`")
    assert not problems, f"{pipeline}: {skill}.md\n  " + "\n  ".join(problems)


@pytest.mark.parametrize(("pipeline", "skill"), EP_SKILLS)
def test_ep_budget_row_matches_cost_tracker(pipeline: str, skill: str) -> None:
    """The budget is resolve_budget_usd's, enforced per config.yaml budget.mode."""
    text = _ep_text(skill)
    row = _row(text, "Max total budget")
    assert row is not None, f"{pipeline}: {skill}.md has no 'Max total budget' row"
    for needle in ("budget_default_usd", "budget.total_usd", "budget.mode"):
        assert needle in row, f"{pipeline}: 'Max total budget' row does not name `{needle}`"
    assert "hard stop" not in text.lower(), (
        f"{pipeline}: {skill}.md claims a hard stop on spending; only "
        f"budget.mode: cap refuses a paid call, observe and warn never block"
    )
