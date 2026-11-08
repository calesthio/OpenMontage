"""Every `<tool>.execute({...})` example in a skill must use real input names.

Stage-director skills are followed literally by the agent. Tools read inputs
with `inputs.get(...)`, so a misspelled key is not rejected — it is silently
ignored and the tool falls back to its default (e.g. `media_profile` instead
of `profile` makes the final encode skip the platform profile entirely), or,
for a required input, the call crashes with a KeyError.

Examples are discovered by scanning the docs and checked against the
registry's `input_schema`, so a newly added example is covered automatically.
"""

import re
from pathlib import Path

import pytest

from tools.tool_registry import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_GLOBS = ("skills/**/*.md", "docs/**/*.md", "*.md")
# tool_name.execute({ | ToolClass().execute({ | registry.get("tool_name").execute({
_CALL_RE = re.compile(
    r'(?:registry\.get\(\s*["\'](\w+)["\']\s*\)|\b(\w+)\(\)|\b(\w+))\.execute\(\{'
)

_COLON_RE = re.compile(r"[ \t]*:")


def _top_level_keys(text: str, start: int) -> list[str]:
    """Keys of the dict literal opening at text[start - 1]; [] if unterminated.

    String- and comment-aware so brackets inside values or `#` notes don't
    shift the nesting depth.
    """
    keys: list[str] = []
    depth, i, n = 1, start, len(text)
    while i < n:
        ch = text[i]
        if ch == "#":
            i = text.find("\n", i)
            if i < 0:
                return []
        elif ch in "\"'":
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if text[j] == "\\" else 1
            if depth == 1 and _COLON_RE.match(text, j + 1):
                keys.append(text[i + 1 : j])
            i = j
        elif ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
            if depth == 0:
                return keys
        i += 1
    return []


registry.discover()
_CLASS_TO_TOOL = {type(t).__name__: name for name, t in registry._tools.items()}


def _examples() -> list[tuple[str, str, list[str]]]:
    found = []
    paths = sorted({p for g in DOC_GLOBS for p in REPO_ROOT.glob(g)})
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for m in _CALL_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            where = f"{path.relative_to(REPO_ROOT).as_posix()}:{line}"
            name = m.group(1) or m.group(3) or _CLASS_TO_TOOL.get(m.group(2), m.group(2))
            found.append((where, name, _top_level_keys(text, m.end())))
    return found


EXAMPLES = _examples()


def test_examples_are_discovered():
    assert len(EXAMPLES) >= 10, "doc scan found too few execute() examples"
    assert all(keys for _, _, keys in EXAMPLES), "an example's keys could not be parsed"


@pytest.mark.parametrize(
    "where,tool_name,keys", EXAMPLES, ids=[f"{w}:{t}" for w, t, _ in EXAMPLES]
)
def test_example_inputs_exist_in_tool_schema(where, tool_name, keys):
    tool = registry.get(tool_name)
    assert tool is not None, f"{where}: no registered tool named {tool_name!r}"
    props = (tool.input_schema or {}).get("properties", {})
    unknown = [k for k in keys if k not in props]
    assert not unknown, (
        f"{where}: {tool_name}.execute() example passes {unknown}, "
        f"which the tool does not accept; valid inputs: {sorted(props)}"
    )
