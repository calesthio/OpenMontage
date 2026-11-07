"""Tests for scripts/s5_blind_pack.py (S5-4). Synthetic images only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.s5_blind_pack import (  # noqa: E402
    MAX_WIDTH,
    build_sheet,
    panel_order,
    run,
)


def test_panel_order_is_a_permutation_and_reproducible():
    a = panel_order("s01")
    b = panel_order("s01")
    assert a == b, "same scene + salt must reproduce the same order"
    assert sorted(a) == sorted(["sdxl", "zimage", "klein"])


def test_panel_order_differs_across_scenes():
    orders = {tuple(panel_order(f"s{i:02d}")) for i in range(10)}
    assert len(orders) > 1, "orders must not be identical on every sheet"


def test_different_salt_changes_order():
    assert panel_order("s01", salt="a") != panel_order("s01", salt="b") or \
        panel_order("s03", salt="a") != panel_order("s03", salt="b")


def _img(path: Path, shade: int) -> Path:
    im = Image.new("RGB", (1024, 1024), (shade, shade, shade))
    ImageDraw.Draw(im).ellipse((300, 300, 700, 700), fill=(0, 0, 0))
    im.save(path)
    return path


def test_sheet_is_phone_sized_and_labelled(tmp_path):
    images = {
        "sdxl": _img(tmp_path / "a.png", 200),
        "zimage": _img(tmp_path / "b.png", 120),
        "klein": _img(tmp_path / "c.png", 60),
    }
    order = {"A": "klein", "B": "sdxl", "C": "zimage"}
    out = tmp_path / "sheet.png"
    w, h = build_sheet(images, order, out)
    assert w <= MAX_WIDTH and w <= 1600
    assert out.is_file()
    with Image.open(out) as im:
        assert im.size == (w, h)
        # the three panels must come from three different source shades
        px = [im.getpixel((int(w * f), int(h * 0.75)))[0] for f in (0.18, 0.5, 0.82)]
    assert len(set(px)) == 3


def test_run_writes_sheets_csv_instructions_and_mapping(tmp_path):
    root = tmp_path / "out"
    for model_idx, model in enumerate(("sdxl", "zimage", "klein")):
        d = root / f"s5_bakeoff_{model}" / "images"
        d.mkdir(parents=True)
        entries = []
        for i, scene in enumerate(["s01", "s03"]):
            # distinct, deterministic shade per (model, scene)
            p = _img(d / f"{model}_{scene}.png", 40 + model_idx * 60 + i * 15)
            entries.append({"render_id": f"{model}-{scene}", "file": p.name,
                            "scene_id": scene, "variant": "A"})
        (root / f"s5_bakeoff_{model}" / "manifest.json").write_text(json.dumps({
            "model": model,
            "load_seconds": 10.0,
            "steady_state_sec_per_image": 2.0,
            "peak_vram_mb": 7000,
            "black_count": 0, "nan_count": 0, "oom_count": 0,
            "images": entries,
        }), encoding="utf-8")

    out_dir = tmp_path / "blind"
    mapping = run(root, out_dir, salt="test")

    assert (out_dir / "sheet_s01.png").is_file()
    assert (out_dir / "sheet_s03.png").is_file()
    assert (out_dir / "INSTRUCTIONS.txt").read_text().lower().count("no") >= 1
    csv_text = (out_dir / "results.csv").read_text().strip().splitlines()
    assert csv_text[0].startswith("scene,best_panel,worst_panel")
    assert [ln.split(",")[0] for ln in csv_text[1:]] == ["s01", "s03"]

    saved = json.loads((out_dir / "mapping.json").read_text())
    assert set(saved["scenes"]) == {"s01", "s03"}
    for scene, order in saved["scenes"].items():
        assert sorted(order) == ["A", "B", "C"]
        assert sorted(order.values()) == ["klein", "sdxl", "zimage"]
    assert saved["model_metrics"]["sdxl"]["steady_state_sec_per_image"] == 2.0


def test_model_names_stay_out_of_sheet_filenames(tmp_path):
    root = tmp_path / "out"
    for model in ("sdxl", "zimage", "klein"):
        d = root / f"s5_bakeoff_{model}" / "images"
        d.mkdir(parents=True)
        p = _img(d / f"{model}.png", 100)
        (root / f"s5_bakeoff_{model}" / "manifest.json").write_text(json.dumps({
            "model": model, "images": [{"render_id": "r", "file": p.name,
                                        "scene_id": "s01", "variant": "B"}],
        }), encoding="utf-8")
    out_dir = tmp_path / "blind"
    run(root, out_dir, salt="t")
    names = " ".join(p.name for p in out_dir.glob("*.png"))
    for model in ("sdxl", "zimage", "klein"):
        assert model not in names.lower()
