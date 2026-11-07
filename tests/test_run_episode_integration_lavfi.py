#!/usr/bin/env python3
"""Offline integration test: synthetic lavfi clip -> real QC stage.

Builds a tiny H.264/AAC MP4 with ffmpeg lavfi (no network, no external
media), feeds the real `cmd_qc` with a complete artifact set, and asserts the
QC report is produced. A synthetic test card must never come out PASS —
that is the fail-closed property this test exists to protect.

Skipped when ffmpeg/ffprobe are not installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import run_episode  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe not installed",
)

DUR = 3.0


def _lipsum(n=12):
    return "speculative ocean creatures drift beneath the ice shelf while " * n


def _make_clip(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=30:duration={DUR}",
        "-f", "lavfi", "-i", f"sine=frequency=300:duration={DUR}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-shortest", str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-500:]
    return out


def _write_inputs(ep: Path) -> dict:
    art = ep / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    clip = _make_clip(ep / "renders" / "final_t_ep_draft.mp4")

    (art / "narration_manifest.json").write_text(json.dumps({
        "expected_duration": DUR, "tolerance": 0.5,
        "segments": [{"text": "Synthetic narration.", "start": 0.0, "end": DUR}],
    }), encoding="utf-8")

    srt = [
        "1", "00:00:00,000 --> 00:00:01,400", "A speculative ocean drifts.", "",
        "2", "00:00:01,500 --> 00:00:02,900", "Ice above, life below.", "",
    ]
    (ep / "subtitles.srt").write_text("\n".join(srt), encoding="utf-8")

    (art / "credits.txt").write_text(
        "Illustrations: AI-generated (Speculative illustration)\n"
        "Footage: none\n", encoding="utf-8")

    (art / "claim_ids.json").write_text(json.dumps([
        {"sentence": "A speculative ocean drifts.", "claim_id": "T-01"},
        {"sentence": "Ice above, life below.", "claim_id": "T-02"},
    ]), encoding="utf-8")
    (art / "claim_ledger.md").write_text(
        "| claim_id | paraphrase | source | source_type | note |\n"
        "| T-01 | x | https://example.org/a | TWO_SOURCES | ok |\n"
        "| T-02 | y | https://example.org/b | TWO_SOURCES | ok |\n",
        encoding="utf-8")

    import hashlib
    sha = hashlib.sha256(clip.read_bytes()).hexdigest()
    (art / "rights_records.json").write_text(json.dumps([{
        "asset_id": "clip-1", "kind": "video",
        "source_url": "https://example.org/clip.mp4",
        "credit": "OpenMontage synthetic test card",
        "license": "public domain (synthetic)", "rights_basis": "source_policy_us_gov",
        "sha256": sha,
    }]), encoding="utf-8")

    (ep / "edit_decisions.json").write_text(json.dumps({
        "episode_id": "t_ep", "duration": DUR,
        "cuts": [{
            "id": "c1", "generator": "AI", "label": "Speculative illustration",
            "description": "Synthetic test card.", "duration": DUR,
            "source_start": 0.0, "source_end": DUR,
            "motion": {"move": "pan", "easing": "easeinout", "direction": "left"},
            "claim_id": "T-01", "rationale": "integration fixture",
        }],
    }), encoding="utf-8")
    return {"clip": clip, "artifacts": art}


def test_qc_stage_runs_on_synthetic_clip_and_never_passes(tmp_path):
    ep = tmp_path / "ep"
    paths = _write_inputs(ep)
    state = {
        "episode_dir": str(ep),
        "edl_path": str(ep / "edit_decisions.json"),
        "claim_ids_path": str(paths["artifacts"] / "claim_ids.json"),
        "claim_ledger_path": str(paths["artifacts"] / "claim_ledger.md"),
        "qa_report_path": str(paths["artifacts"] / "qa_report.json"),
    }
    res = run_episode.cmd_qc("t_ep", state)
    assert res["status"] == "OK", res
    report = json.loads((paths["artifacts"] / "qa_report.json").read_text())
    assert isinstance(report, list) and len(report) >= 8
    ids = {e["check_id"] for e in report}
    for required in ("ffprobe_streams", "full_decode", "blackdetect",
                     "freezedetect", "silencedetect", "duration_vs_script",
                     "subtitle_sync", "claim_ids", "claim_ids_resolve",
                     "rights_basis", "credits_complete", "added_value"):
        assert required in ids, f"{required} missing from QC report"
    # A 640x360 synthetic test card must not be releasable: at least one check
    # is FAILED/REVIEW/NOT_RUN/BLOCKED and the overall verdict is not PASS.
    assert any(e["status"] in ("FAILED", "REVIEW", "NOT_RUN", "BLOCKED")
               for e in report)
    assert res["outputs"]["verdict"] != "PASS"
