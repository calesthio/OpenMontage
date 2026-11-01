"""Every `agent_skills` pointer a tool advertises must resolve to a real skill.

AGENT_GUIDE.md makes Layer 3 mandatory:

    Every generation tool has an `agent_skills` field listing its Layer 3
    skills. [...] Read them before writing prompts. Layer 3 is not optional.

A pointer that resolves to nothing cannot be read, so the mandated step is
silently skipped — and `tts_selector` republishes the list to its caller as
`required_agent_skills`, propagating the dead name.

The registry is iterated rather than named so a newly added tool is covered
the moment it is discovered.
"""

from pathlib import Path

import pytest

from tools.tool_registry import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / ".agents" / "skills"


def _discovered_tools() -> list[tuple[str, list[str]]]:
    registry.discover()
    pairs: list[tuple[str, list[str]]] = []
    for name, tool in sorted(registry._tools.items()):
        try:
            info = tool.get_info()
        except Exception:  # a tool that cannot introspect is another test's problem
            continue
        pairs.append((name, list(info.get("agent_skills") or [])))
    return pairs


TOOLS = _discovered_tools()
POINTERS = [(name, skill) for name, skills in TOOLS for skill in skills]


def _resolves(skill: str) -> bool:
    return (SKILLS_ROOT / skill / "SKILL.md").exists() or (
        SKILLS_ROOT / f"{skill}.md"
    ).exists()


def test_registry_actually_discovered_tools() -> None:
    assert TOOLS, "registry.discover() found no tools"


def test_some_tools_declare_layer_three_skills() -> None:
    """Guard against the parametrized test below silently covering nothing."""
    assert POINTERS


@pytest.mark.parametrize(("tool", "skill"), POINTERS, ids=lambda v: str(v))
def test_agent_skill_pointer_resolves(tool: str, skill: str) -> None:
    """Regression: four pointers named skills that do not exist.

    - hyperframes_compose -> `website-to-hyperframes`, renamed upstream to
      `website-to-video` (recorded in .agents/skills/hyperframes/PROVENANCE.md)
    - openai_tts, tts_selector -> `openai-docs`, never vendored
    - screen_capture_selector -> `screen-demo`, which names the Layer 2
      pipeline directory rather than a Layer 3 skill
    """
    assert _resolves(skill), (
        f"{tool} advertises agent_skill {skill!r}, but neither "
        f".agents/skills/{skill}/SKILL.md nor .agents/skills/{skill}.md exists"
    )
