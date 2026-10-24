#!/usr/bin/env python3
"""Red-then-green tests for tools/motion/motion_variety.py (M5).

No network, no paid routes. ffmpeg filter strings only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.motion.motion_variety import (  # noqa: E402
    ease_curve,
    build_pan_zoom,
    build_detail_crop,
    build_parallax,
    build_chapter_card,
    lint_variation,
)

TMP = Path("/tmp/kilo_motion")
TMP.mkdir(parents=True, exist_ok=True)


def test_ease_curve_monotonic_and_bounded():
    for name in ("linear", "easein", "easeout", "easeinout"):
        f = ease_curve(name)
        assert f(0.0) == 0.0
        assert f(1.0) == 1.0
        prev = -1.0
        for i in range(101):
            v = f(i / 100)
            assert 0.0 <= v <= 1.0
            assert v >= prev - 1e-9
            prev = v


def test_build_pan_zoom_produces_filter():
    filt = build_pan_zoom(5.0, easing="easeinout", direction="in", start_scale=1.0, end_scale=1.2)
    assert "zoompan" in filt
    assert "z=" in filt or "zoom" in filt


def test_build_pan_zoom_different_easing_different_filter():
    a = build_pan_zoom(5.0, easing="easein", direction="in")
    b = build_pan_zoom(5.0, easing="easeout", direction="in")
    assert a != b


def test_build_detail_crop():
    filt = build_detail_crop(4.0, crop_box=(0.25, 0.25, 0.75, 0.75))
    assert "crop" in filt


def test_build_parallax():
    filt = build_parallax(6.0, layers=2, drift=0.04)
    assert filt is not None and len(filt) > 0


def test_build_chapter_card():
    card = build_chapter_card("Chapter 1", "Orbit", 5.0)
    assert card["title"] == "Chapter 1"
    assert card["subtitle"] == "Orbit"
    assert card["duration"] == 5.0
    assert card["kind"] == "chapter_card"


def test_lint_variation_no_consecutive_identical():
    segments = [
        {"move": "pan_zoom", "easing": "easein", "direction": "in"},
        {"move": "pan_zoom", "easing": "easeout", "direction": "out"},
        {"move": "detail_crop"},
    ]
    assert lint_variation(segments) == []


def test_lint_variation_flags_consecutive_identical():
    segments = [
        {"move": "pan_zoom", "easing": "easein", "direction": "in"},
        {"move": "pan_zoom", "easing": "easein", "direction": "in"},
        {"move": "detail_crop"},
    ]
    problems = lint_variation(segments)
    assert len(problems) == 1
    assert "consecutive" in problems[0]["reason"].lower() or "identical" in problems[0]["reason"].lower()
