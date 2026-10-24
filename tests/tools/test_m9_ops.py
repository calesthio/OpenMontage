#!/usr/bin/env python3
"""Red-then-green smoke tests for M9 ops scripts."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.ci_fast_suite import disk_free_mb, run as ci_run  # noqa: E402
from scripts.portability_dry_run import run as dry_run  # noqa: E402


def test_disk_floor():
    assert disk_free_mb() >= 800


def test_ci_fast_suite_runs():
    res = ci_run()
    assert res["ok"] is True
    assert res["tests_run"] > 0
    assert res["disk_free_mb_before"] >= 800
    assert res["disk_free_mb_after"] >= 800


def test_portability_dry_run():
    res = dry_run()
    assert res["ok"] is True
    assert res["disk_floor_ok"] is True
    assert all(res["binaries"].values())  # python3, ffmpeg, ffprobe, curl, sha256sum
    assert all(v["ok"] for v in res["compiles"].values())
