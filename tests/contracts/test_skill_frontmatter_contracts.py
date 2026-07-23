"""Contract tests for skill frontmatter parsing and validation (RFC #349 phase 1)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "skills" / "skill_frontmatter.schema.json"


def test_schema_file_is_valid_json_schema():
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["required"] == ["name", "version"]


from lib.skill_frontmatter import (
    SkillFrontmatterError,
    has_frontmatter,
    load_skill_frontmatter,
)

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "skill_frontmatter"


def test_valid_frontmatter_parses():
    frontmatter = load_skill_frontmatter(FIXTURES_DIR / "valid_skill.md")
    assert frontmatter["name"] == "valid_skill"
    assert frontmatter["version"] == "1.0"
    assert frontmatter["inputs"]["topic"]["required"] is True
    assert frontmatter["outputs"]["result"] == "string"
    assert frontmatter["steps"][0]["tool"] == "some_tool"


def test_missing_required_field_raises():
    with pytest.raises(SkillFrontmatterError):
        load_skill_frontmatter(FIXTURES_DIR / "missing_required.md")


def test_name_mismatch_raises():
    with pytest.raises(SkillFrontmatterError, match="does not match"):
        load_skill_frontmatter(FIXTURES_DIR / "name_mismatch.md")


def test_has_frontmatter_false_for_legacy_file():
    assert has_frontmatter(FIXTURES_DIR / "no_frontmatter.md") is False


def test_has_frontmatter_true_for_valid_file():
    assert has_frontmatter(FIXTURES_DIR / "valid_skill.md") is True


def test_load_skill_frontmatter_raises_for_legacy_file():
    with pytest.raises(SkillFrontmatterError, match="No frontmatter block"):
        load_skill_frontmatter(FIXTURES_DIR / "no_frontmatter.md")


from lib.skill_frontmatter import list_skills_with_frontmatter


def test_list_skills_with_frontmatter_filters_legacy_files(tmp_path):
    (tmp_path / "with_frontmatter.md").write_text(
        (FIXTURES_DIR / "valid_skill.md").read_text().replace(
            "name: valid_skill", "name: with_frontmatter"
        )
    )
    (tmp_path / "legacy.md").write_text(
        (FIXTURES_DIR / "no_frontmatter.md").read_text()
    )

    result = list_skills_with_frontmatter(tmp_path)

    assert result == [tmp_path / "with_frontmatter.md"]


RIG_PLAN_DIRECTOR = (
    PROJECT_ROOT
    / "skills"
    / "pipelines"
    / "character-animation"
    / "rig-plan-director.md"
)


def test_pilot_rig_plan_director_frontmatter_validates():
    frontmatter = load_skill_frontmatter(RIG_PLAN_DIRECTOR)
    assert frontmatter["name"] == "rig-plan-director"
    assert frontmatter["inputs"]["character_design"]["required"] is True
    assert frontmatter["outputs"]["rig_plan"] == "string"
    assert frontmatter["outputs"]["pose_library"] == "string"
    tool_names = {step["tool"] for step in frontmatter["steps"]}
    assert tool_names == {"svg_rig_builder", "pose_library_builder"}
