"""Tests for scripts/s7_blind_pack.py (S7-7).

Contract:
  * one sheet per scene with 3 panels A/B/C in a per-scene random order;
  * sheets are phone-readable (<= 1600 px wide) and carry NO model name;
  * the panel -> model mapping lives in a separate mapping.json;
  * the CSV template has the columns the owner fills in.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from PIL import Image  # noqa: E402

from scripts.s7_blind_pack import (  # noqa: E402
    CSV_HEADER,
    MAX_WIDTH,
    build_sheet,
    panel_order,
    run,
)

SCENES = ["s01", "s03", "s04", "s05", "s06", "s08", "s09", "s10", "s11", "s12"]


def _make_images(tmp_path: Path):
    """Fake model outputs: one 1024x1024 PNG per model, same for every scene."""
    from PIL import ImageDraw
    out = {}
    for i, model in enumerate(["sdxl", "klein", "zimage"]):
        p = tmp_path / f"{model}.png"
        im = Image.new("RGB", (1024, 1024), (10 * (i + 1), 200, 40))
        d = ImageDraw.Draw(im)
        d.text((40, 40), f"{model} sample", fill=(255, 255, 255))
        im.save(p)
        out[model] = p
    return out


def test_panel_order_is_random_per_scene_but_reproducible():
    a = panel_order("s01", "s7")
    assert panel_order("s01", "s7") == a, "same scene+salt must be stable"
    assert sorted(a) == ["klein", "sdxl", "zimage"]
    orders = {tuple(panel_order(s, "s7")) for s in SCENES}
    assert len(orders) > 1, "the order must differ between scenes"


def test_sheet_is_phone_readable_and_hides_model_names(tmp_path):
    images = _make_images(tmp_path)
    order = {label: model for label, model in zip("ABC", panel_order("s01", "s7"))}
    out = tmp_path / "sheet.png"
    w, h = build_sheet(images, order, out)
    assert w <= MAX_WIDTH
    with Image.open(out) as im:
        assert im.size == (w, h)


def test_pack_writes_sheets_mapping_and_csv_template(tmp_path):
    root = tmp_path / "out"
    for model in ("sdxl", "klein", "zimage"):
        d = root / f"s7_bakeoff_{model}"
        (d / "images").mkdir(parents=True)
        im = Image.new("RGB", (1024, 1024), (30, 30, 30))
        im.save(d / "images" / "r0001.png")
        (d / "manifest.json").write_text(json.dumps({
            "model": model, "job_id": f"s7-{model}-1", "images": [
                {"render_id": "r0001", "scene_id": "s01", "file": "r0001.png",
                 "sha256": "x", "bytes": 1},
            ],
            "steady_state_sec_per_image": 1.0, "peak_vram_mb": 100,
        }), encoding="utf-8")

    pack = tmp_path / "pack"
    mapping = run(root, pack, salt="s7")
    assert len(mapping["sheets"]) == 1
    sheet = pack / "sheet_s01.png"
    assert sheet.is_file()
    assert (pack / "mapping.json").is_file()
    with (pack / "results.csv").open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == list(CSV_HEADER.split(","))
    assert len(rows) == 2
    # the mapping must unblind the sheet, and the sheets must not name models
    doc = json.loads((pack / "mapping.json").read_text(encoding="utf-8"))
    assert sorted(doc["scenes"]["s01"].values()) == ["klein", "sdxl", "zimage"]
    assert "sdxl" not in sheet.read_bytes().decode("latin-1")


def test_two_model_pack_when_one_model_is_blocked(tmp_path):
    """A model with no frames must not appear as an empty/black panel."""
    root = tmp_path / "out"
    for model in ("sdxl", "klein"):
        d = root / f"s7_bakeoff_{model}"
        (d / "images").mkdir(parents=True)
        im = Image.new("RGB", (1024, 1024), (30, 30, 30))
        im.save(d / "images" / "r0001.png")
        (d / "manifest.json").write_text(json.dumps({
            "model": model, "job_id": f"s7-{model}-1", "images": [
                {"render_id": "r0001", "scene_id": "s01", "file": "r0001.png",
                 "sha256": "x", "bytes": 1},
            ],
        }), encoding="utf-8")

    pack = tmp_path / "pack"
    mapping = run(root, pack, salt="s7",
                  blocked_note="zimage: BLOCKED after 4 attempts, 0 usable images")
    assert mapping["pack_models"] == ["sdxl", "klein"]
    assert mapping["scenes"]["s01"].keys() == {"A", "B"}
    with (pack / "results.csv").open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["scene", "best_panel", "worst_panel",
                        "anatomy_ok_A", "anatomy_ok_B", "comment"]
    assert "zimage" in (pack / "INSTRUCTIONS.txt").read_text(encoding="utf-8")
