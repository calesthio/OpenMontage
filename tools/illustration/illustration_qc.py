#!/usr/bin/env python3
"""tools/illustration/illustration_qc.py — auto QC for AI-generated illustrations.

Blur via Laplacian variance, perceptual-hash (average-hash 8x8) duplicates,
aspect/size checks, text-like artifact flagging. Pillow only; no network, no
paid routes, no AI upscaling.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageOps

BLUR_VARIANCE_MIN = 100.0
PHASH_HAMMING_MAX = 8          # <= 8 => near-duplicate
ASPECT_TOLERANCE = 0.01        # 1%


def _load_gray(path: str | Path) -> Image.Image:
    return ImageOps.grayscale(Image.open(path).convert("RGB"))


def laplacian_variance(path: str | Path) -> float:
    """Laplacian variance of a grayscale image (blur measure). Higher = sharper."""
    img = _load_gray(path)
    w, h = img.size
    px = img.load()
    # 3x3 Laplacian kernel: center 4-neighbor sum - 4*center, over interior.
    values = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            c = px[x, y]
            lap = (
                px[x - 1, y] + px[x + 1, y] + px[x, y - 1] + px[x, y + 1] - 4 * c
            )
            values.append(lap)
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return float(var)


def average_hash(path: str | Path) -> int:
    """64-bit average-hash perceptual hash."""
    img = _load_gray(path).resize((8, 8)).convert("L")
    px = list(img.getdata())
    mean = sum(px) / len(px)
    h = 0
    for i, v in enumerate(px):
        if v > mean:
            h |= 1 << (63 - i)
    return h


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _dimensions(path: str | Path) -> Tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def check_aspect_size(path: str | Path, target_w: int, target_h: int) -> bool:
    """True if image is target_w x target_h within ASPECT_TOLERANCE."""
    w, h = _dimensions(path)
    if w <= 0 or h <= 0:
        return False
    target_ratio = target_w / target_h
    actual_ratio = w / h
    return abs(actual_ratio - target_ratio) / target_ratio <= ASPECT_TOLERANCE


def flag_text_like(path: str | Path) -> bool:
    """Heuristic: thin near-white horizontal bands (text/caption chips) in
    top/bottom thirds suggest text-like artifacts.

    Returns True when the image looks text-like (should be rejected/reviewed).
    A band = a thin (<= 8 px) run of > 90% near-white rows flanked by darker
    rows. One or more bands => text-like.
    """
    img = _load_gray(path).convert("L")
    w, h = img.size
    px = img.load()
    third = h // 3
    zones = [(0, third), (h - third, h)]
    band_count = 0
    for y0, y1 in zones:
        y = y0
        while y < y1:
            white = sum(1 for x in range(w) if px[x, y] > 240)
            if white / w > 0.9:
                # start of a white run; measure its height
                run_end = y
                while run_end < y1 and sum(1 for x in range(w) if px[x, run_end] > 240) / w > 0.9:
                    run_end += 1
                run_h = run_end - y
                # flanked by darker rows?
                above_dark = y == y0 or sum(1 for x in range(w) if px[x, y - 1] > 240) / w < 0.6
                below_dark = run_end >= y1 or sum(1 for x in range(w) if px[x, run_end] > 240) / w < 0.6
                if 1 <= run_h <= 8 and above_dark and below_dark:
                    band_count += 1
                y = run_end
            else:
                y += 1
    return band_count >= 1


def _phash_file(path: str | Path) -> int:
    return average_hash(path)


def qc_image(path: str | Path, target_w: int, target_h: int) -> Dict[str, Any]:
    """QC a single illustration image. Returns a result dict with 'passed'."""
    path = str(path)
    blur = laplacian_variance(path)
    aspect_ok = check_aspect_size(path, target_w, target_h)
    text_like = flag_text_like(path)
    blur_ok = blur >= BLUR_VARIANCE_MIN
    passed = blur_ok and aspect_ok and not text_like
    return {
        "path": path,
        "passed": passed,
        "blur_variance": round(blur, 2),
        "blur_ok": blur_ok,
        "aspect_ok": aspect_ok,
        "text_like": text_like,
        "dimensions": _dimensions(path),
    }


def qc_batch(paths: List[str], target_w: int, target_h: int) -> Dict[str, Any]:
    """QC a batch; also checks pairwise p-hash near-duplicates.

    Returns dict with per-image results and a 'duplicates' list of index pairs.
    """
    results = [qc_image(p, target_w, target_h) for p in paths]
    hashes = [average_hash(p) for p in paths]
    duplicates: List[Dict[str, Any]] = []
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            d = hamming_distance(hashes[i], hashes[j])
            if d <= PHASH_HAMMING_MAX:
                duplicates.append(
                    {"i": i, "j": j, "hamming": d,
                     "file_i": paths[i], "file_j": paths[j]}
                )
    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(paths),
        "passed": passed,
        "failed": len(paths) - passed,
        "duplicates": duplicates,
        "results": results,
        "batch_ok": passed == len(paths) and not duplicates,
    }
