#!/usr/bin/env python3
"""scripts/ci_fast_suite.py — CI-style fast test suite (M9).

Runs the fast, media-free test subset and reports pass/fail, exit codes,
elapsed time, and disk free before/after. Fail-closed: nonzero => BLOCKED.
No network, no paid routes.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent

FAST_TEST_FILES = [
    "tests/tools/test_qc_tool.py",
    "tests/tools/test_finish_audio.py",
    "tests/tools/test_illustration_qc.py",
    "tests/tools/test_illustration_batch.py",
    "tests/tools/test_museum_adapters.py",
    "tests/tools/test_motion_variety.py",
    "tests/tools/test_packaging.py",
    "tests/tools/test_analytics_import.py",
    "tests/lib/test_footage_classifier.py",
    "tests/factory/test_artifact_id_resolution.py",
]


def disk_free_mb() -> int:
    st = shutil.disk_usage(ROOT)
    return st.free // (1024 * 1024)


def run() -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    t0 = time.time()
    disk_before = disk_free_mb()
    results["disk_free_mb_before"] = disk_before
    if disk_before < 800:
        results["blocked"] = True
        results["error"] = f"disk {disk_before} MB < 800 MB floor"
        return results

    all_ok = True
    n_run = 0
    n_pass = 0
    for rel in FAST_TEST_FILES:
        path = ROOT / rel
        if not path.exists():
            results[rel] = {"skipped": True, "reason": "not found"}
            continue
        n_run += 1
        st = time.time()
        res = subprocess.run(
            [sys.executable, "-m", "pytest", str(rel), "-q"],
            cwd=ROOT, capture_output=True, text=True,
        )
        elapsed = time.time() - st
        ok = res.returncode == 0
        all_ok = all_ok and ok
        if ok:
            n_pass += 1
        results[rel] = {"passed": ok, "exit_code": res.returncode,
                        "elapsed_s": round(elapsed, 2),
                        "stdout_tail": res.stdout.strip().splitlines()[-2:]}

    disk_after = disk_free_mb()
    results["disk_free_mb_after"] = disk_after
    results["elapsed_s"] = round(time.time() - t0, 2)
    results["tests_run"] = n_run
    results["tests_passed"] = n_pass
    results["all_passed"] = all_ok
    results["ok"] = all_ok and disk_after >= 800
    return results


if __name__ == "__main__":
    import json
    res = run()
    print(json.dumps(res, indent=2))
    sys.exit(0 if res.get("ok") else 1)
