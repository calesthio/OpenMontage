"""Contract tests for Claude Code agent definitions.

Every file in .claude/agents/ must carry valid frontmatter per
schemas/agents/agent_definition.schema.json, with a name matching its file
stem and a non-empty instruction body. This is the CI gate that keeps
malformed agent definitions out of the repo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from lib.agent_loader import AGENTS_DIR, SCHEMA_PATH, list_agents, load_agent, validate_all_agents  # noqa: E402


def test_agent_schema_is_itself_valid():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)


def test_agents_directory_has_definitions():
    assert list_agents(), f"No agent definitions found in {AGENTS_DIR}"


@pytest.mark.parametrize("path", list_agents(), ids=lambda p: p.name)
def test_each_agent_definition_is_valid(path):
    agent = load_agent(path)
    assert agent["name"] == path.stem


def test_no_agent_definition_issues():
    issues = validate_all_agents()
    assert issues == [], "Invalid agent definitions:\n" + "\n".join(
        f"  {i['file']}: {i['error']}" for i in issues
    )


def test_agent_names_are_unique():
    names = [load_agent(p)["name"] for p in list_agents()]
    assert len(names) == len(set(names)), f"Duplicate agent names: {names}"
