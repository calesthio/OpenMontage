#!/usr/bin/env python3
"""S12: fetch ONE bake-off model's kernel output, verify it, measure every
image, and rebuild the per-image CSV + the per-model summary.

Run this the moment `kaggle kernels status` leaves RUNNING:

  python scripts/s12_collect.py --model klein --job-id s12-klein-1
  python scripts/s12_collect.py --model dreamshaper-xl-1-0 --job-id s12-dreamshaper-xl-1-0-1
  python scripts/s12_collect.py --model dreamshaper-xl-lightning --job-id s12-dreamshaper-xl-lightning-1

What it does
------------
1. fetch_output through the bridge (text + PNGs into /tmp/kilo/s12_out/<model>/)
2. bridge `verify` — sha256 fail-closed against the kernel manifest
3. measure every PNG: mean pixel, non-finite pixels -> `black_or_nan_flag`
   (the owner's definition: mean < 5 OR non-finite; the kernel's own stricter
   `max < 8` flag is kept alongside as `kernel_black_flag`)
4. rebuild docs/openmontage/image_gen/S12_PER_IMAGE.csv from EVERY model
   collected so far (idempotent), and write S12_MODEL_<model>.json

`accepted` is the owner's blind verdict; `sec_per_accepted_image` stays null
until projects/s12_blind/results.csv is filled and scripts/s12_tally.py has
run.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

DOCS = REPO / "docs/openmontage/image_gen"
OUT_ROOT = Path("/tmp/kilo/s12_out")
CSV_PATH = DOCS / "S12_PER_IMAGE.csv"
BLACK_MEAN_THRESHOLD = 5.0

CSV_FIELDS = [
    "model_id", "revision", "dtype", "scheduler", "steps", "cfg",
    "width", "height", "seed", "scene_id", "load_time", "warm_render_time",
    "peak_vram_allocated", "peak_vram_reserved", "black_or_nan_flag",
    "output_file",
    # extras (kept after the required block, never in place of it)
    "model_key", "render_id", "render_time_s", "mean_pixel",
    "kernel_black_flag", "kernel_nonfinite_flag", "job_id",
]

SCHEDULER_LABEL = {
    "klein": "FlowMatchEulerDiscreteScheduler (pipeline default)",
    "dreamshaper-xl-1-0": "DEISMultistepScheduler",
    "dreamshaper-xl-lightning": "DPMSolverMultistepScheduler",
}


def _load_s7_fetch():
    spec = importlib.util.spec_from_file_location(
        "s7_fetch", REPO / "scripts/s7_fetch.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _resolve_revision(model_id: str) -> Optional[str]:
    try:
        from huggingface_hub import HfApi
        return HfApi().model_info(model_id).sha
    except Exception:  # noqa: BLE001 - provenance best effort
        return None


def measure_png(path: Path) -> Dict[str, Any]:
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        arr = np.asarray(im.convert("RGB"), dtype=np.float32)
    nonfinite = bool((~np.isfinite(arr)).any())
    mean_pixel = float(arr.mean())
    return {
        "mean_pixel": round(mean_pixel, 2),
        "nonfinite": nonfinite,
        "black_or_nan": bool(nonfinite or mean_pixel < BLACK_MEAN_THRESHOLD),
        "width": int(arr.shape[1]),
        "height": int(arr.shape[0]),
    }


def collect(model: str, job_id: Optional[str], do_fetch: bool = True) -> Dict[str, Any]:
    dest = OUT_ROOT / model
    folder = f"s12_bakeoff_{model}"
    summary: Dict[str, Any] = {}
    if do_fetch:
        summary = _load_s7_fetch().fetch(model, job_id, prefix="s12")
    man_path = dest / folder / "manifest.json"
    if not man_path.is_file():
        raise SystemExit(
            f"BLOCKED: no manifest at {man_path}; status.txt says "
            f"{(dest / folder / 'status.txt').read_text().strip() if (dest / folder / 'status.txt').is_file() else '(none)'}")
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    images_dir = man_path.parent / "images"
    job_id = manifest.get("job_id") or job_id
    log_dir = DOCS / "logs" / job_id
    log_dir.mkdir(parents=True, exist_ok=True)

    done = None
    done_path = dest / folder / "DONE.json"
    if done_path.is_file():
        done = json.loads(done_path.read_text(encoding="utf-8"))
        (log_dir / "DONE.json").write_text(json.dumps(done, indent=2) + "\n",
                                          encoding="utf-8")

    revision = manifest.get("model_revision")
    revision_source = "manifest (recorded by the kernel)" if revision else None
    if not revision:
        revision = _resolve_revision(manifest.get("model_id") or "")
        revision_source = "huggingface_hub model_info at collect time"

    peak_alloc = manifest.get("peak_vram_mb")
    peak_reserved = manifest.get("peak_vram_reserved_mb")
    entries = [e for e in manifest.get("images", []) if e.get("file")]
    rows: List[Dict[str, Any]] = []
    for idx, entry in enumerate(entries):
        p = images_dir / entry["file"]
        if not p.is_file():
            raise SystemExit(f"BLOCKED: manifest lists {entry['file']} but the "
                             f"file is missing in {images_dir}")
        m = measure_png(p)
        rows.append({
            "model_id": manifest.get("model_id"),
            "revision": revision or "not_recorded",
            "dtype": manifest.get("dtype"),
            "scheduler": SCHEDULER_LABEL.get(model, "unrecorded"),
            "steps": entry.get("steps"),
            "cfg": entry.get("guidance_scale"),
            "width": m["width"],
            "height": m["height"],
            "seed": entry.get("seed"),
            "scene_id": entry.get("scene_id"),
            "load_time": manifest.get("load_seconds"),
            "warm_render_time": None if idx == 0 else entry.get("seconds"),
            "peak_vram_allocated": peak_alloc,
            "peak_vram_reserved": peak_reserved,
            "black_or_nan_flag": m["black_or_nan"],
            "output_file": entry["file"],
            "model_key": model,
            "render_id": entry.get("render_id"),
            "render_time_s": entry.get("seconds"),
            "mean_pixel": m["mean_pixel"],
            "kernel_black_flag": entry.get("black"),
            "kernel_nonfinite_flag": entry.get("nonfinite"),
            "job_id": job_id,
        })

    warm = [r["warm_render_time"] for r in rows if r["warm_render_time"] is not None]
    black_nan = [r["output_file"] for r in rows if r["black_or_nan_flag"]]
    model_summary = {
        "model_key": model,
        "model_id": manifest.get("model_id"),
        "revision": revision,
        "revision_source": revision_source,
        "job_id": job_id,
        "status": (done or {}).get("status") or manifest.get("status"),
        "done_json": done,
        "pipeline_class": manifest.get("pipeline_class"),
        "dtype": manifest.get("dtype"),
        "scheduler": SCHEDULER_LABEL.get(model),
        "steps": rows[0]["steps"] if rows else None,
        "cfg": rows[0]["cfg"] if rows else None,
        "resolution": [manifest.get("width"), manifest.get("height")],
        "requested": manifest.get("requested"),
        "generated": manifest.get("generated"),
        "verify_verdict": summary.get("verify_verdict"),
        "verify": summary.get("verify"),
        "load_seconds": manifest.get("load_seconds"),
        "median_warm_sec_per_image": (round(statistics.median(warm), 3)
                                      if warm else None),
        "mean_warm_sec_per_image": (round(statistics.mean(warm), 3)
                                    if warm else None),
        "first_image_sec": rows[0]["render_time_s"] if rows else None,
        "gpu_seconds": manifest.get("gpu_seconds"),
        "usable_images_per_minute": manifest.get("usable_images_per_minute"),
        "peak_vram_allocated_mb": peak_alloc,
        "peak_vram_reserved_mb": peak_reserved,
        "black_or_nan_count": len(black_nan),
        "black_or_nan_files": black_nan,
        "kernel_black_count": manifest.get("black_count"),
        "kernel_nonfinite_count": manifest.get("nan_count"),
        "min_mean_pixel": min((r["mean_pixel"] for r in rows), default=None),
        "versions": manifest.get("versions"),
        "install_log_used_stack": (manifest.get("install_log") or {}).get("used_stack"),
        "vae_model_id": manifest.get("vae_model_id"),
        "log_dir": str(log_dir.relative_to(REPO)),
        "images_dir": str(images_dir),
        "csv_rows": len(rows),
        "owner_scoring": "PENDING: anatomy / usable / caption space are the "
                         "owner's blind call (projects/s12_blind/results.csv)",
    }
    (DOCS / f"S12_MODEL_{model}.json").write_text(
        json.dumps(model_summary, indent=2) + "\n", encoding="utf-8")

    _rebuild_csv()
    return model_summary


def load_model_summaries() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for p in sorted(DOCS.glob("S12_MODEL_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[d["model_key"]] = d
    return out


def _rebuild_csv() -> Path:
    """Rebuild the combined CSV from the per-model summaries' image dirs."""
    rows: List[Dict[str, Any]] = []
    for key, summary in load_model_summaries().items():
        images_dir = Path(summary["images_dir"])
        manifest_path = images_dir.parent / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = [e for e in manifest.get("images", []) if e.get("file")]
        for idx, entry in enumerate(entries):
            p = images_dir / entry["file"]
            if not p.is_file():
                continue
            m = measure_png(p)
            rows.append({
                "model_id": summary["model_id"],
                "revision": summary["revision"] or "not_recorded",
                "dtype": summary["dtype"],
                "scheduler": summary["scheduler"],
                "steps": entry.get("steps"),
                "cfg": entry.get("guidance_scale"),
                "width": m["width"],
                "height": m["height"],
                "seed": entry.get("seed"),
                "scene_id": entry.get("scene_id"),
                "load_time": summary["load_seconds"],
                "warm_render_time": "" if idx == 0 else entry.get("seconds"),
                "peak_vram_allocated": summary["peak_vram_allocated_mb"],
                "peak_vram_reserved": summary["peak_vram_reserved_mb"],
                "black_or_nan_flag": m["black_or_nan"],
                "output_file": entry["file"],
                "model_key": key,
                "render_id": entry.get("render_id"),
                "render_time_s": entry.get("seconds"),
                "mean_pixel": m["mean_pixel"],
                "kernel_black_flag": entry.get("black"),
                "kernel_nonfinite_flag": entry.get("nonfinite"),
                "job_id": summary["job_id"],
            })
    rows.sort(key=lambda r: (r["model_key"], str(r["scene_id"]), int(r["seed"] or 0)))
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return CSV_PATH


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--job-id", default=None)
    ap.add_argument("--no-fetch", action="store_true",
                    help="rebuild from an already fetched output folder")
    args = ap.parse_args(argv)
    s = collect(args.model, args.job_id, do_fetch=not args.no_fetch)
    print(json.dumps({k: v for k, v in s.items()
                      if k not in ("verify", "versions", "install_log_used_stack")},
                     indent=2))
    if s["verify_verdict"] not in (None, "PASS"):
        print(f"VERIFY {s['verify_verdict']}", file=sys.stderr)
        return 1
    if s["black_or_nan_count"]:
        print(f"BLACK/NaN: {s['black_or_nan_files']}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
