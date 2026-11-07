#!/usr/bin/env python3
"""Red/green tests for the improved text-like detector (P4).

The old heuristic (thin near-white bands in the top/bottom thirds) both
MISSED lettering (dark-on-light text, text in the middle) and OVER-FIRED on
flat art (a wide light band across a flat illustration).

These tests build a synthetic fixture set (Pillow only) and measure precision
and recall honestly:

  * text fixtures  (7) - the detector must flag them,
  * clean fixtures (7) - the detector must not flag them,
  * ambiguous     (2) - glyph-like marks that are not lettering; reported
    separately, never counted as a correct detection.

The fixture images are generated at test time (no media in the repo).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from make_qc_fixtures import build  # noqa: E402

from tools.illustration.text_detect import detect_text_like  # noqa: E402


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    out = tmp_path_factory.mktemp("qc_fixtures")
    manifest = build(out)
    return manifest, out


def _measure(manifest, out):
    tp = fp = tn = fn = 0
    ambiguous = []
    for item in manifest["fixtures"]:
        path = out / item["file"]
        flagged = detect_text_like(path)["text_like"]
        if item["label"] is None:
            ambiguous.append((item["name"], flagged))
            continue
        if item["label"] == 1 and flagged:
            tp += 1
        elif item["label"] == 1 and not flagged:
            fn += 1
        elif item["label"] == 0 and flagged:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": precision,
            "recall": recall, "f1": f1, "ambiguous": ambiguous}


def test_the_fixture_set_covers_text_clean_and_ambiguous(fixtures):
    manifest, _ = fixtures
    categories = {f["category"] for f in manifest["fixtures"]}
    assert categories == {"text", "clean", "ambiguous"}
    assert len(manifest["fixtures"]) >= 14


def test_the_detector_flags_lettering(fixtures):
    manifest, out = fixtures
    missed = [f["name"] for f in manifest["fixtures"]
              if f["label"] == 1
              and not detect_text_like(out / f["file"])["text_like"]]
    assert not missed, f"lettering was not detected in: {missed}"


def test_the_detector_does_not_fire_on_flat_art(fixtures):
    manifest, out = fixtures
    false_positives = [f["name"] for f in manifest["fixtures"]
                       if f["label"] == 0
                       and detect_text_like(out / f["file"])["text_like"]]
    assert not false_positives, \
        f"flat art was flagged as text-like: {false_positives}"


def test_precision_and_recall_meet_the_documented_floor(fixtures):
    manifest, out = fixtures
    scores = _measure(manifest, out)
    assert scores["precision"] >= 0.95, scores
    assert scores["recall"] >= 0.95, scores


def test_the_ambiguous_fixtures_are_reported_separately(fixtures):
    """Glyph-like marks are neither a hit nor a miss - they are reported."""
    manifest, out = fixtures
    scores = _measure(manifest, out)
    names = [n for n, _ in scores["ambiguous"]]
    assert set(names) == {"dashes", "barcode"}
    assert scores["tp"] + scores["fp"] + scores["tn"] + scores["fn"] == \
        len(manifest["fixtures"]) - len(scores["ambiguous"])


def test_the_detector_returns_evidence(fixtures):
    manifest, out = fixtures
    result = detect_text_like(out / "text_dark_on_light.png")
    assert result["text_like"] is True
    assert result["lines"] >= 1
    assert result["characters"] >= 3
    assert result["method"] == "connected_components"


def test_the_detector_reports_a_missing_file(fixtures):
    with pytest.raises(FileNotFoundError):
        detect_text_like(Path("/tmp/kilo/does-not-exist.png"))
