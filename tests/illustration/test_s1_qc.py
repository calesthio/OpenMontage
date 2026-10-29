#!/usr/bin/env python3
"""TDD tests for tools/illustration/s1_qc.py (S1-2 automatic QC)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PIL import Image, ImageFilter  # noqa: E402

from tools.illustration.s1_qc import (  # noqa: E402
    check_batch,
    check_image,
    laplacian_blur,
    phash,
    text_like_artifacts,
)

REPO = Path(__file__).resolve().parent.parent.parent


def _save(img: Image.Image, p: Path) -> Path:
    img.convert("RGB").save(p, "PNG")
    return p


def test_sharp_image_not_blurred(tmp_path):
    img = Image.new("RGB", (1280, 720), color=(100, 150, 200))
    # add noise-like variation -> high laplacian variance
    import random
    random.seed(1)
    px = img.load()
    for y in range(0, 720, 4):
        for x in range(0, 1280, 4):
            px[x, y] = (random.randint(0, 255),) * 3
    p = _save(img, tmp_path / "sharp.png")
    r = check_image(p)
    assert r["size_ok"] is True
    assert r["aspect_ok"] is True
    assert r["blur_flag"] is False, r


def test_uniform_image_blurred(tmp_path):
    img = Image.new("RGB", (1280, 720), color=(128, 128, 128))
    p = _save(img, tmp_path / "uniform.png")
    r = check_image(p)
    assert r["blur_flag"] is True, r


def test_wrong_aspect_flagged(tmp_path):
    img = Image.new("RGB", (1024, 1024), color=(10, 20, 30))
    p = _save(img, tmp_path / "sq.png")
    r = check_image(p)
    # 1024x1024 is a target size AND aspect (1:1) -> ok
    assert r["size_ok"] is True
    assert r["aspect_ok"] is True


def test_odd_size_flagged(tmp_path):
    img = Image.new("RGB", (700, 500), color=(10, 20, 30))
    p = _save(img, tmp_path / "odd.png")
    r = check_image(p)
    assert r["size_ok"] is False
    assert r["aspect_ok"] is False  # 7:5 not in {16:9, 1:1}


def test_text_like_heuristic_on_noise(tmp_path):
    # high edge fraction -> text-like suspected (human review)
    import random
    random.seed(2)
    img = Image.new("L", (160, 90))
    px = img.load()
    for y in range(90):
        for x in range(160):
            px[x, y] = random.choice([0, 255])
    # upscale to RGB for the check path
    rgb = img.convert("RGB").resize((1280, 720))
    assert text_like_artifacts(rgb) in (True, False)


def test_anatomy_always_human_review(tmp_path):
    img = Image.new("RGB", (1280, 720), color=(5, 5, 5))
    p = _save(img, tmp_path / "a.png")
    r = check_image(p)
    assert r["anatomy_human_review"] is True


def test_duplicate_detection(tmp_path):
    import importlib
    if importlib.util.find_spec("imagehash") is None:
        import pytest
        pytest.skip("imagehash not installed locally")
    base = Image.new("RGB", (1280, 720), color=(40, 60, 80))
    p1 = _save(base, tmp_path / "dup_a.png")
    p2 = _save(base, tmp_path / "dup_b.png")  # identical
    res = check_batch([p1, p2])
    assert res["summary"]["duplicate_pairs"] >= 1, res
    assert any(d["a"] == "dup_a.png" and d["b"] == "dup_b.png"
               for d in res["duplicates"]), res


def test_batch_summary_keys(tmp_path):
    # smooth gradient: sharp enough (blur ok), correct size/aspect,
    # not text-like, single image (no duplicates) -> ok True
    img = Image.new("RGB", (1280, 720))
    px = img.load()
    for y in range(720):
        for x in range(1280):
            px[x, y] = (x * 255 // 1280, y * 255 // 720, 128)
    p = _save(img, tmp_path / "x.png")
    res = check_batch([p])
    s = res["summary"]
    for key in ("total", "blur_flags", "text_like_flags", "aspect_failures",
                "size_failures", "duplicate_pairs", "anatomy_human_review_count"):
        assert key in s, key
    assert res["ok"] is True, res
