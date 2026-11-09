"""Agent definition loader.

Loads and validates Claude Code subagent definitions from .claude/agents/*.md.
Each definition is a markdown file with YAML frontmatter validated against
schemas/agents/agent_definition.schema.json. The contract test in
tests/contracts/test_agent_definition_contracts.py runs validate_all_agents()
over the real directory so a malformed agent file fails CI.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import jsonschema
import yaml

from lib.paths import REPO_ROOT

AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
SCHEMA_PATH = REPO_ROOT / "schemas" / "agents" / "agent_definition.schema.json"

_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.DOTALL)


class AgentDefinitionError(ValueError):
    """Raised when an agent definition file violates the contract."""


@lru_cache(maxsize=1)
def _load_agent_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def parse_agent_markdown(text: str) -> tuple[dict[str, Any], str]:
    """Split an agent markdown document into (frontmatter dict, body).

    Raises:
        AgentDefinitionError: If the frontmatter block is missing, is not
            valid YAML, or does not parse to a mapping.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise AgentDefinitionError(
            "Missing YAML frontmatter: file must start with '---' and close "
            "the block with '---' on its own line"
        )

    raw_yaml, body = match.group(1), match.group(2)
    try:
        frontmatter = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise AgentDefinitionError(f"Frontmatter is not valid YAML: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise AgentDefinitionError(
            f"Frontmatter must be a YAML mapping, got {type(frontmatter).__name__}"
        )
    return frontmatter, body


def validate_agent_frontmatter(frontmatter: dict) -> None:
    """Validate a frontmatter dict against the agent definition schema."""
    schema = _load_agent_schema()
    try:
        jsonschema.validate(instance=frontmatter, schema=schema)
    except jsonschema.ValidationError as exc:
        raise AgentDefinitionError(f"Frontmatter schema violation: {exc.message}") from exc


def load_agent(path: Path) -> dict[str, Any]:
    """Load and fully validate one agent definition file.

    Beyond schema validation this enforces the file-level contract:
    the frontmatter name must equal the file stem (so the identifier the
    harness uses matches the file it loads), and the body must contain
    actual instructions.

    Returns:
        Dict with name, frontmatter, body, and path.

    Raises:
        FileNotFoundError: If path does not exist.
        AgentDefinitionError: On any contract violation.
    """
    if not path.exists():
        raise FileNotFoundError(f"Agent definition not found: {path}")

    frontmatter, body = parse_agent_markdown(path.read_text(encoding="utf-8"))
    validate_agent_frontmatter(frontmatter)

    name = frontmatter["name"]
    if name != path.stem:
        raise AgentDefinitionError(
            f"Frontmatter name {name!r} must match the file stem {path.stem!r}"
        )
    if not body.strip():
        raise AgentDefinitionError("Agent body is empty: no instructions after frontmatter")

    return {"name": name, "frontmatter": frontmatter, "body": body, "path": path}


def list_agents(agents_dir: Optional[Path] = None) -> list[Path]:
    """List agent definition files, sorted for deterministic output."""
    agents_dir = agents_dir or AGENTS_DIR
    if not agents_dir.is_dir():
        return []
    return sorted(agents_dir.glob("*.md"))


def validate_all_agents(agents_dir: Optional[Path] = None) -> list[dict[str, str]]:
    """Validate every agent definition in a directory.

    Returns:
        A list of issues, one per invalid file: {"file": ..., "error": ...}.
        An empty list means every definition passes.
    """
    issues: list[dict[str, str]] = []
    for path in list_agents(agents_dir):
        try:
            load_agent(path)
        except (AgentDefinitionError, UnicodeDecodeError, FileNotFoundError, OSError) as exc:
            issues.append({"file": str(path), "error": str(exc)})
    return issues
