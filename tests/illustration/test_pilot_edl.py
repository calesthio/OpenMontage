#!/usr/bin/env python3
"""Red/green tests for the illustration EDL builder (G6/G8).

The pilot is 84 AI stills + narration: every cut must carry the speculative
label, a description, the sentence's claim_ids, a sha256 of the source image,
and a motion move that never repeats back-to-back.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.illustration.pilot_edl import build_illustration_edl  # noqa: E402

LABEL = "Speculative illustration"


def _images(n=4):
    return [{"file": f"img_{i:03d}.png", "sha256": hashlib.sha256(str(i).encode()).hexdigest(),
             "scene_id": "filter_drifter" if i % 2 == 0 else "vent_grazer"}
            for i in range(n)]


def _sentences():
    return [
        {"sentence": "Beneath miles of ice there could be an ocean.", "claim_id": "SE-01"},
        {"sentence": "Europa hides a global saltwater sea under a frozen crust.", "claim_id": "SE-01, SE-04"},
        {"sentence": "A vent grazer grips the chimney with six limbs.", "claim_id": "SE-09"},
    ]


def test_every_image_becomes_one_cut(tmp_path):
    edl = build_illustration_edl(_images(4), _sentences(), total_duration=40.0,
                                 topic="t_ep", episode="se_pilot")
    assert len(edl["cuts"]) == 4
    assert edl["total_duration_s"] == 40.0


def test_cuts_carry_label_description_claim_and_hash():
    edl = build_illustration_edl(_images(4), _sentences(), total_duration=40.0,
                                 topic="t_ep", episode="se_pilot")
    for cut in edl["cuts"]:
        assert cut["label"] == LABEL
        assert cut["generator"] == "AI"
        assert cut["description"].strip()
        assert cut["claim_ids"].strip()
        assert len(cut["source_sha256"]) == 64
        assert cut["rights_basis"] == "ai_generated_illustration"
        assert cut["role"] == "illustration"
        assert cut["duration"] > 0


def test_durations_are_contiguous_and_exact():
    edl = build_illustration_edl(_images(4), _sentences(), total_duration=40.0,
                                 topic="t_ep", episode="se_pilot")
    cursor = 0.0
    for cut in edl["cuts"]:
        assert cut["start"] == round(cursor, 3)
        cursor += cut["duration"]
    assert abs(cursor - 40.0) < 1e-6
    assert edl["cuts"][-1]["end"] == 40.0


def test_no_two_identical_moves_in_a_row():
    edl = build_illustration_edl(_images(12), _sentences(), total_duration=120.0,
                                 topic="t_ep", episode="se_pilot")
    moves = [(c["move"], c["easing"], c["direction"]) for c in edl["cuts"]]
    for a, b in zip(moves, moves[1:]):
        assert a != b, moves


def test_motion_segments_mirror_cuts_for_the_lint():
    edl = build_illustration_edl(_images(4), _sentences(), total_duration=40.0,
                                 topic="t_ep", episode="se_pilot")
    assert len(edl["motion_segments"]) == len(edl["cuts"])
    for seg, cut in zip(edl["motion_segments"], edl["cuts"]):
        assert seg["move"] == cut["move"]


def test_claim_ids_come_from_the_sentences_not_invented():
    edl = build_illustration_edl(_images(3), _sentences(), total_duration=30.0,
                                 topic="t_ep", episode="se_pilot")
    allowed = {"SE-01", "SE-04", "SE-09"}
    for cut in edl["cuts"]:
        ids = {p.strip() for p in cut["claim_ids"].split(",")}
        assert ids and ids <= allowed, cut["claim_ids"]


def test_writes_edl_file(tmp_path):
    out = tmp_path / "edit_decisions.json"
    edl = build_illustration_edl(_images(2), _sentences(), total_duration=20.0,
                                 topic="t_ep", episode="se_pilot", out_path=out)
    assert out.is_file()
    assert json.loads(out.read_text())["cuts"] == edl["cuts"]


def test_rejects_empty_inputs():
    try:
        build_illustration_edl([], _sentences(), total_duration=10.0,
                               topic="t", episode="e")
    except ValueError:
        pass
    else:
        raise AssertionError("empty images must raise")
    try:
        build_illustration_edl(_images(1), [], total_duration=10.0,
                               topic="t", episode="e")
    except ValueError:
        pass
    else:
        raise AssertionError("empty sentences must raise")


def test_many_images_per_sentence_keeps_positive_durations():
    """84 images over 46 sentences (the pilot ratio) must not overshoot.

    The last cut of a multi-image sentence advances the cursor by the whole
    sentence duration on top of the images already placed, which made the
    final cut negative and the render BLOCKED.
    """
    rows = [{"sentence": f"sentence number {i} with some words", "claim_id": "SE-01"}
            for i in range(5)]
    edl = build_illustration_edl(_images(12), rows, total_duration=30.0,
                                 topic="t_ep", episode="se_pilot")
    assert all(c["duration"] > 0 for c in edl["cuts"]), edl["cuts"]
    assert edl["cuts"][-1]["end"] == 30.0
    starts = [c["start"] for c in edl["cuts"]]
    ends = [c["end"] for c in edl["cuts"]]
    assert starts[0] == 0.0
    assert all(abs(a - b) < 1e-6 for a, b in zip(ends, starts[1:]))
    assert sum(c["duration"] for c in edl["cuts"]) == 30.0
