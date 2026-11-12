"""Burned-in captions must keep right-to-left scripts in reading order.

CaptionOverlay renders each word as an inline-block <span>. The bidi algorithm
treats an inline-block as a neutral object, so with no base direction the
paragraph defaults to LTR and Arabic/Hebrew/Persian/Urdu words are placed left
to right: the sentence reads backwards even though each word is shaped
correctly. The page wrapper therefore has to carry an explicit direction,
detected from the words when the caller does not pass one.

Source-text assertions, same idiom as test_theme_text_contrast_contract.py.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPTION = REPO_ROOT / "remotion-composer" / "src" / "components" / "CaptionOverlay.tsx"


def _src() -> str:
    return CAPTION.read_text(encoding="utf-8")


def test_caption_overlay_accepts_direction_prop():
    assert re.search(r'direction\?:\s*"ltr"\s*\|\s*"rtl"\s*\|\s*"auto"', _src())


def test_caption_overlay_defaults_to_auto_detection():
    src = _src()
    assert 'direction = "auto"' in src
    assert "detectDirection(" in src
    assert "rtl > ltr" in src  # majority of words, not the first letter


def test_page_wrapper_sets_dir_and_css_direction():
    src = _src()
    assert "dir={direction}" in src
    assert re.search(r"style=\{\{\s*direction,", src)


def test_rtl_detection_covers_arabic_and_hebrew_blocks():
    src = _src()
    m = re.search(r"const RTL_CHAR = /\[(.+?)\]/", src)
    assert m, "RTL_CHAR regex missing"
    ranges = m.group(1)
    assert "\\u0590" in ranges  # Hebrew
    assert "\\u08FF" in ranges  # Arabic Extended-A
    assert "\\uFEFF" in ranges  # Arabic Presentation Forms-B
