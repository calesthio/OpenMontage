#!/usr/bin/env python3
"""tools/qa/release_gate.py — publication blocker computation (L2/L7/L9).

A draft is NEVER publishable by an agent. This module only computes the exact
list of reasons a human must clear. Fail-closed: a missing input is a blocker.

Inputs are file paths so the gate can run read-only from a review pack.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from tools.qa.qc import _parse_claim_ledger

REQUIRED_OWNER_SIGNOFFS = (
    "voice",
    "image_model",
    "rights_flags",
    "disclosure",
)


def _load(path: str | Path | None):
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def single_source_sentences(claim_ids_path, ledger_path) -> List[Dict[str, Any]]:
    """Sentences citing at least one SINGLE_SOURCE / UNVERIFIED claim.

    A sentence may cite several ids; it is flagged when ANY cited claim is
    single-source (SCR-06). Unresolved ids are returned too — they are a
    harder blocker, never silently dropped.
    """
    data = _load(claim_ids_path)
    ledger = _parse_claim_ledger(str(ledger_path)) if ledger_path else {}
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(data):
        raw = str(row.get("claim_id") or "")
        parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
        if not parts:
            out.append({"sentence_index": i, "claim_id": "", "reason": "missing claim_id"})
            continue
        unknown = [p for p in parts if p not in ledger]
        if unknown:
            out.append({"sentence_index": i, "claim_id": raw,
                        "reason": f"unresolved: {', '.join(unknown)}"})
            continue
        singles = [p for p in parts if "SINGLE" in ledger[p].upper()
                   or "UNVERIFIED" in ledger[p].upper()]
        if singles:
            out.append({"sentence_index": i, "claim_id": raw,
                        "reason": f"single-source: {', '.join(singles)}"})
    return out


def publication_blockers(
    qa_report_path=None,
    claim_ids_path=None,
    claim_ledger_path=None,
    owner_signoffs: Dict[str, bool] | None = None,
    extra: List[str] | None = None,
) -> Dict[str, Any]:
    """Return {"publishable": bool, "reasons": [...]} for a draft episode.

    `owner_signoffs` keys come from REQUIRED_OWNER_SIGNOFFS. Absent or false
    sign-offs are blockers (OWNER_GATED), never assumed.
    """
    reasons: List[str] = []

    report = _load(qa_report_path)
    if not isinstance(report, list) or not report:
        reasons.append("QC report missing or unreadable")
    else:
        statuses = [e.get("status") for e in report if isinstance(e, dict)]
        bad = [e for e in report if isinstance(e, dict)
               and e.get("status") in ("FAILED", "BLOCKED")]
        not_run = [e for e in report if isinstance(e, dict)
                   and e.get("status") == "NOT_RUN"]
        if bad:
            reasons.append("QC has FAILED/BLOCKED checks: "
                           + ", ".join(str(e.get("check_id")) for e in bad))
        if not_run:
            reasons.append("QC has NOT_RUN checks (cannot be treated as passed): "
                           + ", ".join(str(e.get("check_id")) for e in not_run))
        if not statuses:
            reasons.append("QC report has no checks")

    singles = single_source_sentences(claim_ids_path, claim_ledger_path)
    for item in singles:
        reasons.append(f"sentence {item['sentence_index']}: {item['reason']}")

    signoffs = owner_signoffs or {}
    for key in REQUIRED_OWNER_SIGNOFFS:
        if not signoffs.get(key):
            reasons.append(f"owner sign-off missing: {key}")

    if extra:
        reasons.extend(extra)

    return {"publishable": not reasons, "reasons": reasons,
            "single_source_count": len(singles)}
