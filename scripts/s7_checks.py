#!/usr/bin/env python3
"""S7-6: objective, non-aesthetic checks on the generated stills.

Flags only — nothing here judges beauty, anatomy or style (the owner does
that, blind).

Per image:
  * resolution        — vs the requested 1024x1024
  * blur              — Laplacian variance (absolute floor + within-scene
                        relative outlier; a flat-vector plate is legitimately
                        smooth, so only a scene-relative outlier counts)
  * text-like         — heuristic: horizontal bands of high edge density
                        with regular spacing (lettering often looks like this).
                        HEURISTIC, not OCR; treat as "look at this one".
  * duplicates        — 64-bit difference hash (dHash); hamming distance <= 6
                        inside a scene, or <= 4 anywhere.
  * saturation        — mean HSV saturation; outlier vs the model's own median
  * contrast          — RMS contrast (std of the luma); outlier vs the model's
                        own median

Usage:
  python scripts/s7_checks.py --root /tmp/kilo/s7_out \
      --out docs/openmontage/image_gen/S7_CHECKS.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
EXPECTED_SIZE = (1024, 1024)

BLUR_ABS_FLOOR = 15.0
BLUR_REL_RATIO = 0.35
TEXT_BLOCK = 32
TEXT_EDGE_PERCENTILE = 99.0
TEXT_BLOCK_DENSITY = 0.12
TEXT_ROW_FRACTION = 0.6
DUP_SAME_SCENE = 6
DUP_ANY = 4
# Robust outlier rule: |x - median| > OUTLIER_Z * (1.4826 * MAD)
OUTLIER_Z = 3.0
OUTLIER_FLOOR_SAT = 6.0
OUTLIER_FLOOR_CONTRAST = 4.0


def _gray(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("L"), dtype=np.float32)


def _saturation(path: Path) -> float:
    with Image.open(path) as im:
        hsv = np.asarray(im.convert("HSV"), dtype=np.float32)
    return float(hsv[:, :, 1].mean())


def laplacian_variance(gray: np.ndarray) -> float:
    """4-neighbour Laplacian response variance (higher = more detail/edges)."""
    k = (
        np.roll(gray, 1, axis=0) + np.roll(gray, -1, axis=0)
        + np.roll(gray, 1, axis=1) + np.roll(gray, -1, axis=1)
        - 4.0 * gray
    )
    return float(k.var())


def text_like_score(gray: np.ndarray) -> float:
    """Max fraction of high-edge blocks in any horizontal band (0..1)."""
    gy, gx = np.gradient(gray)
    edges = np.abs(gx) + np.abs(gy)
    if edges.max() <= 0:
        return 0.0
    thr = float(np.percentile(edges, TEXT_EDGE_PERCENTILE)) * 0.5
    mask = edges > thr
    h, w = mask.shape
    bh, bw = h // TEXT_BLOCK, w // TEXT_BLOCK
    if bh < 1 or bw < 1:
        return 0.0
    blocks = mask[: bh * TEXT_BLOCK, : bw * TEXT_BLOCK]
    density = blocks.reshape(bh, TEXT_BLOCK, bw, TEXT_BLOCK).mean(axis=(1, 3))
    per_row = (density > TEXT_BLOCK_DENSITY).mean(axis=1)
    return float(per_row.max()) if per_row.size else 0.0


def dhash(path: Path, size: int = 8) -> int:
    """64-bit difference hash; only relative hamming distance is meaningful."""
    with Image.open(path) as im:
        small = np.asarray(
            im.convert("L").resize((size + 1, size), Image.LANCZOS), dtype=np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    out = 0
    for b in bits:
        out = (out << 1) | int(b)
    return out


def hamming(a: int, b: int) -> int:
    return int(a ^ b).bit_count()


def _mad_outliers(values: List[float], floor: float) -> List[bool]:
    """Robust per-model outlier flags (median + MAD)."""
    if not values:
        return []
    med = float(np.median(values))
    mad = float(np.median([abs(v - med) for v in values]))
    scale = 1.4826 * mad
    tol = max(OUTLIER_Z * scale, floor)
    return [abs(v - med) > tol for v in values]


def check_image(path: Path) -> Dict[str, Any]:
    gray = _gray(path)
    with Image.open(path) as im:
        size = im.size
    score = text_like_score(gray)
    return {
        "file": path.name,
        "width": size[0],
        "height": size[1],
        "resolution_ok": list(size) == list(EXPECTED_SIZE),
        "laplacian_var": round(laplacian_variance(gray), 3),
        "text_like_score": round(score, 3),
        "text_like_flag": score >= TEXT_ROW_FRACTION,
        "dhash": dhash(path),
        "saturation_mean": round(_saturation(path), 2),
        "contrast_rms": round(float(gray.std()), 2),
    }


def find_manifests(root: Path) -> List[Path]:
    return sorted(root.glob("s7_bakeoff_*/manifest.json"))


def run(root: Path, out_path: Path) -> Dict[str, Any]:
    manifests = find_manifests(root)
    if not manifests:
        raise SystemExit(f"no s7_bakeoff_*/manifest.json under {root}")

    per_model: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
    for mp in manifests:
        man = json.loads(mp.read_text(encoding="utf-8"))
        model = man["model"]
        img_dir = mp.parent / "images"
        checked = []
        for entry in man.get("images", []):
            if not entry.get("file"):
                continue
            path = img_dir / entry["file"]
            if not path.is_file():
                checked.append({"file": entry["file"], "missing": True})
                continue
            c = check_image(path)
            c.update({
                "render_id": entry["render_id"],
                "scene_id": entry.get("scene_id"),
                "variant": entry.get("variant"),
                "model": model,
                "manifest_sha256": entry.get("sha256"),
                "manifest_bytes": entry.get("bytes"),
            })
            checked.append(c)
            rows.append(c)
        per_model[model] = {
            "manifest": str(mp),
            "job_id": man.get("job_id"),
            "images": len([c for c in checked if not c.get("missing")]),
            "black_count": man.get("black_count"),
            "nan_count": man.get("nan_count"),
            "oom_count": man.get("oom_count"),
            "load_seconds": man.get("load_seconds"),
            "steady_state_sec_per_image": man.get("steady_state_sec_per_image"),
            "usable_images_per_minute": man.get("usable_images_per_minute"),
            "peak_vram_mb": man.get("peak_vram_mb"),
            "pipeline_class": man.get("pipeline_class"),
            "versions": man.get("versions"),
        }

    # within-scene blur outliers
    by_scene: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_scene.setdefault(r.get("scene_id") or "?", []).append(r)
    for scene, items in by_scene.items():
        vals = [i["laplacian_var"] for i in items]
        median = float(np.median(vals)) if vals else 0.0
        for i in items:
            i["blur_flag_absolute"] = i["laplacian_var"] < BLUR_ABS_FLOOR
            i["blur_flag_relative"] = bool(
                median > 0 and i["laplacian_var"] < BLUR_REL_RATIO * median)
            i["scene_median_laplacian"] = round(median, 3)

    # saturation / contrast outliers, per model (robust MAD rule)
    for model in per_model:
        items = [r for r in rows if r["model"] == model]
        sat_flags = _mad_outliers([i["saturation_mean"] for i in items],
                                  OUTLIER_FLOOR_SAT)
        con_flags = _mad_outliers([i["contrast_rms"] for i in items],
                                  OUTLIER_FLOOR_CONTRAST)
        for i, sf, cf in zip(items, sat_flags, con_flags):
            i["saturation_outlier"] = sf
            i["contrast_outlier"] = cf
        per_model[model]["saturation_median"] = round(
            float(np.median([i["saturation_mean"] for i in items])), 2) if items else None
        per_model[model]["contrast_median"] = round(
            float(np.median([i["contrast_rms"] for i in items])), 2) if items else None

    # duplicates
    duplicates: List[Dict[str, Any]] = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            d = hamming(a["dhash"], b["dhash"])
            same_scene = a.get("scene_id") == b.get("scene_id")
            if d <= (DUP_SAME_SCENE if same_scene else DUP_ANY):
                duplicates.append({
                    "a": f"{a['model']}:{a['render_id']}",
                    "b": f"{b['model']}:{b['render_id']}",
                    "hamming": d,
                    "same_scene": same_scene,
                })

    report = {
        "schema_version": "1.0",
        "milestone": "S7-6",
        "note": "objective flags only; anatomy/beauty/style are the owner's "
                "blind judgement, not this script's",
        "thresholds": {
            "blur_abs_laplacian_floor": BLUR_ABS_FLOOR,
            "blur_rel_ratio_of_scene_median": BLUR_REL_RATIO,
            "text_like_row_fraction": TEXT_ROW_FRACTION,
            "dup_hamming_same_scene": DUP_SAME_SCENE,
            "dup_hamming_any": DUP_ANY,
            "saturation_contrast_outlier_z": OUTLIER_Z,
        },
        "per_model": per_model,
        "images": rows,
        "duplicates": duplicates,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for m, d in report["per_model"].items():
        imgs = [r for r in rows if r["model"] == m]
        print(f"{m}: {d['images']} images, "
              f"resolution_bad={sum(1 for r in imgs if not r['resolution_ok'])}, "
              f"blur_abs={sum(1 for r in imgs if r['blur_flag_absolute'])}, "
              f"blur_rel={sum(1 for r in imgs if r['blur_flag_relative'])}, "
              f"text_like={sum(1 for r in imgs if r['text_like_flag'])}, "
              f"sat_out={sum(1 for r in imgs if r['saturation_outlier'])}, "
              f"contrast_out={sum(1 for r in imgs if r['contrast_outlier'])}")
    print(f"duplicates: {len(duplicates)}")
    print(f"wrote {out_path}")
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="/tmp/kilo/s7_out")
    ap.add_argument("--out", default=str(REPO / "docs/openmontage/image_gen/S7_CHECKS.json"))
    args = ap.parse_args(argv)
    run(Path(args.root), Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
