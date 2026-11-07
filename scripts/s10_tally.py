#!/usr/bin/env python3
"""S10-5: tally the owner's blind results (style test).

Reads projects/s10_blind/results.csv and projects/s10_blind/mapping.json and
prints wins / losses / caption readability per STYLE. It never judges beauty,
never fills the CSV and never edits STYLE_BIBLE.md: it only reports, and it
refuses to recommend anything while the CSV is incomplete (OWNER_GATED).

Usage:
  python scripts/s10_tally.py                       # default paths
  python scripts/s10_tally.py --csv ... --mapping ...
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
CSV_PATH = REPO / "projects/s10_blind/results.csv"
MAPPING_PATH = REPO / "projects/s10_blind/mapping.json"
LABELS = ("A", "B", "C")
YES = {"yes", "y", "true", "1"}
NO = {"no", "n", "false", "0"}


def _norm(value: Optional[str]) -> str:
    return (value or "").strip()


def _valid_label(value: str) -> bool:
    return _norm(value).upper() in LABELS


def _valid_bool(value: str) -> bool:
    v = _norm(value).lower()
    return v in YES or v in NO


def tally(csv_path: Path, mapping_path: Path) -> Dict[str, Any]:
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    scenes = mapping["scenes"]
    rows: List[Dict[str, str]] = []
    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append({k: _norm(v) for k, v in row.items() if k})

    filled = [
        r for r in rows
        if _valid_label(r.get("best_panel", ""))
        and all(_valid_bool(r.get(f"readable_with_captions_{l}", ""))
                for l in LABELS)
    ]
    out: Dict[str, Any] = {
        "status": "INCOMPLETE",
        "csv": str(csv_path),
        "mapping": str(mapping_path),
        "expected": len(scenes),
        "filled": len(filled),
        "n_scenes": len(scenes),
        "wins": {},
        "losses": {},
        "caption_readable": {},
        "caption_scored": {},
        "comment": "",
        "recommendation": None,
    }
    if len(filled) < len(scenes):
        out["comment"] = ("OWNER_GATED: the CSV is not complete, so no style is "
                          "recommended and STYLE_BIBLE.md is not touched.")
        return out

    wins: Dict[str, int] = {}
    losses: Dict[str, int] = {}
    readable: Dict[str, int] = {}
    scored: Dict[str, int] = {}
    per_scene: Dict[str, Any] = {}
    for r in filled:
        scene = r["scene"]
        order = scenes.get(scene)
        if not order:
            continue
        best = r["best_panel"].upper()
        worst = r.get("worst_panel", "").upper()
        best_style = order[best]
        wins[best_style] = wins.get(best_style, 0) + 1
        if worst in LABELS:
            losses[order[worst]] = losses.get(order[worst], 0) + 1
        panel_read = {}
        for label in LABELS:
            style = order[label]
            value = r[f"readable_with_captions_{label}"].lower()
            ok = value in YES
            scored[style] = scored.get(style, 0) + 1
            if ok:
                readable[style] = readable.get(style, 0) + 1
            panel_read[label] = {"style": style, "readable": ok}
        per_scene[scene] = {
            "best_panel": best, "best_style": best_style,
            "worst_panel": worst or None,
            "worst_style": order.get(worst) if worst in LABELS else None,
            "panels": panel_read,
            "comment": r.get("comment", ""),
        }

    order_by_wins = sorted(wins.items(), key=lambda kv: (-kv[1], kv[0]))
    top = order_by_wins[0] if order_by_wins else None
    tie = (len(order_by_wins) > 1 and order_by_wins[1][1] == top[1]) if top else False
    out.update({
        "status": "COMPLETE",
        "wins": wins,
        "losses": losses,
        "caption_readable": readable,
        "caption_scored": scored,
        "per_scene": per_scene,
        "recommendation": None if tie else (top[0] if top else None),
        "comment": ("TIE between the top styles - the owner decides, the agent "
                    "does not break a tie." if tie else
                    "Owner-decided. Write the winner into STYLE_BIBLE.md by hand "
                    "(the agent does not edit it from a tally)."),
    })
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(CSV_PATH))
    ap.add_argument("--mapping", default=str(MAPPING_PATH))
    args = ap.parse_args(argv)
    result = tally(Path(args.csv), Path(args.mapping))
    print(json.dumps(result, indent=2))
    if result["status"] != "COMPLETE":
        print(f"\n{result['comment']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
