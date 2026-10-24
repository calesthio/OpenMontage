#!/usr/bin/env python3
"""TDD tests for tools/illustration/s1_edl.py (S1-5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.illustration.s1_edl import build_edl  # noqa: E402

SHOTS = [
    {
        "source": "img_000.png", "source_sha256": "a" * 64,
        "claim_ids": ["SE-01"], "rationale": "hook: frozen ocean hook",
        "duration": 5.0, "generator": "AI",
        "move": {"type": "pan", "easing": "easein", "direction": "in"},
    },
    {
        "source": "img_001.png", "source_sha256": "b" * 64,
        "claim_ids": ["SE-02"], "rationale": "Europa ocean scale",
        "duration": 6.0, "generator": "AI",
        "move": {"type": "zoom", "easing": "easeout", "direction": "in"},
    },
    {
        "source": "img_002.png", "source_sha256": "c" * 64,
        "claim_ids": ["SE-03"], "rationale": "tidal heating keeps water liquid",
        "duration": 5.0, "generator": "AI",
        "move": {"type": "parallax", "easing": "easeinout", "direction": "out"},
    },
]


def test_edl_builds_cuts_with_rationale(tmp_path):
    out = tmp_path / "edl.json"
    res = build_edl(SHOTS, out)
    assert out.exists() and out.stat().st_size > 0
    assert len(res["cuts"]) == 3
    assert abs(sum(c["duration"] for c in res["cuts"]) - 16.0) < 1e-6
    c = res["cuts"][0]
    assert c["cut_id"] == "cut_001"
    assert c["start"] == 0.0
    assert c["end"] == 5.0
    assert c["rationale"] == "hook: frozen ocean hook"
    assert c["claim_ids"] == ["SE-01"]
    assert c["label"] == "Speculative illustration"
    assert c["motion"]["type"] == "pan"


def test_edl_motion_variety_ok(tmp_path):
    out = tmp_path / "edl_ok.json"
    res = build_edl(SHOTS, out)
    assert res["ok"] is True, res
    assert res["motion_problems"] == [], res


def test_edl_flags_identical_consecutive_moves(tmp_path):
    shots = list(SHOTS)
    shots[1]["move"] = {"type": "pan", "easing": "easein", "direction": "in"}
    out = tmp_path / "edl_bad.json"
    res = build_edl(shots, out)
    assert res["ok"] is False, res
    assert len(res["motion_problems"]) == 1
    assert "consecutive identical move" in res["motion_problems"][0]["reason"]
