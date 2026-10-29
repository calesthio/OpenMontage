#!/usr/bin/env python3
"""SCR-07: cmd_edl must be episode-generic, not Artemis-hardcoded.

Two fake episodes with different scripts and narration durations must yield
different, internally consistent edit decisions with no Artemis literals.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_episode  # noqa: E402


def _script(tmp_path, name, rows):
    """Write a script table: rows = [(beat, sentence, claim_ids), ...]."""
    lines = [
        "| Beat | Sentence | claim_ids | flags |",
        "|---|---|---|---|",
    ]
    for beat, sentence, claim_ids in rows:
        lines.append(f"| {beat} | {sentence} | {claim_ids} | |")
    path = tmp_path / name
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _run_edl(tmp_path, topic, script, duration_s, manifest=None):
    state = {
        "script_path": str(script),
        "narration_duration_s": duration_s,
        "edl_path": str(tmp_path / f"{topic}_edl.json"),
    }
    if manifest is not None:
        state["narration_manifest_path"] = str(manifest)
    return run_episode.cmd_edl(topic, state), Path(state["edl_path"])


def test_two_episodes_produce_different_edls(tmp_path):
    """Episode A (3 beats/6 sentences, 60 s) vs B (1 beat/2 sentences, 20 s)."""
    script_a = _script(tmp_path, "a.md", [
        ("B1", "First sentence of episode A.", "EP-A-01"),
        ("B1", "Second sentence of episode A.", "EP-A-01"),
        ("B2", "Third sentence of episode A.", "EP-A-02"),
        ("B2", "Fourth sentence of episode A.", "EP-A-02"),
        ("B3", "Fifth sentence of episode A.", "EP-A-03"),
        ("B3", "Sixth sentence of episode A.", "EP-A-03"),
    ])
    script_b = _script(tmp_path, "b.md", [
        ("B1", "First sentence of episode B.", "EP-B-01"),
        ("B1", "Second sentence of episode B.", "EP-B-01"),
    ])

    res_a, path_a = _run_edl(tmp_path, "ep_a", script_a, 60.0)
    res_b, path_b = _run_edl(tmp_path, "ep_b", script_b, 20.0)

    assert res_a["status"] == "OK", res_a
    assert res_b["status"] == "OK", res_b
    edl_a = json.loads(path_a.read_text())
    edl_b = json.loads(path_b.read_text())

    # Different episodes -> different total duration and different cut counts.
    assert edl_a["total_duration_s"] == 60.0
    assert edl_b["total_duration_s"] == 20.0
    assert len(edl_a["cuts"]) != len(edl_b["cuts"])
    assert edl_a["topic_id"] == "ep_a"
    assert edl_b["topic_id"] == "ep_b"

    # No Artemis literals or hardcoded duration may survive.
    text_a = path_a.read_text()
    for literal in ("ARTEMIS", "artemis", "185.43"):
        assert literal not in text_a, literal
    assert "185.43" not in path_b.read_text()

    # Cuts are contiguous and cover exactly the narration duration.
    for edl in (edl_a, edl_b):
        cuts = edl["cuts"]
        assert cuts[0]["start"] == 0.0
        for prev, cur in zip(cuts, cuts[1:]):
            assert cur["start"] == prev["end"], (prev, cur)
        assert cuts[-1]["end"] == edl["total_duration_s"]
        assert len({c["cut_id"] for c in cuts}) == len(cuts)

    # Every cut carries a written rationale; cards are declared static by design.
    for edl in (edl_a, edl_b):
        for cut in edl["cuts"]:
            assert cut["rationale"].strip(), cut
            assert cut["layout"] == "static_card"
            assert cut["role"] == "graphics_card"
        assert len(edl["static_segments"]) == len(edl["cuts"])
        assert all(s["static_by_design"] for s in edl["static_segments"])


def test_edl_carries_episode_claim_ids(tmp_path):
    """Claim ids come from the episode script, not from a hardcoded list."""
    script = _script(tmp_path, "c.md", [
        ("B1", "Sentence one.", "ZZ-01"),
        ("B2", "Sentence two.", "ZZ-02, ZZ-03"),
    ])
    res, path = _run_edl(tmp_path, "ep_c", script, 30.0)
    assert res["status"] == "OK", res
    edl = json.loads(path.read_text())
    blob = json.dumps(edl)
    assert "ZZ-01" in blob and "ZZ-02" in blob and "ZZ-03" in blob
    beat_cuts = [c for c in edl["cuts"] if c["role"] == "graphics_card"
                 and c["asset_id"].startswith("card_b")]
    assert len(beat_cuts) == 2, beat_cuts


def test_edl_uses_narration_manifest_duration(tmp_path):
    """The manifest's measured duration wins when state has no explicit value."""
    script = _script(tmp_path, "d.md", [("B1", "Only sentence.", "MM-01")])
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"expected_duration": 12.5}))
    state = {
        "script_path": str(script),
        "narration_manifest_path": str(manifest),
        "edl_path": str(tmp_path / "ep_d_edl.json"),
    }
    res = run_episode.cmd_edl("ep_d", state)
    assert res["status"] == "OK", res
    edl = json.loads(Path(state["edl_path"]).read_text())
    assert edl["total_duration_s"] == 12.5


def test_edl_blocks_without_script(tmp_path):
    res = run_episode.cmd_edl("ep_missing", {
        "narration_duration_s": 10.0,
        "edl_path": str(tmp_path / "x.json"),
    })
    assert res["status"] == "BLOCKED"
    assert "script" in res["error"].lower()


def test_edl_blocks_without_narration_duration(tmp_path):
    script = _script(tmp_path, "e.md", [("B1", "Sentence.", "NN-01")])
    res = run_episode.cmd_edl("ep_nodur", {
        "script_path": str(script),
        "edl_path": str(tmp_path / "y.json"),
    })
    assert res["status"] == "BLOCKED"
    assert "narration" in res["error"].lower()
