#!/usr/bin/env python3
"""Red-then-green tests for tools/illustration/illustration_qc.py.

Auto QC for AI-generated illustrations: blur via Laplacian variance,
perceptual-hash duplicates, aspect/size checks, text-like artifact flagging.
No network, no paid routes, no AI upscaling. Pillow only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.illustration.illustration_qc import (  # noqa: E402
    laplacian_variance,
    average_hash,
    hamming_distance,
    check_aspect_size,
    flag_text_like,
    qc_image,
)

TMP = Path("/tmp/kilo_illustration_qc")
TMP.mkdir(parents=True, exist_ok=True)


def _make(path, w, h, pattern="shapes"):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (w, h), (20, 30, 40))
    d = ImageDraw.Draw(img)
    if pattern == "shapes":
        # sharp-edged geometric blocks -> high Laplacian variance
        d.rectangle([0, 0, w // 2, h // 2], fill=(240, 240, 240))
        d.rectangle([w // 2, 0, w, h // 2], fill=(60, 60, 60))
        d.rectangle([0, h // 2, w // 2, h], fill=(60, 60, 60))
        d.rectangle([w // 2, h // 2, w, h], fill=(240, 240, 240))
        d.line([0, 0, w, h], fill=(255, 255, 255), width=4)
        d.line([0, h, w, 0], fill=(255, 255, 255), width=4)
    elif pattern == "blur":
        img = img.resize((w // 4, h // 4)).resize((w, h))
    elif pattern == "textzone":
        # two thin full-width white bands (text-chip-like) in top/bottom thirds
        d.rectangle([0, int(h * 0.12), w, int(h * 0.12) + 3], fill=(255, 255, 255))
        d.rectangle([0, int(h * 0.82), w, int(h * 0.82) + 3], fill=(255, 255, 255))
    img.save(path)


def test_laplacian_variance_blur_detected():
    sharp = TMP / "sharp.png"
    blurry = TMP / "blurry.png"
    _make(sharp, 200, 200, "shapes")
    _make(blurry, 200, 200, "blur")
    assert laplacian_variance(sharp) > laplacian_variance(blurry)
    assert laplacian_variance(sharp) >= 100  # sharp shapes exceed threshold
    assert laplacian_variance(blurry) < 100  # blur threshold


def test_average_hash_deterministic_and_similar():
    a = TMP / "a.png"; b = TMP / "b.png"
    _make(a, 200, 200); _make(b, 200, 200)
    ha, hb = average_hash(a), average_hash(b)
    assert ha == hb
    assert hamming_distance(ha, hb) == 0


def test_hamming_distance_detects_near_dup():
    a = TMP / "a.png"; b = TMP / "b.png"
    _make(a, 200, 200); _make(b, 200, 200)
    ha = average_hash(a)
    # flip a 20x20 block -> hash changes slightly (near-duplicate)
    from PIL import Image
    img = Image.open(b).convert("RGB")
    px = img.load()
    for dy in range(20):
        for dx in range(20):
            v = px[10 + dx, 10 + dy]
            px[10 + dx, 10 + dy] = (0, 0, 0)
    img.save(b)
    hb2 = average_hash(b)
    d = hamming_distance(ha, hb2)
    assert 0 < d <= 8  # near-duplicate range


def test_check_aspect_size_within_tolerance():
    ok = TMP / "ok.png"; bad = TMP / "bad.png"
    _make(ok, 1280, 720)
    _make(bad, 1280, 640)
    assert check_aspect_size(ok, 1280, 720) is True
    assert check_aspect_size(bad, 1280, 720) is False


def test_flag_text_like():
    texty = TMP / "texty.png"; clean = TMP / "clean.png"
    _make(texty, 1280, 720, "textzone")
    _make(clean, 1280, 720, "gradient")
    assert flag_text_like(texty) is True
    assert flag_text_like(clean) is False


def test_qc_image_pass_and_fail():
    good = TMP / "good.png"; _make(good, 1280, 720)
    rep = qc_image(good, 1280, 720)
    assert rep["passed"] is True
    assert rep["blur_ok"] is True
    assert rep["aspect_ok"] is True
    assert rep["text_like"] is False

    blurry = TMP / "blurry.png"; _make(blurry, 1280, 720, "blur")
    rep2 = qc_image(blurry, 1280, 720)
    assert rep2["passed"] is False
    assert rep2["blur_ok"] is False
