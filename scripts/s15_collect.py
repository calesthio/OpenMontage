#!/usr/bin/env python3
"""S15: fetch the style-lock kernel output, verify it, stage the text record.

Downloads the Kaggle output for the S15 job into /tmp/kilo/s15_out/, runs the
bridge `verify` (sha256 + byte count fail-closed against the kernel manifest),
and copies the TEXT artefacts (manifest, status, install log, wide-style
decision, tracebacks) into docs/openmontage/image_gen/logs/<job_id>/ so the
committed record keeps a stable path. PNGs stay in /tmp — media is never
committed.

Run the moment `kaggle kernels status` leaves RUNNING:

  python scripts/s15_collect.py --job-id s15-style-lock-1

Then:
  python scripts/s15_assemble.py --manifest <path printed above>
  python scripts/s15_checks.py   --manifest <same>
  python scripts/s15_blind_pack.py --manifest <same>
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool  # noqa: E402

KERNEL_SLUG = "forts845/of-bridge-runner"
OUT_ROOT = Path("/tmp/kilo/s15_out")
LOGS_DIR = REPO / "docs/openmontage/image_gen/logs"
FOLDER = "s15_style_lock_dreamshaper-xl-1-0"
TEXT_FILES = ("manifest.json", "status.txt", "install_log.json",
              "wide_style.json", "DONE.json")


def fetch(job_id: str) -> Dict[str, Any]:
    dest = OUT_ROOT
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    bridge = KaggleBridgeTool()
    fo = bridge.execute({
        "command": "fetch_output",
        "kernel_slug": KERNEL_SLUG,
        "dest": str(dest),
        "file_pattern": "*",
        "kaggle_cmd": "kaggle",
    })
    if not fo.success:
        raise SystemExit(f"FETCH FAILED: {fo.error}")

    man_path = dest / FOLDER / "manifest.json"
    if not man_path.is_file():
        # Kaggle sometimes nests the output zip one level deeper
        found = sorted(dest.rglob("manifest.json"))
        if not found:
            raise SystemExit(
                f"NO MANIFEST. Files fetched: "
                f"{sorted(p.name for p in dest.rglob('*'))[:40]}")
        man_path = found[0]

    status_path = man_path.parent / "status.txt"
    status = status_path.read_text(encoding="utf-8").strip() \
        if status_path.is_file() else ""
    manifest = json.loads(man_path.read_text(encoding="utf-8"))

    # verify: flat stage (manifest + images side by side), never mutate kernel files
    stage = dest / "_verify_stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(man_path, stage / "manifest.json")
    images = list((man_path.parent / "images").glob("*.png"))
    for png in images:
        shutil.copy2(png, stage / png.name)
    vr = bridge.execute({
        "command": "verify",
        "output_folder": str(stage),
        "job_id": manifest.get("job_id") or job_id,
        "kaggle_cmd": "kaggle",
    })
    verify = (vr.data or {}).get("verify", {})
    verdict = (vr.data or {}).get("verdict", "REJECT")

    log_dir = LOGS_DIR / job_id
    log_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in TEXT_FILES:
        for candidate in (man_path.parent / name, dest / name):
            if candidate.is_file():
                shutil.copy2(candidate, log_dir / name)
                written.append(name)
                break
    for tb in sorted(man_path.parent.glob("traceback_*.txt")):
        shutil.copy2(tb, log_dir / tb.name)
        written.append(tb.name)

    summary = {
        "job_id": manifest.get("job_id"),
        "verdict": verdict,
        "verify": verify,
        "status_txt": status,
        "images_on_disk": len(images),
        "generated": manifest.get("generated"),
        "total_requested": manifest.get("total_requested"),
        "black_count": manifest.get("black_count"),
        "nan_count": manifest.get("nan_count"),
        "oom_count": manifest.get("oom_count"),
        "load_seconds": manifest.get("load_seconds"),
        "peak_vram_mb": manifest.get("peak_vram_mb"),
        "log_dir": str(log_dir),
        "text_files": written,
        "manifest": str(man_path),
        "images_dir": str(man_path.parent / "images"),
    }
    (log_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n",
                                          encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job-id", default="s15-style-lock-1")
    args = ap.parse_args(argv)
    summary = fetch(args.job_id)
    return 0 if summary["verdict"] == "PASS" else 3


if __name__ == "__main__":
    sys.exit(main())
