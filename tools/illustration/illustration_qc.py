#!/usr/bin/env python3
"""tools/illustration/illustration_qc.py — auto QC for AI-generated illustrations.

Checks (all objective, none of them a beauty judgement):

  * blur (Laplacian variance) - a technical sharpness measure,
  * aspect AND exact size against the target frame,
  * text-like artifacts (connected-component detector, see text_detect.py),
  * palette drift against the niche style file (the palette must show up),
  * near-duplicates across an episode (average hash + difference hash).

Anatomy, composition and beauty stay **owner-judged**: this module never
scores them. The thresholds live in `config/qc_thresholds.json`
(`illustration_qc`); nothing here changes them silently.

Pillow + numpy only; no network, no paid routes, no new runtime dependency.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageOps

from tools.illustration.text_detect import detect_text_like

REPO = Path(__file__).resolve().parents[2]
THRESHOLDS_PATH = REPO / "config" / "qc_thresholds.json"

# Fallbacks used only when the config cannot be read (fail closed elsewhere).
BLUR_VARIANCE_MIN = 100.0
PHASH_HAMMING_MAX = 8          # <= 8 => near-duplicate
ASPECT_TOLERANCE = 0.01        # 1%
SIZE_EXACT = True
PALETTE_COLOR_DISTANCE_MAX = 70
PALETTE_MIN_COVERAGE = 0.04
PALETTE_MAX_OFF_PALETTE_SHARE = 0.92


def load_thresholds(path: str | Path | None = None) -> Dict[str, Any]:
    """The illustration QC thresholds (config/qc_thresholds.json)."""
    p = Path(path) if path else THRESHOLDS_PATH
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    section = doc.get("illustration_qc")
    return dict(section) if isinstance(section, dict) else {}


def _threshold(name: str, default: Any) -> Any:
    section = load_thresholds()
    return section.get(name, default)


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


def difference_hash(path: str | Path) -> int:
    """64-bit difference hash (horizontal gradient)."""
    img = _load_gray(path).resize((9, 8)).convert("L")
    px = list(img.getdata())
    h = 0
    for y in range(8):
        row = px[y * 9:(y + 1) * 9]
        for x in range(8):
            if row[x] > row[x + 1]:
                h |= 1 << (63 - (y * 8 + x))
    return h


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _dimensions(path: str | Path) -> Tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def check_aspect_size(path: str | Path, target_w: int, target_h: int) -> bool:
    """True if the image matches the target frame (ratio and, if configured,
    the exact pixel size)."""
    w, h = _dimensions(path)
    if w <= 0 or h <= 0:
        return False
    target_ratio = target_w / target_h
    actual_ratio = w / h
    tolerance = float(_threshold("aspect_tolerance", ASPECT_TOLERANCE))
    if abs(actual_ratio - target_ratio) / target_ratio > tolerance:
        return False
    if _threshold("size_exact", SIZE_EXACT):
        if (w, h) != (target_w, target_h):
            return False
    return True


def flag_text_like(path: str | Path) -> bool:
    """True when the image contains lettering or text-like artifacts.

    P4: the connected-component detector replaced the old "thin near-white
    band" heuristic, which missed lettering and over-fired on flat art.
    """
    return bool(detect_text_like(path)["text_like"])


def flag_caption_band(path: str | Path) -> bool:
    """The OLD heuristic, kept as a separate (secondary) flag.

    Thin near-white horizontal bands in the top/bottom thirds look like a
    caption chip. They are no longer a text verdict (that over-fired on flat
    art); the flag is reported so the owner still sees the plate.
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
                run_end = y
                while run_end < y1 and sum(1 for x in range(w) if px[x, run_end] > 240) / w > 0.9:
                    run_end += 1
                run_h = run_end - y
                above_dark = y == y0 or sum(1 for x in range(w) if px[x, y - 1] > 240) / w < 0.6
                below_dark = run_end >= y1 or sum(1 for x in range(w) if px[x, run_end] > 240) / w < 0.6
                if 1 <= run_h <= 8 and above_dark and below_dark:
                    band_count += 1
                y = run_end
            else:
                y += 1
    return band_count >= 1


def text_evidence(path: str | Path) -> Dict[str, Any]:
    """The detector's evidence (lines, characters, polarity)."""
    return detect_text_like(path)


