#!/usr/bin/env python3
"""Red-then-green tests for qc.py `ai_illustration_label` check.

A clip with generator=AI must carry the "Illustration" label and stay within
the configured runtime share; otherwise the check FAILS (red). Compliant clips
PASS (green). stdlib + ffmpeg only.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.qa.qc import QCTool  # noqa: E402

TMP = Path("/tmp/kilo_qc_ai")
TMP.mkdir(parents=True, exist_ok=True)


def make_video(path, seconds=10):
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "testsrc=size=160x90:rate=24", "-t", str(seconds),
            "-pix_fmt", "yuv420p", str(path),
        ],
        check=True, capture_output=True,
    )


def edit_decisions(cuts):
    return {"cuts": cuts}


def label_status(report):
    for e in report:
        if e["check_id"] == "ai_illustration_label":
            return e["status"]
    return None


def run_qc(video, cuts, max_share=0.15):
    ed = TMP / "edits.json"
    ed.write_text(json.dumps(edit_decisions(cuts)))
    out = TMP / "report.json"
    res = QCTool().execute({
        "input_path": str(video),
        "output_path": str(out),
        "edit_decisions_path": str(ed),
        "ai_label_max_share": max_share,
    })
    assert res.success, res.error
    report = json.loads(out.read_text())
    return report, label_status(report)


def test_ai_without_label_fails_red(tmp_path):
    video = TMP / "v.mp4"
    make_video(video, 10)
    # AI cut, no label -> red (FAILED)
    report, status = run_qc(
        video, [{"id": "c1", "generator": "AI", "duration": 3.0}]
    )
    assert status == "FAILED", status


def test_ai_with_label_and_small_share_passes_green(tmp_path):
    video = TMP / "v.mp4"
    make_video(video, 10)
    # AI cut, Illustration label, share 0.1 <= 0.15 -> green (PASS)
    report, status = run_qc(
        video, [{"id": "c1", "generator": "AI", "label": "Illustration", "duration": 1.0}]
    )
    assert status == "PASS", status


def test_ai_exceeds_share_fails_red(tmp_path):
    video = TMP / "v.mp4"
    make_video(video, 10)
    # AI cut, Illustration label, but share 0.6 > 0.15 -> red (FAILED)
    report, status = run_qc(
        video, [{"id": "c1", "generator": "AI", "label": "Illustration", "duration": 6.0}]
    )
    assert status == "FAILED", status


def test_no_ai_cuts_passes(tmp_path):
    video = TMP / "v.mp4"
    make_video(video, 10)
    report, status = run_qc(
        video, [{"id": "c1", "generator": "stock", "duration": 5.0}]
    )
    assert status == "PASS", status
