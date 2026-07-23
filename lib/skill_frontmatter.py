"""Skill frontmatter parsing and validation (RFC #349 phase 1).

Parses the optional YAML frontmatter block at the top of a skill Markdown
file and validates it against schemas/skills/skill_frontmatter.schema.json.
This is metadata only — no interpolation, no execution. A skill file with
no leading `---` block is left entirely alone; legacy prose skills are
unaffected by this module's existence.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import jsonschema
import yaml

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "schemas"
    / "skills"
    / "skill_frontmatter.schema.json"
)

_DELIMITER = "---"


class SkillFrontmatterError(ValueError):
    """Raised when a skill's frontmatter is missing, invalid, or mismatched."""


@lru_cache(maxsize=1)
def _load_frontmatter_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def _extract_frontmatter_block(text: str) -> Optional[str]:
    """Return the raw YAML between the leading --- delimiters, or None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _DELIMITER:
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIMITER:
            return "\n".join(lines[1:i])
    return None


def has_frontmatter(path: Path) -> bool:
    """Cheap check: does this skill file start with a --- frontmatter block?

    Does not validate the block's contents.
    """
    text = Path(path).read_text()
    return _extract_frontmatter_block(text) is not None


def load_skill_frontmatter(path: Path) -> dict[str, Any]:
    """Parse and validate a skill file's frontmatter block.

    Raises SkillFrontmatterError if the block is missing, fails schema
    validation, or its `name` field doesn't match the file's stem.
    """
    path = Path(path)
    text = path.read_text()
    block = _extract_frontmatter_block(text)
    if block is None:
        raise SkillFrontmatterError(f"No frontmatter block found in {path}")

    frontmatter = yaml.safe_load(block)
    schema = _load_frontmatter_schema()
    try:
        jsonschema.validate(instance=frontmatter, schema=schema)
    except jsonschema.ValidationError as e:
        raise SkillFrontmatterError(f"Invalid frontmatter in {path}: {e.message}") from e

    if frontmatter["name"] != path.stem:
        raise SkillFrontmatterError(
            f"Frontmatter name {frontmatter['name']!r} does not match "
            f"filename stem {path.stem!r} in {path}"
        )

    return frontmatter


def list_skills_with_frontmatter(skills_dir: Optional[Path] = None) -> list[Path]:
    """Return all skill Markdown files under skills_dir that have a frontmatter block.

    Does not validate — a file can be returned here and still fail
    load_skill_frontmatter() if its block is malformed.
    """
    skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR
    return sorted(p for p in skills_dir.rglob("*.md") if has_frontmatter(p))
