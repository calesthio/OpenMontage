"""Tests for lib.image_uniqueness (aHash near-duplicate detection)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/workspaces/OpenMontage")

from PIL import Image  # noqa: E402

from lib.image_uniqueness import (  # noqa: E402
    DUPLICATE_THRESHOLD,
    UniquenessReport,
    build_revision_prompt,
    check_uniqueness,
    compute_ahash,
)


def _make_pattern(path, pattern):
    """Render a 64x64 grayscale image from pattern(x, y) -> 0..255."""
    img = Image.new("L", (64, 64))
    px = img.load()
    for x in range(64):
        for y in range(64):
            px[x, y] = pattern(x, y)
    img.save(path)
    return str(path)


def _left_white(x, y):
    return 255 if x < 32 else 0


def _right_white(x, y):
    return 0 if x < 32 else 255


def _top_white(x, y):
    return 255 if y < 32 else 0


def _checker(x, y):
    return 255 if (x // 8 + y // 8) % 2 == 0 else 0


def _uniform(x, y):
    return 128


def test_ahash_is_deterministic(tmp_path):
    p1 = _make_pattern(tmp_path / "a.png", _checker)
    p2 = _make_pattern(tmp_path / "b.png", _checker)
    assert compute_ahash(p1) == compute_ahash(p2)


def test_distinct_patterns_have_different_hashes(tmp_path):
    p1 = _make_pattern(tmp_path / "a.png", _left_white)
    p2 = _make_pattern(tmp_path / "b.png", _right_white)
    assert compute_ahash(p1) != compute_ahash(p2)


def test_all_unique_images(tmp_path):
    patterns = [_left_white, _right_white, _top_white, _checker, _uniform]
    paths = [_make_pattern(tmp_path / f"u{i}.png", p) for i, p in enumerate(patterns)]
    report = check_uniqueness(paths)
    assert report.total == 5
    assert report.unique == 5
    assert report.duplicates == 0
    assert report.duplicate_rate == 0.0


def test_duplicate_detected(tmp_path):
    base = _make_pattern(tmp_path / "base.png", _checker)
    copy = _make_pattern(tmp_path / "copy.png", _checker)
    report = check_uniqueness([base, copy])
    assert report.total == 2
    assert report.unique == 1
    assert report.duplicates == 1
    assert report.duplicate_groups == [[base, copy]]


def test_threshold_controls_sensitivity(tmp_path):
    base = _make_pattern(tmp_path / "base.png", _checker)
    report = check_uniqueness([base, base], threshold=0)
    assert report.duplicates == 1


def test_unreadable_image_recorded_as_issue(tmp_path):
    missing = str(tmp_path / "does_not_exist.png")
    report = check_uniqueness([missing])
    assert report.total == 1
    assert report.unique == 0
    assert any("does_not_exist" in i for i in report.issues)


def test_build_revision_prompt():
    rev = build_revision_prompt("A cat on a mat.", "base.png")
    assert rev.startswith("A cat on a mat")
    assert "unique composition" in rev
    rev2 = build_revision_prompt("A cat on a mat", "base.png")
    assert rev2.endswith(".")


def test_report_fields():
    r = UniquenessReport(total=4, unique=3, duplicates=1)
    assert r.duplicate_rate == 0.25
    r2 = UniquenessReport()
    assert r2.duplicate_rate == 0.0
