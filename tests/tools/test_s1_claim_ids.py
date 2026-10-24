#!/usr/bin/env python3
"""TDD test: S1 speculative-evolution claim_ids resolve check.

Uses the real claim ledger (docs/openmontage/evidence/S1_SPECULATIVE_CLAIM_LEDGER.md)
and claim_ids JSON (docs/openmontage/slice/speculative_evolution/CLAIM_IDS.json).
Every claim_id must resolve to the ledger; SPECULATION claims carry a flag.
Generates a throwaway ffmpeg fixture (no media committed).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.qa.qc import QCTool  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
LEDGER = REPO / "docs" / "openmontage" / "evidence" / "S1_SPECULATIVE_CLAIM_LEDGER.md"
CLAIM_IDS = REPO / "docs" / "openmontage" / "slice" / "speculative_evolution" / "CLAIM_IDS.json"


def _gen_video(path, duration=5):
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "testsrc=size=1920x1080:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac", str(path),
        ],
        capture_output=True, text=True, timeout=120,
    )
    assert path.exists() and path.stat().st_size > 0


def test_s1_claim_ids_resolve_pass(tmp_path):
    vid = tmp_path / "good.mp4"
    _gen_video(vid)
    qc = QCTool()
    out = tmp_path / "qa_report.json"
    res = qc.execute({
        "input_path": str(vid),
        "output_path": str(out),
        "claim_ids_path": str(CLAIM_IDS),
        "claim_ledger_path": str(LEDGER),
    })
    assert res.success, res.error
    report = json.loads(out.read_text())
    by_id = {e["check_id"]: e for e in report}
    assert by_id["claim_ids"]["status"] == "PASS", by_id["claim_ids"]
    assert by_id["claim_ids_resolve"]["status"] == "PASS", by_id["claim_ids_resolve"]
