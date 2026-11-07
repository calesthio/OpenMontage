#!/usr/bin/env python3
"""Red-then-green tests for scripts/review_pack.py (M7).

Offline: copies only read-only report/qa/ledger artifacts into a review pack
directory; never media, never secrets. Runs EVALS.md tasks via pytest.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.review_pack import bundle_review_pack, run_evals  # noqa: E402

TMP = Path("/tmp/kilo_review_pack")
TMP.mkdir(parents=True, exist_ok=True)


def test_bundle_contains_qa_report_and_ledger():
    out = TMP / "pack1"
    res = bundle_review_pack(out)
    assert res["ok"] is True
    files = [p.name for p in Path(out).rglob("*") if p.is_file()]
    assert any("qa_report" in f for f in files), files
    assert any("CLAIM_LEDGER" in f or "CLAIM_IDS" in f for f in files), files
    # read-only: no media, no secrets
    assert not any(f.endswith((".mp4", ".wav", ".png", ".env")) for f in files), files


def test_bundle_is_read_only_no_media():
    out = TMP / "pack2"
    bundle_review_pack(out)
    for f in Path(out).rglob("*"):
        if f.is_file():
            assert f.stat().st_size < 5_000_000, f  # no large media


def test_run_evals_returns_results():
    res = run_evals()
    assert res["ok"] is True
    assert "tasks" in res
    assert res["tasks"] >= 5  # E1..E5
