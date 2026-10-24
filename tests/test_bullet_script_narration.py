#!/usr/bin/env python3
"""Red/green tests for bullet-style script parsing and the Kokoro torch helper.

The pilot script (docs/openmontage/slice/speculative_evolution/SCRIPT_v0.md)
is bullet-style with trailing `[SE-xx]` claim ids, not a `| B1 | ... |` table.
Both the pipeline parser and the narration helper must handle it, and the
spoken text must never include the bracketed claim ids.

No model download: only the pure parsing functions are exercised here.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_episode  # noqa: E402
import kokoro_torch_narrate as ktn  # noqa: E402

PILOT = ROOT / "docs/openmontage/slice/speculative_evolution/SCRIPT_v0.md"


def test_bullet_script_parses_all_sentences():
    rows = run_episode._parse_script_rows(PILOT)
    assert len(rows) == 46, len(rows)
    assert rows[0]["claim_ids"] == "SE-01"
    assert rows[-1]["claim_ids"] == "SE-01, SE-03"
    assert all(r["sentence"].strip() for r in rows)
    # claim markers never leak into the sentence
    assert not any("[" in r["sentence"] for r in rows)


def test_bullet_beats_follow_chapter_headings():
    rows = run_episode._parse_script_rows(PILOT)
    beats = [r["beat"] for r in rows]
    assert beats[0] == "B0"          # hook
    assert beats == sorted(beats, key=lambda b: int(b[1:]))
    assert int(beats[-1][1:]) == 9   # nine chapters after the hook


def test_table_script_still_parses(tmp_path):
    p = tmp_path / "script.md"
    p.write_text(
        "| beat | sentence | claim_ids |\n"
        "|---|---|---|\n"
        "| B1 | One fact. | C-01 |\n"
        "| B1-2 | Another fact. | C-02 |\n",
        encoding="utf-8")
    rows = run_episode._parse_script_rows(p)
    assert [r["beat"] for r in rows] == ["B1", "B1"]
    assert rows[1]["claim_ids"] == "C-02"


def test_narration_helper_strips_claim_markers():
    assert ktn.strip_claim_ids("Ocean under ice. [SE-01, SE-04]") == "Ocean under ice."
    assert ktn.strip_claim_ids("No marker here.") == "No marker here."


def test_narration_helper_parses_bullets_and_tables(tmp_path):
    p = tmp_path / "s.md"
    p.write_text(
        "## Hook\n\n- First line. [SE-01]\n- Second line. [SE-02]\n\n"
        "## Chapter 1\n\n- Third line. [SE-03]\n",
        encoding="utf-8")
    assert ktn.parse_script(p) == ["First line.", "Second line.", "Third line."]

    t = tmp_path / "t.md"
    t.write_text("| B1 | Table line. | C-01 |\n", encoding="utf-8")
    assert ktn.parse_script(t) == ["Table line."]


def test_narration_helper_refuses_missing_script(tmp_path):
    try:
        ktn.parse_script(tmp_path / "nope.md")
    except FileNotFoundError:
        return
    raise AssertionError("missing script must raise")
