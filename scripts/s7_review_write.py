#!/usr/bin/env python3
"""S7-9 helper: upsert the agent's rubric scores for one render into the sheet.

The review sheet is a CSV with one row per render (render_id, scene_id, model,
then the six rubric dimensions 0-2, then a free-text note). The agent views an
image and records a score; this script writes that score into the sheet without
touching the other rows, so a partially scored sheet is always valid and the
work survives a session restart.

Usage:
  python scripts/s7_review_write.py --csv /tmp/kilo/s7_agent_review.csv \
      --render-id r0001 --anatomy 0 --geometry 1 --count-relation 0 \
      --texture 2 --text 0 --usefulness 0 --notes "collage, garbled text"
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional

DIMS = ["anatomy", "geometry", "count_relation", "texture", "text", "usefulness"]
HEADER = ["render_id", "scene_id", "model"] + DIMS + ["notes"]


def read_sheet(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"BLOCKED: review sheet not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in HEADER if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"BLOCKED: {path} missing columns: {missing}")
        return [dict(r) for r in reader]


def write_sheet(path: Path, rows: List[Dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in HEADER})


def upsert(rows: List[Dict[str, str]], render_id: str, scores: Dict[str, int],
           notes: str) -> List[Dict[str, str]]:
    for r in rows:
        if (r.get("render_id") or "").strip() == render_id:
            for d in DIMS:
                if d in scores:
                    r[d] = str(scores[d])
            if notes:
                r["notes"] = notes
            return rows
    raise SystemExit(f"BLOCKED: render_id {render_id!r} is not in the review sheet")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--render-id", required=True)
    ap.add_argument("--notes", default="")
    for d in DIMS:
        ap.add_argument(f"--{d.replace('_', '-')}", type=int, default=None,
                        choices=[0, 1, 2], help=f"rubric score for {d}")
    args = ap.parse_args(argv)

    path = Path(args.csv)
    rows = read_sheet(path)
    scores = {d: getattr(args, d) for d in DIMS
              if getattr(args, d, None) is not None}
    if not scores:
        raise SystemExit("BLOCKED: no dimension scores given")
    upsert(rows, args.render_id, scores, args.notes)
    write_sheet(path, rows)
    print(f"scored {args.render_id}: " +
          ", ".join(f"{d}={v}" for d, v in scores.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
