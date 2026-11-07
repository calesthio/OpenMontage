#!/usr/bin/env python3
"""Red/green tests for the S1 speculative-illustration gate (S1-3).

stdlib only. Red cases must fail the gate; green cases must pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.illustration.s1_speculative_gate import (  # noqa: E402
    check_motion_variety,
    check_speculative_label,
)

LABEL = "Speculative illustration"


def _cut(ai=True, label=None, description="A speculative illustration.", duration=5.0):
    return {
        "id": "c1",
        "generator": "AI" if ai else "footage",
        "label": label if label is not None else LABEL,
        "description": description,
        "duration": duration,
    }


def test_green_speculative_label_passes():
    """AI cut with Speculative illustration label + description -> OK."""
    res = check_speculative_label([_cut()], duration=10.0)
    assert res["ok"] is True, res
    assert res["ai_total"] == 1
    assert res["ai_labeled"] == 1


def test_red_speculative_label_missing_label():
    """AI cut without the Speculative illustration label -> problem."""
    res = check_speculative_label([_cut(label="Illustration")], duration=10.0)
    assert res["ok"] is False, res
    assert res["ai_labeled"] == 0
    assert len(res["problems"]) == 1
    assert LABEL in res["problems"][0]["reason"]


def test_red_speculative_label_missing_description():
    """AI cut with label but empty description -> problem."""
    res = check_speculative_label([_cut(description="")], duration=10.0)
    assert res["ok"] is False, res
    assert len(res["problems"]) == 1


def test_red_speculative_label_footage_not_required():
    """Non-AI cut is not subject to the Speculative illustration label."""
    res = check_speculative_label([_cut(ai=False)], duration=10.0)
    assert res["ok"] is True, res
    assert res["ai_total"] == 0


def test_green_motion_varied_passes():
    """Varied moves across segments -> OK."""
    segments = [
        {"move": "pan", "easing": "easein", "direction": "in"},
        {"move": "zoom", "easing": "easeout", "direction": "in"},
        {"move": "parallax", "easing": "easeinout", "direction": "out"},
    ]
    res = check_motion_variety(segments)
    assert res["ok"] is True, res
    assert res["problems"] == []


def test_red_motion_identical_consecutive():
    """Two identical consecutive moves -> problem."""
    segments = [
        {"move": "pan", "easing": "easein", "direction": "in"},
        {"move": "pan", "easing": "easein", "direction": "in"},
    ]
    res = check_motion_variety(segments)
    assert res["ok"] is False, res
    assert len(res["problems"]) == 1
    assert "consecutive identical move" in res["problems"][0]["reason"]
