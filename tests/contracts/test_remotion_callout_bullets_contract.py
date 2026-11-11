"""CalloutBox must render newlines and "- item" lines as separate lines/bullets.

SCENE_TYPES.md sells `callout` as a "boxed message with bullets", but the
component printed `text` as one run, so the 2026-11-11 audit render showed
its bullet list merged into a single line.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSER = REPO_ROOT / "remotion-composer"
HELPER = COMPOSER / "src" / "lib" / "calloutText.ts"


def _parse(text: str) -> list[dict]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    match = re.match(r"v(\d+)\.(\d+)", version.strip())
    if not match or (int(match.group(1)), int(match.group(2))) < (22, 6):
        pytest.skip(f"node {version.strip()} cannot strip TypeScript types")
    script = (
        f"const m = await import({json.dumps(HELPER.as_uri())});\n"
        f"console.log(JSON.stringify(m.parseCalloutText({json.dumps(text)})));\n"
    )
    proc = subprocess.run(
        [node, "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_plain_text_stays_one_paragraph() -> None:
    assert _parse("Light bends in water.") == [{"kind": "paragraph", "text": "Light bends in water."}]


def test_lines_and_bullet_markers() -> None:
    text = "Intro line\n- first\n* second\n• third\r\n\n  - indented  \nOutro"
    assert _parse(text) == [
        {"kind": "paragraph", "text": "Intro line"},
        {"kind": "bullet", "text": "first"},
        {"kind": "bullet", "text": "second"},
        {"kind": "bullet", "text": "third"},
        {"kind": "bullet", "text": "indented"},
        {"kind": "paragraph", "text": "Outro"},
    ]


def test_a_hyphen_inside_a_line_is_not_a_bullet() -> None:
    assert _parse("well-known -fact") == [{"kind": "paragraph", "text": "well-known -fact"}]


def test_callout_box_renders_parsed_lines() -> None:
    source = (COMPOSER / "src" / "components" / "CalloutBox.tsx").read_text(encoding="utf-8")
    assert 'from "../lib/calloutText"' in source
    assert "parseCalloutText(text).map(" in source
    scene_types = (COMPOSER / "SCENE_TYPES.md").read_text(encoding="utf-8")
    assert "bullet" in scene_types.split("| `callout` |", 1)[1].split("\n", 1)[0]
