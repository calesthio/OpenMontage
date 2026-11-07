"""Tests for scripts/s5_checks.py (S5-3). Synthetic images only — no media."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.s5_checks import (  # noqa: E402
    check_image,
    dhash,
    hamming,
    laplacian_variance,
    run,
    text_like_score,
)


def _save(tmp_path: Path, name: str, arr: np.ndarray) -> Path:
    p = tmp_path / name
    Image.fromarray(arr.astype(np.uint8), mode="L").save(p)
    return p


def test_laplacian_flags_blur_relative_to_sharp(tmp_path):
    rng = np.random.default_rng(0)
    sharp = (rng.integers(0, 2, (256, 256)) * 255).astype(np.uint8)
    blurred = np.asarray(
        Image.fromarray(sharp).filter(ImageFilter.GaussianBlur(6)))
    v_sharp = laplacian_variance(sharp.astype(np.float32))
    v_blur = laplacian_variance(blurred.astype(np.float32))
    assert v_sharp > v_blur * 5
    assert v_blur < 15.0


def test_text_like_score_flags_repetitive_glyph_bands(tmp_path):
    img = np.full((256, 256), 245, dtype=np.uint8)
    # simulate two lines of text: evenly spaced thin dark vertical strokes
    for row in (60, 180):
        for x in range(20, 236, 8):
            img[row:row + 20, x:x + 3] = 20
    flat = np.full((256, 256), 128, dtype=np.uint8)
    assert text_like_score(img.astype(np.float32)) > text_like_score(
        flat.astype(np.float32))


def test_dhash_identical_and_different(tmp_path):
    rng = np.random.default_rng(1)
    a = (rng.integers(0, 2, (256, 256)) * 255).astype(np.uint8)
    b = 255 - a
    pa = _save(tmp_path, "a.png", a)
    pb = _save(tmp_path, "b.png", a.copy())
    pc = _save(tmp_path, "c.png", b)
    assert hamming(dhash(pa), dhash(pb)) == 0
    assert hamming(dhash(pa), dhash(pc)) > 10


def test_check_image_flags_wrong_resolution(tmp_path):
    p = _save(tmp_path, "small.png", np.full((512, 512), 128, dtype=np.uint8))
    c = check_image(p)
    assert c["resolution_ok"] is False
    assert c["width"] == 512


def test_run_reports_duplicates_and_keeps_models_blind(tmp_path):
    root = tmp_path / "out"
    same = (np.indices((64, 64)).sum(axis=0) % 2 * 255).astype(np.uint8)
    for model in ("sdxl", "zimage"):
        d = root / f"s5_bakeoff_{model}"
        (d / "images").mkdir(parents=True)
        Image.fromarray(same).resize((1024, 1024), Image.NEAREST).save(
            d / "images" / "r0001.png")
        (d / "manifest.json").write_text(json.dumps({
            "model": model,
            "steady_state_sec_per_image": 1.5,
            "peak_vram_mb": 7000,
            "black_count": 0, "nan_count": 0, "oom_count": 0,
            "images": [{"render_id": "r0001", "file": "r0001.png",
                        "scene_id": "s01", "variant": "N"}],
        }), encoding="utf-8")
    out = tmp_path / "checks.json"
    report = run(root, out)
    assert out.is_file()
    assert set(report["per_model"]) == {"sdxl", "zimage"}
    assert report["duplicates"], "identical images must be flagged"
    assert all(r["resolution_ok"] for r in report["images"])
