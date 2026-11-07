#!/usr/bin/env python3
"""S7-7 helper: stage a pack root from the cached images + committed manifests.

The Kaggle kernel keeps only the output of its LATEST version, and the
sandbox's /tmp can be wiped at any time, so the fetched PNGs are mirrored
into the gitignored `output/s7_cache/<model>/` and the text manifests are
committed under `docs/openmontage/image_gen/logs/<job_id>/`.

This script rebuilds the `s7_bakeoff_<model>/{manifest.json,images/}` layout
that scripts/s7_checks.py and scripts/s7_blind_pack.py expect, and verifies
every image against the sha256 in the kernel manifest (fail closed: a
mismatch is an error, never a silent pass).

Usage:
  python scripts/s7_stage_pack_root.py --cache-root output/s7_cache \
      --logs-root docs/openmontage/image_gen/logs \
      --out output/s7_pack_root
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
MODELS = ["sdxl", "klein", "zimage"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def newest_manifest(logs_root: Path, model: str) -> Path:
    cands = sorted(logs_root.glob(f"s7-{model}-*/manifest.json"))
    if not cands:
        raise SystemExit(f"BLOCKED: no manifest for model {model} under {logs_root}")
    return cands[-1]


def stage_model(model: str, cache_root: Path, logs_root: Path,
                out_root: Path) -> Dict[str, Any]:
    man_path = newest_manifest(logs_root, model)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    src_img_dir = cache_root / model
    if not src_img_dir.is_dir():
        raise SystemExit(f"BLOCKED: no cached images for {model} at {src_img_dir}")

    dest = out_root / f"s7_bakeoff_{model}"
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "images").mkdir(parents=True, exist_ok=True)
    shutil.copy2(man_path, dest / "manifest.json")

    verified, failed = 0, []
    for entry in man.get("images", []):
        name = entry.get("file")
        if not name:
            continue
        src = src_img_dir / name
        if not src.is_file():
            failed.append(f"{model}:{name} missing from cache")
            continue
        digest = sha256(src)
        if digest != entry.get("sha256"):
            failed.append(f"{model}:{name} sha256 mismatch")
            continue
        shutil.copy2(src, dest / "images" / name)
        verified += 1
    if failed:
        raise SystemExit("BLOCKED: " + "; ".join(failed))
    return {"model": model, "job_id": man.get("job_id"),
            "manifest": _display(man_path),
            "images_verified": verified}


def _display(path: Path) -> str:
    """Repo-relative path when possible, absolute otherwise."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-root", default=str(REPO / "output/s7_cache"))
    ap.add_argument("--logs-root", default=str(
        REPO / "docs/openmontage/image_gen/logs"))
    ap.add_argument("--out", default=str(REPO / "output/s7_pack_root"))
    ap.add_argument("--models", default=",".join(MODELS))
    args = ap.parse_args(argv)

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    summary = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        summary.append(stage_model(model, Path(args.cache_root),
                                   Path(args.logs_root), out_root))
    for s in summary:
        print(f"{s['model']}: {s['images_verified']} images verified "
              f"(job {s['job_id']}, manifest {s['manifest']})")
    print(f"pack root: {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
