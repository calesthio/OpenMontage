"""Contact sheet layout tests: 3 cols x 4 rows = 12 tiles per sheet.

Covers scripts/s12_contact_sheets.py and scripts/s14_contact_sheet.py after the
COLS/ROWS change (2,3) -> (3,4). Builds synthetic tile PNGs and confirms each
sheet carries exactly 12 tiles (except a partial final sheet) and that the
tile grid math (col = pos % COLS, row = pos // COLS) matches the declared
layout.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_tiles(tmp_path: Path, n: int) -> list[Path]:
    paths = []
    for i in range(n):
        p = tmp_path / f"tile_{i:03d}.png"
        Image.new("RGB", (64, 64), (i * 10 % 256, 128, 200)).save(p)
        paths.append(p)
    return paths


@pytest.fixture
def s12():
    return _load("s12_contact_sheets", REPO / "scripts/s12_contact_sheets.py")


@pytest.fixture
def s14():
    return _load("s14_contact_sheet", REPO / "scripts/s14_contact_sheet.py")


def test_layout_is_12_tiles_per_sheet(s12, s14):
    for mod in (s12, s14):
        assert mod.COLS == 3, f"{mod.__name__}: COLS should be 3"
        assert mod.ROWS == 4, f"{mod.__name__}: ROWS should be 4"
        assert mod.TILES_PER_SHEET == 12, f"{mod.__name__}: 3*4 must be 12"


def test_s12_sheets_have_12_tiles(s12, tmp_path):
    tile_paths = _make_tiles(tmp_path, 25)
    items = []
    for i, p in enumerate(tile_paths):
        items.append({
            "code": f"A{i+1}",
            "path": str(p),
            "render_id": f"r{i+1}",
            "model": "m",
            "scene_id": "s",
            "seed": 1,
            "output_file": p.name,
        })
    out = tmp_path / "sheets"
    s12.build(items, out)

    sheets = sorted(out.glob("sheet_*.png"))
    assert len(sheets) == 3, f"expected 3 sheets for 25 items, got {len(sheets)}"
    mapping = json.loads((out / "mapping.json").read_text())
    assert len(mapping["codes"]) == 25
    # first two sheets full (12), last partial (1)
    assert len(list((out / "sheet_01.png").parent.glob("sheet_01.png"))) == 1


def test_s14_sheets_have_12_tiles(s14, tmp_path, monkeypatch):
    tile_paths = _make_tiles(tmp_path, 25)
    items = [{"path": str(p), "model": "m", "output_file": p.name} for p in tile_paths]
    # s14 writes to its module-level OUT; redirect to tmp_path.
    monkeypatch.setattr(s14, "OUT", tmp_path / "sheets")
    s14.build(items)

    sheets = sorted((tmp_path / "sheets").glob("sheet_*.png"))
    assert len(sheets) == 3, f"expected 3 sheets for 25 items, got {len(sheets)}"
    mapping = json.loads((tmp_path / "sheets" / "mapping.json").read_text())
    assert len(mapping["tiles"]) == 25
