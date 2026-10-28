#!/usr/bin/env python3
"""TDD tests for tools/illustration/s1_contact_sheet.py (S1-5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PIL import Image  # noqa: E402

from tools.illustration.s1_contact_sheet import (  # noqa: E402
    build_contact_sheet,
    write_mapping,
)

REPO = Path(__file__).resolve().parent.parent.parent


def _make_images(tmp, names):
    paths = []
    for i, name in enumerate(names):
        p = tmp / name
        Image.new("RGB", (1280, 720), color=(i * 40, i * 20, 100)).save(p, "PNG")
        paths.append(p)
    return paths


def test_contact_sheet_builds_12_frames(tmp_path):
    images = _make_images(tmp_path, [f"img_{i:03d}.png" for i in range(12)])
    out = tmp_path / "contact.png"
    res = build_contact_sheet(images, out, cols=4, rows=3)
    assert out.exists() and out.stat().st_size > 0
    assert res["cols"] == 4 and res["rows"] == 3
    assert len(res["frames"]) == 12
    for i, fr in enumerate(res["frames"]):
        assert fr["sheet_name"] == f"sheet_{i+1:02d}"
        assert fr["source"] == f"img_{i:03d}.png"
        assert fr["sha256"] and fr["bytes"] > 0


def test_contact_sheet_trims_to_grid(tmp_path):
    images = _make_images(tmp_path, [f"img_{i:03d}.png" for i in range(15)])
    out = tmp_path / "contact.png"
    res = build_contact_sheet(images, out, cols=4, rows=3)
    assert len(res["frames"]) == 12  # 4x3 = 12 max


def test_write_mapping_separate_file(tmp_path):
    images = _make_images(tmp_path, [f"img_{i:03d}.png" for i in range(3)])
    out = tmp_path / "contact.png"
    res = build_contact_sheet(images, out, cols=3, rows=1)
    mapping = tmp_path / "mapping.json"
    write_mapping(res["frames"], mapping)
    data = json.loads(mapping.read_text())
    assert data["sheet_01"]["source"] == "img_000.png"
    assert data["sheet_02"]["source"] == "img_001.png"
    assert data["sheet_03"]["source"] == "img_002.png"
    # mapping must not be embedded in the sheet image itself
    assert "mapping" not in res
