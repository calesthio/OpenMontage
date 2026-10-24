#!/usr/bin/env python3
"""S7-3..5: fetch ONE model's kernel output and verify it through the bridge.

Downloads the Kaggle kernel output for the last pushed model into
/tmp/kilo/s7_out/<model>/ and runs the bridge `verify` command, which
recomputes every image sha256 and byte count against the kernel manifest
(fail-closed: a mismatch is a REJECT, never a pass).

Text artefacts (status.txt, manifest.json, tracebacks, install_log.json) are
copied into docs/openmontage/image_gen/logs/ so the committed record keeps a
stable path for the traceback; the PNGs stay in /tmp (media is never
committed).

Usage: python scripts/s7_fetch.py {sdxl|klein|zimage} [--job-id s7-sdxl-1]
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

KERNEL_SLUG = "forts845/openmontage-runner"
OUT_ROOT = Path("/tmp/kilo/s7_out")
LOGS_DIR = REPO / "docs/openmontage/image_gen/logs"


def fetch(model: str, job_id: Optional[str] = None) -> Dict[str, Any]:
    dest = OUT_ROOT / model
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
        raise SystemExit(f"FETCH FAILED ({model}): {fo.error}")

    man_path = dest / f"s7_bakeoff_{model}" / "manifest.json"
    status_path = dest / f"s7_bakeoff_{model}" / "status.txt"
    status = status_path.read_text(encoding="utf-8").strip() if status_path.is_file() else ""
    if not man_path.is_file():
        raise SystemExit(
            f"NO MANIFEST for {model}. status.txt says: {status or '(none)'}. "
            f"Files fetched: {sorted(p.name for p in dest.iterdir())}")

    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    # The bridge's verify resolves each manifest image path relative to the
    # folder that holds manifest.json, but the runner writes the images into
    # an `images/` sub-folder. Stage a flat copy (manifest + images side by
    # side) so the bridge verifies the real bytes without touching the
    # kernel artefact.
    stage = dest / "_verify_stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(man_path, stage / "manifest.json")
    for png in (man_path.parent / "images").glob("*.png"):
        shutil.copy2(png, stage / png.name)

    vr = bridge.execute({
        "command": "verify",
        "output_folder": str(stage),
        "job_id": manifest.get("job_id") or job_id,
        "kaggle_cmd": "kaggle",
    })
    verify = vr.data.get("verify", {}) if vr.data else {}
    verdict = vr.data.get("verdict") if vr.data else "REJECT"

    # committed text record (no media)
    log_dir = LOGS_DIR / f"{manifest.get('job_id', model)}"
    log_dir.mkdir(parents=True, exist_ok=True)
    for name in ("status.txt", "manifest.json", "install_log.json"):
        src = man_path.parent / name
        if src.is_file():
            shutil.copy2(src, log_dir / name)
    for tb in man_path.parent.glob("traceback*.txt"):
        shutil.copy2(tb, log_dir / tb.name)
    for log in dest.glob("*.log"):
        shutil.copy2(log, log_dir / "kernel.log")

    summary = {
        "model": model,
        "job_id": manifest.get("job_id"),
        "status": status,
        "verify_verdict": verdict,
        "verify": verify,
        "generated": manifest.get("generated"),
        "requested": manifest.get("requested"),
        "load_seconds": manifest.get("load_seconds"),
        "steady_state_sec_per_image": manifest.get("steady_state_sec_per_image"),
        "usable_images_per_minute": manifest.get("usable_images_per_minute"),
        "peak_vram_mb": manifest.get("peak_vram_mb"),
        "black_count": manifest.get("black_count"),
        "nan_count": manifest.get("nan_count"),
        "oom_count": manifest.get("oom_count"),
        "pipeline_class": manifest.get("pipeline_class"),
        "versions": manifest.get("versions"),
        "install_log": manifest.get("install_log"),
        "log_dir": str(log_dir.relative_to(REPO)),
        "images_dir": str((man_path.parent / "images")),
    }
    (log_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n",
                                          encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model", choices=["sdxl", "klein", "zimage"])
    ap.add_argument("--job-id", default=None)
    args = ap.parse_args()
    s = fetch(args.model, args.job_id)
    print(json.dumps({k: v for k, v in s.items() if k != "install_log"}, indent=2))
    if s["verify_verdict"] != "PASS":
        print(f"VERIFY {s['verify_verdict']} — see {s['log_dir']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
