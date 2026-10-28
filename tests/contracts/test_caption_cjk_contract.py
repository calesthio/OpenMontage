"""CJK captions must lose the inter-word space in every composition.

PR #507 gave `CaptionOverlay` a `wordSeparator` prop, but it defaulted to
`" "` and only `TalkingHead` forwarded it. `Explainer` and `CinematicRenderer`
never passed it, so captions there kept a space between every token — the
defect #507 set out to fix, still live on the two main composition paths.

The separator is now decided per adjacent pair when the prop is unset, so a
script boundary keeps its space ("使用 OpenMontage 製作的影片") while two CJK
tokens are glued. An explicit `wordSeparator` still overrides.

There is no JS test runner in this repo, so the wiring is asserted against the
source the way test_remotion_video_transition_contract.py does. The character
ranges are extracted and exercised for real, since a range table is exactly
the kind of thing that looks right and is not.
"""

import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

COMPOSER = PROJECT_ROOT / "remotion-composer" / "src"
CAPTION_OVERLAY = COMPOSER / "components" / "CaptionOverlay.tsx"

# Matches both \uXXXX and the \u{XXXXX} form the /u flag allows.
_RANGE = re.compile(r"\\u\{?([0-9A-Fa-f]{4,6})\}?-\\u\{?([0-9A-Fa-f]{4,6})\}?")


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _cjk_ranges() -> list[tuple[int, int]]:
    """Parse the ranges out of the TSX, tolerating their absence.

    Raising at import time would turn every assertion below into one
    collection error, which hides which behaviour actually broke.
    """
    source = _source(CAPTION_OVERLAY)
    start = source.find("const CJK_CHARACTER")
    if start == -1:
        return []
    literal = source[start : source.index(";", start)]
    return [(int(low, 16), int(high, 16)) for low, high in _RANGE.findall(literal)]


RANGES = _cjk_ranges()


def test_the_range_table_exists() -> None:
    """Without this, the parametrized range tests would pass vacuously."""
    assert RANGES, "CaptionOverlay declares no CJK character ranges"


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return any(low <= code <= high for low, high in RANGES)


# --- the range table, exercised ---------------------------------------------


@pytest.mark.parametrize(
    "char",
    [
        "阿",  # CJK Unified Ideographs
        "聽",
        "\u3400",  # Extension A
        "\U00020000",  # Extension B — rarer Traditional forms live here
        "の",  # Hiragana
        "ス",  # Katakana
        "한",  # Hangul
        "。",  # CJK punctuation, must stay glued to the preceding word
        "、",
        "？",  # Fullwidth forms
        "）",
    ],
)
def test_character_is_recognised_as_cjk(char: str) -> None:
    assert _is_cjk(char), f"{char!r} (U+{ord(char):04X}) should count as CJK"


@pytest.mark.parametrize("char", ["a", "Z", "0", " ", ".", "?", "é", "—"])
def test_latin_character_is_not_cjk(char: str) -> None:
    assert not _is_cjk(char), f"{char!r} must not count as CJK"


def test_range_table_reaches_past_the_basic_plane() -> None:
    """A table stopping at U+9FFF drops the rarer Traditional forms."""
    assert max(high for _, high in RANGES) > 0xFFFF


# --- wiring ------------------------------------------------------------------


def test_word_separator_no_longer_defaults_to_a_space() -> None:
    """The default was what made every non-TalkingHead composition wrong."""
    source = _source(CAPTION_OVERLAY)
    assert 'wordSeparator = " "' not in source
    assert "wordSeparator?: string;" in source


def test_separator_is_decided_per_pair_when_the_prop_is_unset() -> None:
    source = _source(CAPTION_OVERLAY)
    assert "wordSeparator ?? separatorBetween(w.word, next.word)" in source


def test_rendered_separator_is_the_per_pair_one() -> None:
    """The fixed ``wordSeparator`` expression must not survive next to it (#613
    moved the separator outside the word span; it must still be ``separator``)."""
    source = _source(CAPTION_OVERLAY)
    assert "{separator}" in source
    assert '? wordSeparator : ""' not in source


@pytest.mark.parametrize("composition", ["Explainer.tsx", "CinematicRenderer.tsx"])
def test_composition_gets_cjk_captions_without_opting_in(composition: str) -> None:
    """These two never passed wordSeparator; the fix must not require them to.

    If a composition starts pinning the separator, this test should be updated
    deliberately rather than the behaviour regressing silently.
    """
    source = _source(COMPOSER / composition)
    call_start = source.index("<CaptionOverlay")
    call = source[call_start : source.index("/>", call_start)]
    assert "wordSeparator" not in call
