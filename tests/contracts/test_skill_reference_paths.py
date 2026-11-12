"""Fail when a skill or doc cites a repo path that does not exist (#799)."""

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]
CITE = re.compile(r"`((?:docs|remotion-composer/public/demo-props)/[^`\s]+)`")
SKIP = ("<", ">", "*", "$")


def _citations():
    files = [*ROOT.glob("skills/**/*.md"), *ROOT.glob("docs/**/*.md")]
    for path in sorted(files):
        for target in CITE.findall(path.read_text(encoding="utf-8")):
            if not any(marker in target for marker in SKIP):
                yield path.relative_to(ROOT).as_posix(), target


CASES = list(_citations())
assert CASES, "no citations found — did the regex drift?"


@pytest.mark.parametrize(("source", "target"), CASES, ids=[f"{s}:{t}" for s, t in CASES])
def test_cited_path_exists(source, target):
    assert (ROOT / target).exists(), f"{source} cites missing {target}"
