#!/usr/bin/env python3
"""S5-3: objective, non-aesthetic checks on generated stills.

Flags only — nothing here judges beauty or anatomy (the owner does that).

  * resolution      — image size vs the requested 1024x1024
  * blur            — Laplacian variance (absolute flag) + within-scene relative
                      flag (a flat-vector plate is legitimately smooth, so only
                      a scene-relative outlier counts as "much softer")
  * text-like       — heuristic: horizontal bands of high edge density with
                      regular spacing (lettering often looks like this).
                      HEURISTIC, not OCR; treat as "look at this one".
  * duplicates      — 64-bit difference hash (dHash); hamming distance <= 6
                      inside a scene, or <= 4 anywhere.

Usage:
  python scripts/s5_checks.py --root /tmp/kilo/s5_out \
      --out docs/openmontage/image_gen/S5_CHECKS.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
EXPECTED_SIZE = (1024, 1024)

# Absolute Laplacian-variance floor: below this the frame has almost no edges.
BLUR_ABS_FLOOR = 15.0
# Within-scene relative floor: flag if this image is < 35% of its scene median.
BLUR_REL_RATIO = 0.35
# Text-like heuristic thresholds.
TEXT_BLOCK = 32
TEXT_EDGE_PERCENTILE = 99.0
TEXT_BLOCK_DENSITY = 0.12
TEXT_ROW_FRACTION = 0.6
DUP_SAME_SCENE = 6
DUP_ANY = 4


def _gray(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("L"), dtype=np.float32)


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
    }


def find_manifests(root: Path) -> List[Path]:
    return sorted(root.glob("s5_bakeoff_*/manifest.json"))


def run(root: Path, out_path: Path) -> Dict[str, Any]:
    manifests = find_manifests(root)
    if not manifests:
        raise SystemExit(f"no s5_bakeoff_*/manifest.json under {root}")

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
            })
            checked.append(c)
            rows.append(c)
        per_model[model] = {
            "manifest": str(mp),
            "images": len([c for c in checked if not c.get("missing")]),
            "black_count": man.get("black_count"),
            "nan_count": man.get("nan_count"),
            "oom_count": man.get("oom_count"),
            "steady_state_sec_per_image": man.get("steady_state_sec_per_image"),
            "peak_vram_mb": man.get("peak_vram_mb"),
            "load_seconds": man.get("load_seconds"),
            "versions": man.get("versions"),
            "pipeline_class": man.get("pipeline_class"),
            "checks": checked,
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
        "milestone": "S5-3",
        "note": "objective flags only; anatomy/beauty are the owner's judgement",
        "thresholds": {
            "blur_abs_laplacian_floor": BLUR_ABS_FLOOR,
            "blur_rel_ratio_of_scene_median": BLUR_REL_RATIO,
            "text_like_row_fraction": TEXT_ROW_FRACTION,
            "dup_hamming_same_scene": DUP_SAME_SCENE,
            "dup_hamming_any": DUP_ANY,
        },
        "per_model": {m: {k: v for k, v in d.items() if k != "checks"}
                      for m, d in per_model.items()},
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
              f"dupes={sum(1 for d2 in duplicates if m in d2['a'].split(':')[0] or m in d2['b'].split(':')[0])}")
    print(f"wrote {out_path}")
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="/tmp/kilo/s5_out")
    ap.add_argument("--out", default=str(REPO / "docs/openmontage/image_gen/S5_CHECKS.json"))
    args = ap.parse_args(argv)
    run(Path(args.root), Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
