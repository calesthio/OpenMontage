"""Per-letter title animation must split by grapheme, not by UTF-16 unit.

HeroTitle put every `title.split("")` piece in its own inline-block span. On
the 2026-11-11 audit render `make demo` drew "Build Momentum 🚀" as two U+FFFD
boxes, and a Thai title drew its vowels and tone marks on dotted circles.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSER_SRC = REPO_ROOT / "remotion-composer" / "src"
HELPER = COMPOSER_SRC / "lib" / "graphemes.ts"

CASES = {
    "ascii": "Render audit",
    "emoji": "Build Momentum 🚀",
    "thai": "ชาเขียว ที่ดีที่สุด",
    "zwj": "\U0001F469\u200d\U0001F469\u200d\U0001F467 ok",
}


def _node_with_type_stripping() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    match = re.match(r"v(\d+)\.(\d+)", version.strip())
    if not match or (int(match.group(1)), int(match.group(2))) < (22, 6):
        pytest.skip(f"node {version.strip()} cannot strip TypeScript types")
    return node


def _split_with_node(*, without_segmenter: bool) -> dict[str, list[str]]:
    node = _node_with_type_stripping()
    script = (
        ("Intl.Segmenter = undefined;\n" if without_segmenter else "")
        + f"const {{ splitGraphemes }} = await import({json.dumps(HELPER.as_uri())});\n"
        + f"const cases = {json.dumps(CASES, ensure_ascii=False)};\n"
        + "const out = {};\n"
        + "for (const [k, v] of Object.entries(cases)) out[k] = splitGraphemes(v);\n"
        + "console.log(JSON.stringify(out));\n"
    )
    proc = subprocess.run(
        [node, "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize("without_segmenter", [False, True], ids=["segmenter", "fallback"])
def test_split_graphemes_keeps_emoji_and_thai_marks_whole(without_segmenter: bool) -> None:
    parts = _split_with_node(without_segmenter=without_segmenter)

    for name, text in CASES.items():
        assert "".join(parts[name]) == text, name
    # ASCII is unchanged, so existing titles keep their stagger and accent.
    assert parts["ascii"] == list(CASES["ascii"])
    assert parts["emoji"][-1] == "🚀"
    assert parts["thai"][:5] == ["ช", "า", "เ", "ขี", "ย"]
    assert parts["thai"][7:9] == ["ที่", "ดี"]
    assert parts["zwj"][0] == "\U0001F469\u200d\U0001F469\u200d\U0001F467"
    for name, pieces in parts.items():
        for piece in pieces:
            assert not re.search(r"[\ud800-\udfff]", piece), (name, piece)
            assert not re.match(r"[ัิ-ฺ็-๎]", piece), (name, piece)


def test_hero_title_splits_by_grapheme() -> None:
    source = (COMPOSER_SRC / "components" / "HeroTitle.tsx").read_text(encoding="utf-8")
    assert 'from "../lib/graphemes"' in source
    assert 'split("")' not in source
    assert "splitGraphemes(title)" in source
    assert "splitGraphemes(word)" in source


# `split("")` is fine where the pieces are not text glyphs (hex colour expansion).
_NON_TEXT_SPLITS = {"Explainer.tsx": 'clean.split("").map(c => c + c)'}


def test_no_component_splits_display_text_by_utf16_unit() -> None:
    offenders = []
    for path in sorted(COMPOSER_SRC.rglob("*.tsx")):
        source = path.read_text(encoding="utf-8")
        allowed = _NON_TEXT_SPLITS.get(path.name)
        if allowed:
            source = source.replace(allowed, "")
        if 'split("")' in source:
            offenders.append(str(path.relative_to(COMPOSER_SRC)))
    assert not offenders, f"use splitGraphemes() instead of split(\"\"): {offenders}"


def test_hero_title_accents_the_whole_first_word() -> None:
    # The audit render coloured the first 8 characters, so "Your rainbow"
    # switched colour inside "rainbow". The accent follows the word index.
    source = (COMPOSER_SRC / "components" / "HeroTitle.tsx").read_text(encoding="utf-8")
    assert "i < 8" not in source
    assert "w === 0 ? accentColor : textColor" in source


def test_explainer_holds_the_last_cut_through_the_tail_padding() -> None:
    # Root.tsx adds `tailPaddingSeconds` (default 1) after the last cut; with
    # no cut covering it, every render ended on a second of bare background.
    source = (COMPOSER_SRC / "Explainer.tsx").read_text(encoding="utf-8")
    assert "lastOutSeconds" in source
    assert "durationInFrames - from" in source
