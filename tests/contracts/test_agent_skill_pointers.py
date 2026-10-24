"""Every `agent_skills` pointer a tool advertises must resolve for every agent.

AGENT_GUIDE.md makes Layer 3 mandatory:

    Every generation tool has an `agent_skills` field listing its Layer 3
    skills. [...] Read them before writing prompts. Layer 3 is not optional.

A pointer that resolves to nothing cannot be read, so the mandated step is
silently skipped — and `tts_selector` republishes the list to its caller as
`required_agent_skills`, propagating the dead name.

Two roots, not one
------------------
`.agents/skills/` is the source of truth. Claude Code reads `.claude/skills/`.
An earlier revision of this test checked only `.agents/`, so `.claude/` was
free to rot: it drifted to 49 of 90 skills, and two of the 49 that remained
went stale (`ai-video-gen` lost the Kling Official provider for seven weeks).
Both roots are now asserted, and `test_skill_roots_agree` fails the moment
they diverge again.

The registry is iterated rather than named so a newly added tool is covered
the moment it is discovered.
"""

from pathlib import Path

import pytest

from tools.tool_registry import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_SKILLS = REPO_ROOT / ".agents" / "skills"
CLAUDE_SKILLS = REPO_ROOT / ".claude" / "skills"

# Every root an agent may load Layer 3 from. Add a root here and it is
# enforced everywhere below — no other edit needed.
SKILL_ROOTS = (
    ("agents", AGENTS_SKILLS),
    ("claude", CLAUDE_SKILLS),
)


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

# One case per (root, tool, skill) so a failure names the agent it breaks.
ROOTED_POINTERS = [
    (label, root, tool, skill)
    for label, root in SKILL_ROOTS
    for tool, skill in POINTERS
]


def _skill_names(root: Path) -> set[str]:
    """Skill names published under a root, following symlinks."""
    if not root.is_dir():
        return set()
    names = set()
    for entry in root.iterdir():
        if entry.is_dir() and (entry / "SKILL.md").is_file():
            names.add(entry.name)
        elif entry.is_file() and entry.suffix == ".md" and entry.stem != "INDEX":
            names.add(entry.stem)
    return names


def _resolves(root: Path, skill: str) -> bool:
    return (root / skill / "SKILL.md").is_file() or (root / f"{skill}.md").is_file()


def test_registry_actually_discovered_tools() -> None:
    assert TOOLS, "registry.discover() found no tools"


def test_some_tools_declare_layer_three_skills() -> None:
    """Guard against the parametrized test below silently covering nothing."""
    assert POINTERS


@pytest.mark.parametrize(("label", "root", "tool", "skill"), ROOTED_POINTERS,
                         ids=lambda v: str(v.name if isinstance(v, Path) else v))
def test_agent_skill_pointer_resolves(label: str, root: Path, tool: str, skill: str) -> None:
    """Regression: four pointers named skills that do not exist.

    - hyperframes_compose -> `website-to-hyperframes`, renamed upstream to
      `website-to-video` (recorded in .agents/skills/hyperframes/PROVENANCE.md)
    - openai_tts, tts_selector -> `openai-docs`, never vendored
    - screen_capture_selector -> `screen-demo`, which names the Layer 2
      pipeline directory rather than a Layer 3 skill

    And the `.claude` root regression: 26 skills that 45 tools declare as
    required reading were absent from the mirror entirely.
    """
    assert _resolves(root, skill), (
        f"{tool} advertises agent_skill {skill!r}, but neither "
        f"{root.name}/{skill}/SKILL.md nor {root.name}/{skill}.md exists "
        f"under the {label!r} skill root ({root})"
    )


def test_skill_roots_agree() -> None:
    """`.claude/skills` must publish exactly what `.agents/skills` does.

    INDEX.md documents `.claude/skills/` as symlinks into `.agents/skills/`.
    Keeping that literally true is the cheapest way to hold this invariant;
    a generated copy passes just as well, but drift does not.
    """
    agents = _skill_names(AGENTS_SKILLS)
    claude = _skill_names(CLAUDE_SKILLS)
    assert agents, ".agents/skills published no skills"
    missing = sorted(agents - claude)
    extra = sorted(claude - agents)
    assert not missing and not extra, (
        f"skill roots diverged — missing from .claude/skills: {missing}; "
        f"present only in .claude/skills: {extra}"
    )


@pytest.mark.parametrize("skill", sorted(_skill_names(AGENTS_SKILLS)))
def test_mirrored_skill_content_matches(skill: str) -> None:
    """A mirrored SKILL.md must not drift from its source.

    Regression: `.claude/skills/ai-video-gen/SKILL.md` sat seven weeks behind
    its `.agents` counterpart and never mentioned the Kling Official provider,
    so Claude Code could not learn that `kling_official_video` existed.
    """
    source = AGENTS_SKILLS / skill / "SKILL.md"
    mirror = CLAUDE_SKILLS / skill / "SKILL.md"
    if not source.is_file():
        pytest.skip(f"{skill} is published as a flat .md, not a directory")
    assert mirror.is_file(), f"{skill} is not mirrored into .claude/skills"
    assert mirror.read_bytes() == source.read_bytes(), (
        f".claude/skills/{skill}/SKILL.md has drifted from "
        f".agents/skills/{skill}/SKILL.md"
    )
