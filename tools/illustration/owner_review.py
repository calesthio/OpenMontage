#!/usr/bin/env python3
"""tools/illustration/owner_review.py - the owner approved/rejected ledger.

A CSV ledger (the owner writes it, or the tools append to it):

    render_id,prompt_sha256,sha256,decision,reviewer,reviewed_utc,note

  * `approved` - the image may be used and is **never regenerated** (the P3
    cache reads this file),
  * `rejected` - the image must not be used; the run re-queues it with a new
    seed (after 4 attempts it stays rejected and the episode fails closed).

The ledger is the owner's decision record. The agents never write a decision
into it on their own - `write_decision` is only called by an explicit tool
invocation that names the reviewer.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

#: The ledger columns (the first two are the key).
LEDGER_COLUMNS = (
    "render_id", "prompt_sha256", "sha256", "decision", "reviewer",
    "reviewed_utc", "note",
)

DECISIONS = ("approved", "rejected")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ledger_path(episode_root: str | Path) -> Path:
    """The canonical ledger path of an episode."""
    return Path(episode_root) / "assets" / "illustrations" / "owner_review.csv"


def read_ledger(path: str | Path) -> List[Dict[str, str]]:
    """Read the ledger (empty when the file does not exist)."""
    p = Path(path)
    if not p.is_file():
        return []
    rows: List[Dict[str, str]] = []
    with p.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("render_id"):
                continue
            rows.append({key: (row.get(key) or "") for key in LEDGER_COLUMNS})
    return rows


def decisions_by_render(path: str | Path) -> Dict[str, Dict[str, str]]:
    """The last decision per render id."""
    out: Dict[str, Dict[str, str]] = {}
    for row in read_ledger(path):
        out[row["render_id"]] = row
    return out


def write_decision(path: str | Path, render_id: str, decision: str, *,
                   sha256: str = "", prompt_sha256: str = "",
                   reviewer: str = "owner", note: str = "",
                   reviewed_utc: Optional[str] = None) -> Dict[str, str]:
    """Append (or replace) one decision in the ledger."""
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {list(DECISIONS)}")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = [r for r in read_ledger(p) if r.get("render_id") != render_id]
    row = {
        "render_id": render_id,
        "prompt_sha256": prompt_sha256,
        "sha256": sha256,
        "decision": decision,
        "reviewer": reviewer,
        "reviewed_utc": reviewed_utc or _now(),
        "note": note,
    }
    rows.append(row)
    with p.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(LEDGER_COLUMNS))
        writer.writeheader()
        for item in rows:
            writer.writerow({key: item.get(key, "") for key in LEDGER_COLUMNS})
    return row


def approved_prompt_hashes(path: str | Path) -> Dict[str, str]:
    """prompt_sha256 -> render_id for every approved image."""
    return {row["prompt_sha256"]: row["render_id"]
            for row in read_ledger(path)
            if row.get("decision") == "approved" and row.get("prompt_sha256")}


def rejected_prompt_hashes(path: str | Path) -> Dict[str, str]:
    """prompt_sha256 -> render_id for every rejected image."""
    return {row["prompt_sha256"]: row["render_id"]
            for row in read_ledger(path)
            if row.get("decision") == "rejected" and row.get("prompt_sha256")}
