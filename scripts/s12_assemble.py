#!/usr/bin/env python3
"""S12: assemble the per-image CSV + per-model stats from the 3 verified
Kaggle manifests. Reads only local artefacts (no network, no model judgment).

Outputs:
  docs/openmontage/image_gen/S12_RESULTS.csv   (54 rows, one per image)
  docs/openmontage/image_gen/S12_STATS.json    (per-model + per-seed-cohort stats)
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

MODEL_ORDER = ["klein", "dreamshaper-xl-lightning", "dreamshaper-xl-1-0"]
SEEDS = [1001, 2027, 4409]
SCENES = ["s01", "s03", "s05", "s06", "s10", "s12"]

CSV_HEADER = ["model_id", "revision", "dtype", "scheduler", "steps", "cfg",
              "width", "height", "seed", "scene_id", "load_time",
              "warm_render_time", "peak_vram_allocated",
              "peak_vram_reserved", "black_or_nan_flag", "output_file"]


def load_manifest(model: str) -> Dict[str, Any]:
    p = Path(f"/tmp/kilo/s12_out/{model}/s12_bakeoff_{model}/manifest.json")
    if not p.is_file():
        raise SystemExit(f"BLOCKED: manifest not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def model_row_meta(m: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
    img0 = manifest["images"][0]
    scheduler = manifest["load_notes"].get("scheduler") or ""
    return {
        "model_id": manifest.get("model_id", ""),
        "revision": "",
        "dtype": manifest.get("dtype", ""),
        "scheduler": scheduler,
        "steps": img0.get("steps", 0),
        "cfg": img0.get("guidance_scale", 0),
        "width": manifest.get("width", 0),
        "height": manifest.get("height", 0),
        "load_time": manifest.get("load_seconds", 0.0),
        "peak_vram_allocated": manifest.get("peak_vram_mb"),
        "peak_vram_reserved": manifest.get("peak_vram_reserved_mb"),
    }


def main() -> int:
    rows: List[Dict[str, Any]] = []
    stats: List[Dict[str, Any]] = []

    for model in MODEL_ORDER:
        manifest = load_manifest(model)
        images = manifest.get("images", [])
        if not images:
            raise SystemExit(f"BLOCKED: no images in manifest for {model}")
        meta = model_row_meta(model, manifest)
        times = [float(i["seconds"]) for i in images if i.get("file")]
        warm_times = times[1:] if len(times) > 1 else times
        accepted = [i for i in images if i.get("file")
                    and not (i.get("black") or i.get("nonfinite"))]
        accepted_warm = [float(i["seconds"]) for i in accepted][1:] if accepted else []
        model_stats: Dict[str, Any] = {
            "model": model,
            "model_id": manifest.get("model_id"),
            "job_id": manifest.get("job_id"),
            "requested": manifest.get("requested"),
            "generated": manifest.get("generated"),
            "load_seconds": manifest.get("load_seconds"),
            "warm_images": len(warm_times),
            "median_warm_sec_per_image": (round(statistics.median(warm_times), 3)
                                          if warm_times else None),
            "mean_warm_sec_per_image": (round(statistics.mean(warm_times), 3)
                                        if warm_times else None),
            "sec_per_accepted_image": (round(sum(accepted_warm) / len(accepted_warm), 3)
                                       if accepted_warm else None),
            "accepted_count": len(accepted),
            "black_count": manifest.get("black_count"),
            "nan_count": manifest.get("nan_count"),
            "oom_count": manifest.get("oom_count"),
            "peak_vram_allocated_mb": manifest.get("peak_vram_mb"),
            "peak_vram_reserved_mb": manifest.get("peak_vram_reserved_mb"),
            "pipeline_class": manifest.get("pipeline_class"),
            "cpu_offload_used": manifest.get("cpu_offload_used"),
            "scheduler": meta["scheduler"],
            "steps": meta["steps"],
            "cfg": meta["cfg"],
            "versions": manifest.get("versions"),
            "install_stack": manifest.get("install_log", {}).get("used_stack"),
            "black_or_nan_images": [i["render_id"] for i in images
                                    if i.get("black") or i.get("nonfinite")],
        }
        stats.append(model_stats)

        first = True
        for img in images:
            warm = "" if first else round(float(img["seconds"]), 4)
            first = False
            rows.append({
                "model_id": meta["model_id"],
                "revision": meta["revision"],
                "dtype": meta["dtype"],
                "scheduler": meta["scheduler"],
                "steps": meta["steps"],
                "cfg": meta["cfg"],
                "width": meta["width"],
                "height": meta["height"],
                "seed": img.get("seed"),
                "scene_id": img.get("scene_id"),
                "load_time": round(meta["load_time"], 3),
                "warm_render_time": warm,
                "peak_vram_allocated": meta["peak_vram_allocated"],
                "peak_vram_reserved": meta["peak_vram_reserved"],
                "black_or_nan_flag": "yes" if (img.get("black") or img.get("nonfinite")) else "no",
                "output_file": img.get("file"),
            })

    # per seed cohort: 6 scenes x 3 models = 18 images per seed
    cohort_stats: List[Dict[str, Any]] = []
    for seed in SEEDS:
        cohort = [r for r in rows if r["seed"] == seed]
        usable = sum(1 for r in cohort if r["black_or_nan_flag"] == "no")
        cohort_stats.append({
            "seed": seed,
            "images": len(cohort),
            "usable_without_repair": usable,
            "black_or_nan": sum(1 for r in cohort if r["black_or_nan_flag"] == "yes"),
        })

    out_dir = REPO / "docs/openmontage/image_gen"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "S12_RESULTS.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(",".join(CSV_HEADER) + "\n")
        for r in rows:
            f.write(",".join("" if r[c] is None else str(r[c]) for c in CSV_HEADER) + "\n")

    report = {
        "schema_version": "1.0",
        "milestone": "S12",
        "models": stats,
        "seed_cohorts": cohort_stats,
        "total_images": len(rows),
        "total_black_or_nan": sum(1 for r in rows if r["black_or_nan_flag"] == "yes"),
        "csv": str(csv_path.relative_to(REPO)),
    }
    stats_path = out_dir / "S12_STATS.json"
    stats_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {csv_path} ({len(rows)} rows)")
    print(f"wrote {stats_path}")
    for s in stats:
        print(f"{s['model']}: generated={s['generated']} load={s['load_seconds']}s "
              f"median_warm={s['median_warm_sec_per_image']}s "
              f"sec_per_accepted={s['sec_per_accepted_image']}s "
              f"peak_vram_alloc={s['peak_vram_allocated_mb']}MB "
              f"peak_vram_reserved={s['peak_vram_reserved_mb']}MB "
              f"black={s['black_count']} nan={s['nan_count']}")
    for c in cohort_stats:
        print(f"seed {c['seed']}: {c['usable_without_repair']}/{c['images']} usable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
