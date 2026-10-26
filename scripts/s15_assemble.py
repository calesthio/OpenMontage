#!/usr/bin/env python3
"""S15: assemble the per-image CSV + recipe stats from the style-lock kernel.

Reads only local artefacts (no network, no model judgement).

Outputs:
  docs/openmontage/image_gen/S15_RESULTS.csv   one row per image (42)
  docs/openmontage/image_gen/S15_STATS.json    per-style + wide-bucket stats

CSV columns (the S15 task contract):
  style, scene, seed, size, steps, cfg, warm_sec_per_img (first of each bucket
  excluded), peak_vram_allocated_mb, peak_vram_reserved_mb, black_or_nan,
  output_file (+ render_id for joins)

Usage:
  python scripts/s15_assemble.py \
      --manifest /tmp/kilo/s15_out/<job>/s15_style_lock_dreamshaper-xl-1-0/manifest.json
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = Path(
    "/tmp/kilo/s15_out/s15-style-lock-1/s15_style_lock_dreamshaper-xl-1-0/"
    "manifest.json")
OUT_CSV = REPO / "docs/openmontage/image_gen/S15_RESULTS.csv"
OUT_STATS = REPO / "docs/openmontage/image_gen/S15_STATS.json"

CSV_HEADER = ["style", "scene", "seed", "size", "steps", "cfg",
              "warm_sec_per_img", "peak_vram_allocated_mb",
              "peak_vram_reserved_mb", "black_or_nan", "output_file",
              "render_id"]


def _size(img: Dict[str, Any]) -> str:
    return f"{img.get('width')}x{img.get('height')}"


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--out-csv", default=str(OUT_CSV))
    ap.add_argument("--out-stats", default=str(OUT_STATS))
    args = ap.parse_args(argv)

    mp = Path(args.manifest)
    if not mp.is_file():
        raise SystemExit(f"BLOCKED: manifest not found: {mp}")
    man = json.loads(mp.read_text(encoding="utf-8"))
    images = man.get("images") or []
    if not images:
        raise SystemExit("BLOCKED: manifest has no images")

    # warm-up = the first generated image of each bucket (1024 square / wide)
    seen_bucket: set = set()
    rows: List[Dict[str, Any]] = []
    for img in images:
        bucket = "wide" if int(img.get("width") or 0) != int(img.get("height") or 0) \
            else "square"
        first = bucket not in seen_bucket
        seen_bucket.add(bucket)
        warm = "" if first else (round(float(img["seconds"]), 4)
                                 if img.get("seconds") is not None else "")
        rows.append({
            "style": img.get("style"),
            "scene": img.get("scene_id"),
            "seed": img.get("seed"),
            "size": _size(img),
            "steps": img.get("steps"),
            "cfg": img.get("guidance_scale"),
            "warm_sec_per_img": warm,
            "peak_vram_allocated_mb": img.get("peak_vram_allocated_mb"),
            "peak_vram_reserved_mb": img.get("peak_vram_reserved_mb"),
            "black_or_nan": "yes" if (img.get("black") or img.get("nonfinite"))
                            else "no",
            "output_file": img.get("file") or "",
            "render_id": img.get("render_id"),
        })

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    def bucket_stats(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        times = [float(i["seconds"]) for i in items
                 if i.get("file") and i.get("seconds") is not None]
        warm = times[1:] if len(times) > 1 else times
        alloc = [i.get("peak_vram_allocated_mb") for i in items
                 if i.get("peak_vram_allocated_mb") is not None]
        res = [i.get("peak_vram_reserved_mb") for i in items
               if i.get("peak_vram_reserved_mb") is not None]
        return {
            "images": len(items),
            "generated": len(times),
            "median_sec_per_image": round(statistics.median(times), 3)
            if times else None,
            "median_warm_sec_per_image": round(statistics.median(warm), 3)
            if warm else None,
            "mean_warm_sec_per_image": round(statistics.mean(warm), 3)
            if warm else None,
            "peak_vram_allocated_mb": max(alloc) if alloc else None,
            "peak_vram_reserved_mb": max(res) if res else None,
            "black_or_nan": sum(1 for i in items
                                if i.get("black") or i.get("nonfinite")),
            "caption_readable": sum(1 for i in items
                                    if i.get("caption_readable") is True),
            "caption_unreadable": sum(1 for i in items
                                      if i.get("caption_readable") is False),
            "blur_flagged": sum(1 for i in items if i.get("blur_flag") is True),
        }

    square = [i for i in images
              if int(i.get("width") or 0) == int(i.get("height") or 0)]
    wide = [i for i in images
            if int(i.get("width") or 0) != int(i.get("height") or 0)]

    per_style = {
        style: bucket_stats([i for i in square if i.get("style") == style])
        for style in sorted({i.get("style") for i in square if i.get("style")})
    }
    per_scene = {
        scene: bucket_stats([i for i in square if i.get("scene_id") == scene])
        for scene in sorted({i.get("scene_id") for i in square})
    }

    stats = {
        "schema_version": "1.0",
        "milestone": "S15",
        "job_id": man.get("job_id"),
        "model": man.get("model"),
        "model_id": man.get("model_id"),
        "model_revision": man.get("model_revision"),
        "pipeline_class": man.get("pipeline_class"),
        "dtype": man.get("dtype"),
        "bf16": man.get("bf16"),
        "bitsandbytes": man.get("bitsandbytes"),
        "device": man.get("device"),
        "scheduler": (man.get("load_notes") or {}).get("scheduler"),
        "steps": (square[0] if square else {}).get("steps"),
        "cfg": (square[0] if square else {}).get("guidance_scale"),
        "requested": man.get("requested"),
        "wide_requested": man.get("wide_requested"),
        "total_requested": man.get("total_requested"),
        "generated": man.get("generated"),
        "load_seconds": man.get("load_seconds"),
        "gpu_seconds": man.get("gpu_seconds"),
        "oom_count": man.get("oom_count"),
        "black_count": man.get("black_count"),
        "nan_count": man.get("nan_count"),
        "wall_cap_hit": man.get("wall_cap_hit"),
        "install_stack": (man.get("install_log") or {}).get("used_stack"),
        "versions": man.get("versions"),
        "wide_style": None,
        "buckets": {"square_1024": bucket_stats(square),
                    "wide_1344x768": bucket_stats(wide)},
        "per_style": per_style,
        "per_scene": per_scene,
        "warm_definition": "first generated image of each bucket excluded "
                           "(1024 bucket and 1344x768 bucket separately)",
        "source_manifest": str(mp),
    }
    wide_style_path = mp.parent / "wide_style.json"
    if wide_style_path.is_file():
        stats["wide_style"] = json.loads(wide_style_path.read_text(encoding="utf-8"))

    out_stats = Path(args.out_stats)
    out_stats.parent.mkdir(parents=True, exist_ok=True)
    out_stats.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")

    for style, d in per_style.items():
        print(f"{style}: {d['images']} images, median warm "
              f"{d['median_warm_sec_per_image']}s, black/nan {d['black_or_nan']}, "
              f"caption unreadable {d['caption_unreadable']}")
    print(f"wrote {out_csv} ({len(rows)} rows)")
    print(f"wrote {out_stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
