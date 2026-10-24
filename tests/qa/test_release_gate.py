#!/usr/bin/env python3
"""SINGLE_SOURCE blocking rule + publication gate (L2/L7)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.qa.release_gate import publication_blockers, single_source_sentences  # noqa: E402

LEDGER = (
    "| claim_id | claim | sources | source_type | verification | notes |\n"
    "|---|---|---|---|---|---|\n"
    "| CID-01 | two-source claim | A;B | TWO_SOURCES | ok | n |\n"
    "| CID-02 | one-source claim | A | SINGLE_SOURCE | ok | n |\n"
)

ALL_SIGNOFFS = {"voice": True, "image_model": True, "rights_flags": True,
                "disclosure": True}


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj) if not isinstance(obj, str) else obj,
                 encoding="utf-8")
    return p


def test_mixed_multi_id_sentence_is_flagged(tmp_path):
    ledger = _write(tmp_path, "ledger.md", LEDGER)
    claims = _write(tmp_path, "claims.json", [
        {"claim_id": "CID-01, CID-02", "source_flags": "SINGLE_SOURCE"},
        {"claim_id": "CID-01", "source_flags": ""},
    ])
    flagged = single_source_sentences(claims, ledger)
    assert len(flagged) == 1
    assert flagged[0]["sentence_index"] == 0
    assert "single-source" in flagged[0]["reason"]


def test_unresolved_id_is_a_blocker(tmp_path):
    ledger = _write(tmp_path, "ledger.md", LEDGER)
    claims = _write(tmp_path, "claims.json", [{"claim_id": "GHOST-1"}])
    flagged = single_source_sentences(claims, ledger)
    assert flagged and "unresolved" in flagged[0]["reason"]


def test_publication_refused_on_single_source(tmp_path):
    report = _write(tmp_path, "qa.json", [{"check_id": "ffprobe_streams",
                                           "status": "PASS", "evidence": "ok"}])
    ledger = _write(tmp_path, "ledger.md", LEDGER)
    claims = _write(tmp_path, "claims.json", [{"claim_id": "CID-02"}])
    res = publication_blockers(report, claims, ledger, owner_signoffs=ALL_SIGNOFFS)
    assert res["publishable"] is False
    assert any("single-source" in r for r in res["reasons"])


def test_publication_refused_when_qc_not_run(tmp_path):
    report = _write(tmp_path, "qa.json", [{"check_id": "claim_ids",
                                           "status": "NOT_RUN", "evidence": "no input"}])
    ledger = _write(tmp_path, "ledger.md", LEDGER)
    claims = _write(tmp_path, "claims.json", [{"claim_id": "CID-01"}])
    res = publication_blockers(report, claims, ledger, owner_signoffs=ALL_SIGNOFFS)
    assert res["publishable"] is False
    assert any("NOT_RUN" in r for r in res["reasons"])


def test_publication_refused_without_owner_signoffs(tmp_path):
    report = _write(tmp_path, "qa.json", [{"check_id": "ffprobe_streams",
                                           "status": "PASS", "evidence": "ok"}])
    ledger = _write(tmp_path, "ledger.md", LEDGER)
    claims = _write(tmp_path, "claims.json", [{"claim_id": "CID-01"}])
    res = publication_blockers(report, claims, ledger, owner_signoffs={})
    assert res["publishable"] is False
    assert sum("owner sign-off" in r for r in res["reasons"]) == 4


def test_publication_true_only_when_everything_clears(tmp_path):
    report = _write(tmp_path, "qa.json", [{"check_id": "ffprobe_streams",
                                           "status": "PASS", "evidence": "ok"}])
    ledger = _write(tmp_path, "ledger.md", LEDGER)
    claims = _write(tmp_path, "claims.json", [{"claim_id": "CID-01"}])
    res = publication_blockers(report, claims, ledger, owner_signoffs=ALL_SIGNOFFS)
    assert res["publishable"] is True, res
    assert res["reasons"] == []
