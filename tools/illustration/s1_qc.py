#!/usr/bin/env python3
"""S1-2 automatic QC on generated stills (no automatic anatomy judgment).

Checks:
- Laplacian blur (variance of Laplacian) -> below threshold => blur flag
- perceptual-hash duplicates -> near-identical images flagged
- aspect/size -> outside target (1280x720 or 1024x1024) flagged
- text-like artifacts -> flagged for human review (not an automatic pass/fail)
- limb/anatomy -> flagged for HUMAN review only; never claimed as automatic

Stdlib + Pillow + imagehash (if available). No media committed.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageFilter, ImageOps  # noqa: E402

try:  # imagehash is optional; pHash duplicate check degrades gracefully
    import imagehash  # noqa: E402
    _HAS_IMAGEHASH = True
except Exception:  # noqa: BLE001
    _HAS_IMAGEHASH = False

# Target aspect ratios (width:height) accepted for this niche.
TARGET_ASPECTS = {(16, 9), (1, 1)}
TARGET_SIZES = {(1280, 720), (1024, 1024)}


def laplacian_blur(img: Image.Image) -> float:
    """Variance of Laplacian (higher = sharper). Returns float score."""
    gray = ImageOps.grayscale(img)
    lap = gray.filter(ImageFilter.FIND_EDGES)  # proxy for edge energy
    # FIND_EDGES highlights edges; compute variance of pixel intensities
    pixels = list(lap.getdata())
    n = len(pixels)
    mean = sum(pixels) / n
    var = sum((p - mean) ** 2 for p in pixels) / n
    return float(var)


def phash(img: Image.Image) -> Any:
    if not _HAS_IMAGEHASH:
        return None
    return imagehash.phash(img)


def aspect_ratio_ok(size: Tuple[int, int]) -> bool:
    w, h = size
    g = math.gcd(w, h)
    return (w // g, h // g) in TARGET_ASPECTS


def size_ok(size: Tuple[int, int]) -> bool:
    return size in TARGET_SIZES


def text_like_artifacts(img: Image.Image) -> bool:
    """Heuristic: detect blocks of high-contrast small structured regions
    that resemble rendered text. Returns True if text-like artifacts suspected
    (flag for human review; not automatic reject)."""
    gray = ImageOps.grayscale(img).resize((160, 90))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    px = list(edges.getdata())
    # text tends to produce many small sharp transitions: count edge pixels
    edge_px = sum(1 for p in px if p > 120)
    frac = edge_px / len(px)
    # threshold chosen conservatively -> False positives go to human review
    return frac > 0.25


def check_image(path: Path) -> Dict[str, Any]:
    with Image.open(path) as img:
        size = img.size
        blur = laplacian_blur(img)
        ph = phash(img)
    return {
        "file": path.name,
        "size": size,
        "aspect_ok": aspect_ratio_ok(size),
        "size_ok": size_ok(size),
        "blur_variance": round(blur, 2),
        "blur_flag": blur < 80.0,  # tentative threshold; tune per batch
        "phash": str(ph) if ph is not None else None,
        "text_like": text_like_artifacts(img),
        # anatomy/limb: deliberately NOT auto-judged -> human review flag
        "anatomy_human_review": True,
    }


def check_batch(image_paths: List[Path]) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    phash_objs: List[Tuple[Path, Any]] = []  # (path, imagehash.ImageHash or None)
    for p in image_paths:
        with Image.open(p) as img:
            size = img.size
            blur = laplacian_blur(img)
            phobj = phash(img)
            text = text_like_artifacts(img)
        results.append({
            "file": p.name,
            "size": size,
            "aspect_ok": aspect_ratio_ok(size),
            "size_ok": size_ok(size),
            "blur_variance": round(blur, 2),
            "blur_flag": blur < 80.0,
            "phash": str(phobj) if phobj is not None else None,
            "text_like": text,
            "anatomy_human_review": True,
        })
        if phobj is not None:
            phash_objs.append((p, phobj))

    # duplicate detection via pHash hamming distance
    duplicates: List[Dict[str, Any]] = []
    for i in range(len(phash_objs)):
        for j in range(i + 1, len(phash_objs)):
            p1, h1 = phash_objs[i]
            p2, h2 = phash_objs[j]
            try:
                dist = h1 - h2
            except Exception:
                continue
            if dist <= 5:
                duplicates.append({
                    "a": p1.name,
                    "b": p2.name,
                    "hamming_distance": int(dist),
                })

    summary = {
        "total": len(results),
        "blur_flags": sum(1 for r in results if r["blur_flag"]),
        "text_like_flags": sum(1 for r in results if r["text_like"]),
        "aspect_failures": sum(1 for r in results if not r["aspect_ok"]),
        "size_failures": sum(1 for r in results if not r["size_ok"]),
        "duplicate_pairs": len(duplicates),
        "anatomy_human_review_count": len(results),  # all go to human review
    }
    return {
        "results": results,
        "duplicates": duplicates,
        "summary": summary,
        "ok": summary["blur_flags"] == 0 and summary["text_like_flags"] == 0
        and summary["aspect_failures"] == 0 and summary["size_failures"] == 0
        and summary["duplicate_pairs"] == 0,
    }
