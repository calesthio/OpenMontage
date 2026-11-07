#!/usr/bin/env python3
"""scripts/run_evals.py — executable EVALS.md fixed tasks (L10).

Runs the six fixed tasks from docs/agent-improvement/EVALS.md against the
current code and prints one PASS/FAIL line per task plus a JSON summary.

Rules:
- No network, no paid routes, no secrets.
- A task that cannot run is FAILED (never PASS).
- Exit code 0 only when every task passes.

Usage: python scripts/run_evals.py [--json-out PATH]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.footage_classifier import classify_footage  # noqa: E402
from tools.qa.qc import QCTool, _parse_ebur128  # noqa: E402


def _ffmpeg(args, timeout=120):
    return subprocess.run(["ffmpeg", "-hide_banner", "-y"] + args,
                          capture_output=True, text=True, timeout=timeout)


def _probe_report(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _check(report, check_id):
    for e in report:
        if e["check_id"] == check_id:
            return e
    return None


def _run_qc(inputs: dict, out: Path):
    res = QCTool().execute(inputs)
    report = _probe_report(out) if out.is_file() else []
    return report, res


# --------------------------------------------------------------------- E1
def eval_e1_corrupt_mp4(tmp: Path):
    bad = tmp / "corrupt.mp4"
    bad.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"garbage" * 50)
    out = tmp / "e1.json"
    report, res = _run_qc({"input_path": str(bad), "output_path": str(out)}, out)
    bad_statuses = [e["status"] for e in report if e["status"] in ("FAILED", "BLOCKED")]
    verdict = (res.data or {}).get("verdict") if hasattr(res, "data") else None
    ok = bool(bad_statuses) and verdict != "PASS"
    return ok, f"verdict={verdict}; failed/blocked checks={len(bad_statuses)}"


# --------------------------------------------------------------------- E2
def eval_e2_loudness(tmp: Path):
    src = tmp / "clipped.wav"
    out = tmp / "finished.wav"
    _ffmpeg(["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=8",
             "-af", "volume=12dB,alimiter=limit=0.99", "-ac", "2", str(src)])
    from tools.audio.finish_audio import FinishAudioTool
    res = FinishAudioTool().execute({"input_path": str(src), "output_path": str(out)})
    if not getattr(res, "success", False) or not out.is_file():
        return False, f"finish_audio failed: {getattr(res, 'error', 'no output')}"
    eb = _ffmpeg(["-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"])
    parsed = _parse_ebur128(eb.stderr)
    i, tp = parsed["integrated_lufs"], parsed["true_peak"]
    ok = i is not None and abs(i - (-14.0)) <= 2.0 and tp is not None and tp <= -1.5
    return ok, f"I={i} LUFS, TP={tp} dBTP (target -14+/-2, TP<=-1.5)"


# --------------------------------------------------------------------- E3
def eval_e3_piper_refused(_tmp: Path):
    from tools.audio.tts_kaggle import KokoroTTSTool
    out = Path(tempfile.mkdtemp(prefix="eval3_")) / "piper.wav"
    res = KokoroTTSTool().execute({
        "text": "This must never be synthesized with Piper lessac.",
        "job_id": "eval-e3",
        "output_path": str(out),
        "engine": "piper_en_US-lessac-medium",
    })
    data = res.get("data", {}) if isinstance(res, dict) else getattr(res, "data", {})
    verdict = data.get("verdict")
    ok = verdict == "REJECT" and not out.exists()
    return ok, f"verdict={verdict}; reason={data.get('reason')}; file_written={out.exists()}"


# --------------------------------------------------------------------- E4
def eval_e4_unknown_claim_id(tmp: Path):
    video = tmp / "v.mp4"
    _ffmpeg(["-f", "lavfi", "-i", "testsrc=size=160x90:rate=24", "-t", "3",
             "-pix_fmt", "yuv420p", str(video)])
    claims = tmp / "claims.json"
    claims.write_text(json.dumps([{"text": "Invented fact.", "claim_id": "GHOST-99",
                                   "source_flags": "SINGLE_SOURCE"}]))
    ledger = tmp / "ledger.md"
    ledger.write_text(
        "| claim_id | claim | sources | source_type | verification | notes |\n"
        "|---|---|---|---|---|---|\n"
        "| CID-01 | known | FS | TWO_SOURCES | ok | n |\n")
    out = tmp / "e4.json"
    report, _ = _run_qc({
        "input_path": str(video), "output_path": str(out),
        "claim_ids_path": str(claims), "claim_ledger_path": str(ledger),
        "expected_width": 160, "expected_height": 90, "expected_fps": 24,
    }, out)
    entry = _check(report, "claim_ids_resolve")
    ok = entry is not None and entry["status"] == "FAILED" and "GHOST-99" in entry["evidence"]
    return ok, f"claim_ids_resolve={entry['status'] if entry else None}"


# --------------------------------------------------------------------- E5
def eval_e5_third_party_credit(_tmp: Path):
    res = classify_footage({"rights_basis": "source_policy_us_gov",
                            "third_party_credit": True})
    ok = res["rights_basis"] == "unknown" and res["usable"] is False
    return ok, f"rights_basis={res['rights_basis']}, usable={res['usable']}"


# --------------------------------------------------------------------- E6
def eval_e6_rebuild_hash_mismatch(tmp: Path):
    src = tmp / "asset.bin"
    src.write_bytes(b"real asset bytes")
    manifest = tmp / "manifest.json"
    manifest.write_text(json.dumps({"assets": [{
        "download_url": src.as_uri(),
        "file_name": "asset.bin",
        "sha256": "0" * 64,
        "role": "still_primary",
    }]}))
    assets = tmp / "assets"
    res = subprocess.run(
        ["bash", str(ROOT / "scripts/rebuild_slice_assets.sh"), str(assets)],
        capture_output=True, text=True, env={**__import__("os").environ,
                                             "MANIFEST": str(manifest)},
        timeout=180,
    )
    text = (res.stdout or "") + (res.stderr or "")
    ok = res.returncode != 0 and "sha256 mismatch" in text.lower()
    return ok, f"exit={res.returncode}; mismatch_reported={'sha256 mismatch' in text.lower()}"


EVALS = [
    ("E1", "qc fails a corrupt MP4", eval_e1_corrupt_mp4),
    ("E2", "finish_audio hits loudness + true peak", eval_e2_loudness),
    ("E3", "TTS refuses Piper lessac", eval_e3_piper_refused),
    ("E4", "claim_ids fails on an unknown id", eval_e4_unknown_claim_id),
    ("E5", "third-party credit classifies REJECT", eval_e5_third_party_credit),
    ("E6", "rebuild script fails on hash mismatch", eval_e6_rebuild_hash_mismatch),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json-out", default=str(ROOT / "docs/openmontage/audit/EVALS_RESULT.json"))
    args = ap.parse_args(argv)

    results = []
    all_ok = True
    for eid, name, fn in EVALS:
        t0 = time.time()
        tmp = Path(tempfile.mkdtemp(prefix=f"eval_{eid}_", dir="/tmp"))
        try:
            ok, detail = fn(tmp)
        except Exception as exc:  # fail-closed: a crashed eval is FAILED
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        elapsed = round(time.time() - t0, 2)
        results.append({"id": eid, "task": name, "status": "PASS" if ok else "FAILED",
                        "detail": detail, "elapsed_s": elapsed})
        print(f"{eid} {'PASS' if ok else 'FAILED'}  {name}  ({detail}) [{elapsed}s]")
        all_ok = all_ok and ok
        shutil.rmtree(tmp, ignore_errors=True)

    payload = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "all_passed": all_ok, "results": results}
    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\noverall: {'PASS' if all_ok else 'FAILED'} ({sum(1 for r in results if r['status']=='PASS')}/{len(results)})")
    print(f"report: {out}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