# --------------------------------------------------------------- palette
def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def palette_drift(path: str | Path, palette: Dict[str, str]) -> Dict[str, Any]:
    """How well the image matches the style palette.

    Reports the share of pixels that sit close to a palette colour and the
    share of the dominant colour that is NOT in the palette.
    """
    if not palette:
        return {"checked": False, "reason": "the style has no palette"}
    with Image.open(path) as img:
        small = img.convert("RGB").resize((128, 128), Image.BILINEAR)
        pixels = np.asarray(small, dtype=np.int16).reshape(-1, 3)
    distance_max = int(_threshold("color_distance_max", PALETTE_COLOR_DISTANCE_MAX)
                       or PALETTE_COLOR_DISTANCE_MAX)
    min_coverage = float(_threshold("min_palette_coverage", PALETTE_MIN_COVERAGE)
                         or PALETTE_MIN_COVERAGE)
    max_off = float(_threshold("max_off_palette_share", PALETTE_MAX_OFF_PALETTE_SHARE)
                    or PALETTE_MAX_OFF_PALETTE_SHARE)

    hits = np.zeros(len(pixels), dtype=bool)
    per_token: Dict[str, float] = {}
    float_pixels = pixels.astype(np.float32)
    for token, hex_value in palette.items():
        target = np.array(_hex_to_rgb(hex_value), dtype=np.float32)
        distance = np.sqrt(((float_pixels - target) ** 2).sum(axis=1))
        token_hits = distance <= distance_max
        per_token[token] = round(float(token_hits.mean()), 4)
        hits |= token_hits
    coverage = float(hits.mean())

    # the dominant colour of the image (coarse 32-value buckets)
    quantized = (pixels // 32).astype(np.int32)
    keys = quantized[:, 0] * 4096 + quantized[:, 1] * 64 + quantized[:, 2]
    values, counts = np.unique(keys, return_counts=True)
    dominant = values[int(np.argmax(counts))]
    dominant_rgb = (int((dominant // 4096) * 32), int(((dominant // 64) % 64) * 32),
                    int((dominant % 64) * 32))
    off_palette = all(
        float(np.sqrt(((np.array(dominant_rgb, dtype=np.float32)
                        - np.array(_hex_to_rgb(v), dtype=np.float32)) ** 2).sum()))
        > distance_max for v in palette.values())
    off_share = 1.0 - coverage
    drift = (coverage < min_coverage) or (off_palette and off_share > max_off)
    return {
        "checked": True,
        "coverage": round(coverage, 4),
        "per_token": per_token,
        "dominant_rgb": list(dominant_rgb),
        "dominant_off_palette": bool(off_palette),
        "drift": bool(drift),
        "min_palette_coverage": min_coverage,
    }


# ------------------------------------------------------------ duplicates
def _brightness(path: str | Path) -> Tuple[float, float]:
    """(mean, std) of the grayscale image - flat images carry no hash info."""
    array = np.asarray(_load_gray(path), dtype=np.float32)
    return float(array.mean()), float(array.std())


def duplicate_report(paths: Sequence[str],
                     brightness_tolerance: int = 12) -> Dict[str, Any]:
    """Near-duplicate detection across an episode.

    Two hashes are used (average + difference); a pair is a near-duplicate
    when both hashes are within the configured Hamming distance AND the mean
    brightness is close. The brightness guard matters: two DIFFERENT flat
    images share an all-zero hash, and they are not duplicates.
    """
    limit = int(_threshold("duplicate_hamming_max", PHASH_HAMMING_MAX)
                or PHASH_HAMMING_MAX)
    a_hashes = [average_hash(p) for p in paths]
    d_hashes = [difference_hash(p) for p in paths]
    brightness = [_brightness(p) for p in paths]
    duplicates: List[Dict[str, Any]] = []
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            a_dist = hamming_distance(a_hashes[i], a_hashes[j])
            d_dist = hamming_distance(d_hashes[i], d_hashes[j])
            mean_delta = abs(brightness[i][0] - brightness[j][0])
            if (a_dist <= limit and d_dist <= limit
                    and mean_delta <= brightness_tolerance):
                duplicates.append({
                    "i": i, "j": j,
                    "file_i": paths[i], "file_j": paths[j],
                    "average_hash_distance": a_dist,
                    "difference_hash_distance": d_dist,
                    "brightness_delta": round(mean_delta, 2),
                })
    return {"total": len(paths), "duplicates": duplicates,
            "hamming_max": limit}


# ----------------------------------------------------------------- checks
def qc_image(path: str | Path, target_w: int, target_h: int,
              palette: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """QC a single illustration image. Returns a result dict with 'passed'."""
    path = str(path)
    blur = laplacian_variance(path)
    aspect_ok = check_aspect_size(path, target_w, target_h)
    text = detect_text_like(path)
    blur_min = float(_threshold("blur_variance_min", BLUR_VARIANCE_MIN)
                     or BLUR_VARIANCE_MIN)
    blur_ok = blur >= blur_min
    drift = palette_drift(path, palette or {})
    palette_ok = not drift.get("drift", False)
    passed = blur_ok and aspect_ok and not text["text_like"] and palette_ok
    return {
        "path": path,
        "passed": passed,
        "blur_variance": round(blur, 2),
        "blur_ok": blur_ok,
        "aspect_ok": aspect_ok,
        "size_ok": _dimensions(path) == (target_w, target_h),
        "text_like": bool(text["text_like"]),
        "text_evidence": text,
        "palette": drift,
        "palette_ok": palette_ok,
        "dimensions": list(_dimensions(path)),
        "band_artifact": flag_caption_band(path),
    }


def qc_batch(paths: List[str], target_w: int, target_h: int,
             palette: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """QC a batch; also checks pairwise near-duplicates across the batch."""
    results = [qc_image(p, target_w, target_h, palette) for p in paths]
    duplicates = duplicate_report(paths)["duplicates"]
    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(paths),
        "passed": passed,
        "failed": len(paths) - passed,
        "duplicates": duplicates,
        "results": results,
        "batch_ok": passed == len(paths) and not duplicates,
    }
