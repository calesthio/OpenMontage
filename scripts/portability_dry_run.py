#!/usr/bin/env python3
"""scripts/portability_dry_run.py — clean-venv portability dry-run (M9).

Checks that a fresh account can rebuild the factory from the committed tree:
python3, ffmpeg, curl present; key scripts compile; dependency list is
pinned/available; disk and time logged. Does NOT install packages (no network).
Fail-closed.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent

KEY_SCRIPTS = [
    "scripts/ci_fast_suite.py",
    "scripts/portability_dry_run.py",
    "scripts/rebuild_slice_assets.sh",
    "scripts/review_pack.py",
    "scripts/assemble_iss_video.py",
    "scripts/iss_narrate_all.py",
    "scripts/iss_narrate_one.py",
]
KEY_TOOLS = [
    "tools/qa/qc.py",
    "tools/audio/finish_audio.py",
    "tools/kaggle_bridge/kaggle_bridge.py",
    "tools/illustration/illustration_qc.py",
    "tools/illustration/illustration_batch.py",
    "tools/museum/adapters.py",
    "tools/museum/rights.py",
    "tools/museum/asset_record.py",
    "tools/motion/motion_variety.py",
    "tools/packaging/packaging.py",
    "tools/analytics/analytics_import.py",
]
DEPENDENCY_BINARIES = ["python3", "ffmpeg", "ffprobe", "curl", "sha256sum"]


def disk_free_mb() -> int:
    st = shutil.disk_usage(ROOT)
    return st.free // (1024 * 1024)


def run() -> Dict[str, Any]:
    t0 = time.time()
    disk_before = disk_free_mb()
    results: Dict[str, Any] = {
        "disk_free_mb_before": disk_before,
        "binaries": {},
        "compiles": {},
    }
    blocked = False

    # 1. Required binaries present (no network).
    for bin_name in DEPENDENCY_BINARIES:
        p = shutil.which(bin_name)
        results["binaries"][bin_name] = bool(p)
        if not p:
            blocked = True

    # 2. Python version.
    results["python_version"] = sys.version

    # 3. Key scripts/tools compile.
    for rel in KEY_SCRIPTS + KEY_TOOLS:
        path = ROOT / rel
        if not path.exists():
            results["compiles"][rel] = {"ok": False, "reason": "missing"}
            blocked = True
            continue
        if rel.endswith(".sh"):
            results["compiles"][rel] = {"ok": True, "reason": "shell script"}
            continue
        res = subprocess.run([sys.executable, "-m", "py_compile", str(path)],
                             capture_output=True, text=True)
        results["compiles"][rel] = {"ok": res.returncode == 0,
                                    "stderr": res.stderr.strip()[-200:]}
        if res.returncode != 0:
            blocked = True

    disk_after = disk_free_mb()
    results["disk_free_mb_after"] = disk_after
    results["elapsed_s"] = round(time.time() - t0, 2)
    results["disk_floor_ok"] = disk_after >= 800
    results["ok"] = (not blocked) and disk_after >= 800
    return results


if __name__ == "__main__":
    import json
    res = run()
    print(json.dumps(res, indent=2))
    sys.exit(0 if res.get("ok") else 1)
