"""AGENT_GUIDE.md is a short router; the procedures live in docs/agent-guide/.

`CLAUDE.md` / `AGENTS.md` make the guide a mandatory read before every reply.
At 50 KB that was ~12k tokens per message whether or not the message had
anything to do with producing a video. It is now a router that states every
binding rule in brief and names the section to read before each kind of step.

These tests keep the split honest: the router stays small, every section is
reachable from it, every heading that skills cite by name is still in it, and
the rules that must be seen by a fresh session are in the router itself.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "AGENT_GUIDE.md"
SECTIONS_DIR = ROOT / "docs" / "agent-guide"
SECTION_FILES = sorted(SECTIONS_DIR.glob("*.md"))

# Bytes. The pre-split guide was 50,059. Raise this only on purpose.
ROUTER_BUDGET = 26_000


def _guide() -> str:
    return GUIDE.read_text(encoding="utf-8")


def test_router_stays_within_its_budget():
    size = len(GUIDE.read_bytes())
    assert size <= ROUTER_BUDGET, (
        f"AGENT_GUIDE.md is {size} bytes (budget {ROUTER_BUDGET}). It is read before "
        f"every reply: move procedures into docs/agent-guide/ instead of growing it."
    )


def test_there_are_section_files():
    assert len(SECTION_FILES) >= 5


@pytest.mark.parametrize("section", SECTION_FILES, ids=lambda p: p.name)
def test_every_section_is_linked_from_the_router_and_links_back(section):
    rel = section.relative_to(ROOT).as_posix()
    assert f"]({rel})" in _guide(), f"{rel} is not linked from AGENT_GUIDE.md — it would never be read"
    text = section.read_text(encoding="utf-8")
    assert "](../../AGENT_GUIDE.md)" in text
    assert "**Read this in full " in text.split("\n## ")[0], f"{rel} does not say when to read it"


def test_router_links_resolve():
    for target in re.findall(r"\]\((docs/agent-guide/[^)#]+)\)", _guide()):
        assert (ROOT / target).is_file(), f"AGENT_GUIDE.md links to missing {target}"


def _cited_headings() -> set[str]:
    """Section titles that skills and docs cite as `AGENT_GUIDE.md → "Title"`."""
    cited = set()
    pattern = re.compile(r"AGENT_GUIDE\.md`?\s*(?:→|>|->)\s*\"([^\"]+)\"")
    for path in [*ROOT.glob("skills/**/*.md"), *ROOT.glob("docs/**/*.md")]:
        for title in pattern.findall(path.read_text(encoding="utf-8")):
            # citations wrap across lines and sometimes end a sentence
            cited.add(" ".join(title.split()).rstrip(".,;:"))
    return cited


def test_headings_cited_by_skills_are_still_in_the_router():
    cited = _cited_headings()
    assert cited, "no citations found — did the regex drift?"
    guide = _guide()
    headings = {m.strip() for m in re.findall(r"(?m)^#{2,3} (.+)$", guide)}
    for title in sorted(cited):
        assert any(title in heading for heading in headings), (
            f'skills cite AGENT_GUIDE.md → "{title}", which is no longer a heading there'
        )


@pytest.mark.parametrize(
    "rule",
    [
        # Rule Zero and the gates
        "Every video production request MUST go through the pipeline system",
        "END YOUR TURN",
        "Approval is per-gate",
        "GATE VIOLATION",
        # decisions
        "append-only history, not a scratchpad",
        "MUST present both options to the user",
        "Do not continue with a substitute path until the user approves",
        # motion
        "Still-image fallback is forbidden",
        "Silent runtime swap is forbidden",
        # layers
        "Layer 3 is not optional",
        # this audit: one decision log, recorded spend, review trace
        "never hand-write a `decision_log.json` file",
        "Leave `cost_snapshot` out",
        "NO REVIEW",
    ],
)
def test_binding_rules_are_in_the_router_itself(rule):
    assert rule in _guide(), f"binding rule missing from AGENT_GUIDE.md: {rule!r}"


def test_router_names_the_section_for_each_kind_of_step():
    guide = _guide()
    table = guide[guide.index("## How To Use This Guide"): guide.index("## First Interaction")]
    for name in ("preflight.md", "decisions.md", "planning.md", "workspace-and-contracts.md", "layers.md"):
        assert name in table
    # each summarised section says to read the full one
    assert guide.count("in full") >= 5
