#!/usr/bin/env python3
"""scripts/review_pack.py — independent review harness (M7).

Bundles only read-only report / qa_report / ledger artifacts into a review-pack
directory for a fresh read-only session, and runs all EVALS.md tasks.
No media, no secrets, no publishing, no network.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent

# Read-only artifact patterns to bundle (never media, never secrets).
LEDGER_PATTERNS = ["*_CLAIM_LEDGER.md", "*_CLAIM_IDS.json"]
REPORT_PATTERNS = ["qa_report.json", "*REPORT*.md", "*_REPORT.md"]
STATE_FILES = ["M_STATE.md", "G2_STATE.md"]
AUDIT_DIR = ROOT / "docs/openmontage/audit"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_files(patterns: List[str], roots: List[Path]) -> List[Path]:
    found: List[Path] = []
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for pat in patterns:
            for p in root.rglob(pat):
                if p.is_file() and p not in seen:
                    seen.add(p)
                    found.append(p)
    return sorted(found)


def bundle_review_pack(output_dir: str | Path) -> Dict[str, Any]:
    """Copy read-only report/qa/ledger artifacts into output_dir.

    Bundles: qa_report.json files, claim ledgers/IDs, edit_decisions,
    rights_records, state files, audit reports. Excludes media (.mp4/.wav/.png)
    and any .env/secrets. Returns {ok, files_copied, output_dir, files}.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    roots = [ROOT / "docs", ROOT / "projects", ROOT / "scripts"]
    report_files = _find_files(REPORT_PATTERNS, roots)
    ledger_files = _find_files(LEDGER_PATTERNS, roots)
    state_files = [ROOT / "docs/openmontage" / f for f in STATE_FILES
                   if (ROOT / "docs/openmontage" / f).exists()]
    audit_files = _find_files("*.md", [AUDIT_DIR]) if AUDIT_DIR.exists() else []

    bundle = report_files + ledger_files + state_files + audit_files
    # also include edit_decisions / rights_records wherever they are
    extra = _find_files(["edit_decisions.json", "rights_records.json"], roots)
    bundle += extra

    copied: List[str] = []
    for src in bundle:
        if not src.is_file():
            continue
        if src.suffix.lower() in {".mp4", ".wav", ".png", ".env", ".jsonl"}:
            continue  # never bundle media or secrets
        try:
            data = src.read_bytes()
        except OSError:
            continue
        if len(data) > 5_000_000:
            continue  # skip oversized (possible media)
        rel = src.relative_to(ROOT)
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(str(rel))

    manifest = {
        "created_utc": now_utc(),
        "review_pack": "openmontage_read_only",
        "files_copied": len(copied),
        "files": copied,
    }
    (out / "review_pack_manifest.json").write_text(json.dumps(manifest, indent=2))
    return {"ok": True, "files_copied": len(copied), "output_dir": str(out),
            "files": copied}


EVALS_TEST_FILES = [
    "tests/tools/test_qc_tool.py",
    "tests/tools/test_finish_audio.py",
    "tests/tools/test_piper_tts.py",
    "tests/factory/test_artifact_id_resolution.py",
    "tests/lib/test_footage_classifier.py",
]


def run_evals() -> Dict[str, Any]:
    """Run all EVALS.md tasks via pytest. Returns {ok, tasks, results}."""
    results: Dict[str, Any] = {}
    tasks = 0
    all_ok = True
    for rel in EVALS_TEST_FILES:
        path = ROOT / rel
        if not path.exists():
            results[rel] = {"skipped": True, "reason": "not found"}
            all_ok = False
            continue
        tasks += 1
        res = subprocess.run(
            [sys.executable, "-m", "pytest", str(path), "-q"],
            capture_output=True, text=True,
        )
        ok = res.returncode == 0
        all_ok = all_ok and ok
        results[rel] = {"passed": ok, "exit_code": res.returncode,
                        "stdout_tail": res.stdout.strip().splitlines()[-3:],
                        "stderr_tail": res.stderr.strip().splitlines()[-3:]}
    return {"ok": all_ok, "tasks": tasks, "results": results}
