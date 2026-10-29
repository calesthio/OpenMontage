"""Unit tests for lib/agent_loader.py.

Covers frontmatter parsing, schema validation, and the file-level contract
(name/stem match, non-empty body) using synthetic files in tmp_path.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.agent_loader import (  # noqa: E402
    AgentDefinitionError,
    list_agents,
    load_agent,
    parse_agent_markdown,
    validate_agent_frontmatter,
    validate_all_agents,
)

VALID_DOC = """---
name: test-agent
description: A test agent that exists only to exercise the loader contract.
color: amber
emoji: 🧪
vibe: Validates things.
---

# Test Agent

You are a test agent.
"""


def _write(tmp_path: Path, filename: str, text: str) -> Path:
    path = tmp_path / filename
    path.write_text(text, encoding="utf-8")
    return path


# --- parse_agent_markdown ---------------------------------------------------

def test_parse_valid_document():
    frontmatter, body = parse_agent_markdown(VALID_DOC)
    assert frontmatter["name"] == "test-agent"
    assert frontmatter["emoji"] == "🧪"
    assert "# Test Agent" in body


def test_parse_missing_frontmatter_raises():
    with pytest.raises(AgentDefinitionError, match="Missing YAML frontmatter"):
        parse_agent_markdown("# Just markdown, no frontmatter\n")


def test_parse_unclosed_frontmatter_raises():
    with pytest.raises(AgentDefinitionError, match="Missing YAML frontmatter"):
        parse_agent_markdown("---\nname: test-agent\n# body without closing fence\n")


def test_parse_non_mapping_frontmatter_raises():
    with pytest.raises(AgentDefinitionError, match="YAML mapping"):
        parse_agent_markdown("---\n- just\n- a\n- list\n---\nbody\n")


def test_parse_invalid_yaml_raises():
    with pytest.raises(AgentDefinitionError, match="not valid YAML"):
        parse_agent_markdown("---\nname: [unclosed\n---\nbody\n")


# --- validate_agent_frontmatter ----------------------------------------------

def test_valid_frontmatter_passes():
    validate_agent_frontmatter({
        "name": "image-prompt-engineer",
        "description": "Crafts detailed prompts for AI image generation.",
        "color": "#e63946",
    })


def test_missing_description_rejected():
    with pytest.raises(AgentDefinitionError, match="schema violation"):
        validate_agent_frontmatter({"name": "no-description"})


@pytest.mark.parametrize("bad_name", [
    "Image Prompt Engineer",   # spaces + uppercase
    "SRE",                     # uppercase
    "double--hyphen",
    "-leading-hyphen",
    "trailing-hyphen-",
    "",
])
def test_bad_names_rejected(bad_name):
    with pytest.raises(AgentDefinitionError, match="schema violation"):
        validate_agent_frontmatter({
            "name": bad_name,
            "description": "A description long enough to pass the length check.",
        })


def test_short_description_rejected():
    with pytest.raises(AgentDefinitionError, match="schema violation"):
        validate_agent_frontmatter({"name": "short-desc", "description": "too short"})


def test_bad_color_rejected():
    with pytest.raises(AgentDefinitionError, match="schema violation"):
        validate_agent_frontmatter({
            "name": "bad-color",
            "description": "A description long enough to pass the length check.",
            "color": "#12345",  # 5-digit hex
        })


def test_tools_accepts_string_and_list():
    base = {
        "name": "tooled-agent",
        "description": "A description long enough to pass the length check.",
    }
    validate_agent_frontmatter({**base, "tools": "Read, Grep"})
    validate_agent_frontmatter({**base, "tools": ["Read", "Grep"]})
    with pytest.raises(AgentDefinitionError, match="schema violation"):
        validate_agent_frontmatter({**base, "tools": []})


# --- load_agent ---------------------------------------------------------------

def test_load_valid_agent(tmp_path):
    path = _write(tmp_path, "test-agent.md", VALID_DOC)
    agent = load_agent(path)
    assert agent["name"] == "test-agent"
    assert agent["path"] == path


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_agent(tmp_path / "does-not-exist.md")


def test_name_stem_mismatch_rejected(tmp_path):
    path = _write(tmp_path, "wrong-filename.md", VALID_DOC)
    with pytest.raises(AgentDefinitionError, match="match the file stem"):
        load_agent(path)


def test_empty_body_rejected(tmp_path):
    doc = "---\nname: empty-body\ndescription: A description long enough to pass.\n---\n   \n"
    path = _write(tmp_path, "empty-body.md", doc)
    with pytest.raises(AgentDefinitionError, match="body is empty"):
        load_agent(path)


# --- list_agents / validate_all_agents ----------------------------------------

def test_list_agents_missing_dir_is_empty(tmp_path):
    assert list_agents(tmp_path / "nope") == []


def test_validate_all_agents_reports_each_bad_file(tmp_path):
    _write(tmp_path, "test-agent.md", VALID_DOC)
    _write(tmp_path, "broken.md", "# no frontmatter at all\n")
    _write(tmp_path, "mismatch.md", VALID_DOC)  # name test-agent != stem mismatch

    issues = validate_all_agents(tmp_path)
    bad_files = {Path(i["file"]).name for i in issues}
    assert bad_files == {"broken.md", "mismatch.md"}


def test_validate_all_agents_clean_dir(tmp_path):
    _write(tmp_path, "test-agent.md", VALID_DOC)
    assert validate_all_agents(tmp_path) == []
