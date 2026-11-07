#!/usr/bin/env python3
"""Tests for scripts/s7_review_write.py (S7-9 rubric sheet upsert)."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "s7_review_write.py"

HEADER = ["render_id", "scene_id", "model", "anatomy", "geometry",
          "count_relation", "texture", "text", "usefulness", "notes"]


def _sheet(tmp_path: Path) -> Path:
    p = tmp_path / "review.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerow(["r0001", "s01", "sdxl", "", "", "", "", "", "", ""])
        w.writerow(["r0002", "s01", "klein", "", "", "", "", "", "", ""])
    return p


def _rows(p: Path):
    with p.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_upsert_writes_scores_and_keeps_other_rows(tmp_path):
    p = _sheet(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--csv", str(p), "--render-id", "r0001",
         "--anatomy", "0", "--geometry", "1", "--count-relation", "0",
         "--texture", "2", "--text", "0", "--usefulness", "0",
         "--notes", "garbled text"],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rows = _rows(p)
    assert rows[0]["anatomy"] == "0"
    assert rows[0]["texture"] == "2"
    assert rows[0]["notes"] == "garbled text"
    assert rows[1]["render_id"] == "r0002"
    assert rows[1]["anatomy"] == ""


def test_partial_update_leaves_other_dimensions(tmp_path):
    p = _sheet(tmp_path)
    subprocess.run(
        [sys.executable, str(SCRIPT), "--csv", str(p), "--render-id", "r0002",
         "--anatomy", "1"],
        capture_output=True, text=True, check=True)
    rows = _rows(p)
    assert rows[1]["anatomy"] == "1"
    assert rows[1]["geometry"] == ""


def test_unknown_render_id_is_blocked(tmp_path):
    p = _sheet(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--csv", str(p), "--render-id", "r9999",
         "--anatomy", "1"],
        capture_output=True, text=True)
    assert r.returncode != 0
    assert "BLOCKED" in (r.stdout + r.stderr)


def test_out_of_range_score_is_rejected(tmp_path):
    p = _sheet(tmp_path)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--csv", str(p), "--render-id", "r0001",
         "--anatomy", "5"],
        capture_output=True, text=True)
    assert r.returncode != 0


def test_missing_sheet_is_blocked(tmp_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--csv", str(tmp_path / "nope.csv"),
         "--render-id", "r0001", "--anatomy", "1"],
        capture_output=True, text=True)
    assert r.returncode != 0
    assert "BLOCKED" in (r.stdout + r.stderr)
