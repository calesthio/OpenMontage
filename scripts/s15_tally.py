#!/usr/bin/env python3
"""S15: join the owner's blind scoring.csv with mapping.json and apply gates.

Pass gates (owner-applied):
  * 0 black/NaN                       (from S15_CHECKS.json, objective)
  * >= 14/18 correct anatomy per style (owner-scored, creature tiles only)
  * >= 15/18 caption space per style   (owner-scored)
  * phone readability median >= 4/5    (owner-scored)

This script never fills the CSV, never edits the model recipe and refuses to
report a verdict while the CSV is incomplete (OWNER_GATED).

Usage:
  python scripts/s15_tally.py
  python scripts/s15_tally.py --csv ... --mapping ... --checks ...
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO / "projects/s15/blind/scoring.csv"
DEFAULT_MAPPING = REPO / "projects/s15/blind/mapping.json"
DEFAULT_CHECKS = REPO / "docs/openmontage/image_gen/S15_CHECKS.json"

YES = {"yes", "y", "true", "1"}
NO = {"no", "n", "false", "0"}
NA = {"na", "n/a", "-", ""}
ANATOMY_RATIO_NUM, ANATOMY_RATIO_DEN = 14, 18   # owner gate, applied as a ratio
CAPTION_RATIO_NUM, CAPTION_RATIO_DEN = 15, 18   # owner gate, applied as a ratio
READABILITY_MEDIAN_GATE = 4.0


def _norm(value: Optional[str]) -> str:
    return (value or "").strip()


def _bool(value: str) -> Optional[bool]:
    v = _norm(value).lower()
    if v in YES:
        return True
    if v in NO:
        return False
    return None


def _int(value: str) -> Optional[int]:
    v = _norm(value)
    if not v:
        return None
    try:
        n = int(float(v))
    except ValueError:
        return None
    return n if 1 <= n <= 5 else None


def tally(csv_path: Path, mapping_path: Path,
          checks_path: Optional[Path]) -> Dict[str, Any]:
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    tiles = mapping["tiles"]

    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        rows = [{k: _norm(v) for k, v in r.items() if k}
                for r in csv.DictReader(fh)]

    by_code = {r["code"]: r for r in rows if r.get("code")}
    unknown = sorted(set(by_code) - set(tiles))
    missing_codes = sorted(set(tiles) - set(by_code))

    scored: List[Dict[str, Any]] = []
    unscored: List[str] = []
    for code, tile in tiles.items():
        row = by_code.get(code)
        if row is None:
            unscored.append(code)
            continue
        anatomy = _bool(row.get("anatomy_ok", ""))
        caption = _bool(row.get("caption_space_ok", ""))
        readability = _int(row.get("readability_1_5", ""))
        # anatomy is NA for habitat/planet tiles; still requires an entry
        anatomy_raw = _norm(row.get("anatomy_ok", "")).lower()
        anatomy_na = anatomy_raw in NA and anatomy_raw != ""
        if anatomy is None and not anatomy_na:
            unscored.append(code)
            continue
        if caption is None or readability is None:
            unscored.append(code)
            continue
        scored.append({
            "code": code,
            "style": tile["style"],
            "scene": tile["scene"],
            "size": tile.get("size"),
            "anatomy": "na" if anatomy_na else bool(anatomy),
            "caption": bool(caption),
            "readability": readability,
            "notes": row.get("notes", ""),
        })

    per_style: Dict[str, Any] = {}
    for style in sorted({t["style"] for t in tiles.values()}):
        items = [s for s in scored if s["style"] == style]
        animal = [s for s in items if s["anatomy"] != "na"]
        cap_ok = sum(1 for s in items if s["caption"])
        reads = [s["readability"] for s in items]
        per_style[style] = {
            "tiles": len([t for t in tiles.values() if t["style"] == style]),
            "scored": len(items),
            "anatomy_scored": len(animal),
            "anatomy_correct": sum(1 for s in animal if s["anatomy"] is True),
            "anatomy_na": len(items) - len(animal),
            "caption_ok": cap_ok,
            "readability_median": (round(statistics.median(reads), 2)
                                   if reads else None),
            "readability_n": len(reads),
        }

    black = None
    nan = None
    gate0 = None
    if checks_path and Path(checks_path).is_file():
        checks = json.loads(Path(checks_path).read_text(encoding="utf-8"))
        g0 = checks.get("gate_0_black_nan", {})
        black = g0.get("black")
        nan = g0.get("nan")
        gate0 = bool(g0.get("pass"))

    complete = not unscored and not unknown and len(scored) == len(tiles)
    status = "COMPLETE" if complete else "OWNER_GATED"

    gates: Dict[str, Any] = {}
    if complete:
        for style, d in per_style.items():
            anat_total = d["anatomy_scored"] or 0
            cap_total = d["scored"] or 0
            anat_ratio = (d["anatomy_correct"] / anat_total) if anat_total else 0.0
            cap_ratio = (d["caption_ok"] / cap_total) if cap_total else 0.0
            gates[style] = {
                "anatomy": bool(anat_total
                                and anat_ratio >= ANATOMY_RATIO_NUM / ANATOMY_RATIO_DEN),
                "anatomy_ratio": round(anat_ratio, 3),
                "caption": bool(cap_total
                                and cap_ratio >= CAPTION_RATIO_NUM / CAPTION_RATIO_DEN),
                "caption_ratio": round(cap_ratio, 3),
                "readability": (d["readability_median"] is not None
                                and d["readability_median"] >= READABILITY_MEDIAN_GATE),
            }
            gates[style]["all"] = all(
                gates[style][k] for k in ("anatomy", "caption", "readability"))

    report = {
        "schema_version": "1.0",
        "milestone": "S15",
        "status": status,
        "csv": str(csv_path),
        "mapping": str(mapping_path),
        "checks": str(checks_path) if checks_path else None,
        "tiles_total": len(tiles),
        "tiles_scored": len(scored),
        "unscored_codes": unscored,
        "unknown_codes": unknown,
        "gate_0_black_nan": {"black": black, "nan": nan, "pass": gate0},
        "gates_definition": {
            "anatomy_per_style": "owner gate 14/18, applied as the ratio "
                                 ">= 0.7778 of the creature tiles actually scored "
                                 "per style (this run: 6 creature tiles x 2 seeds)",
            "caption_space_per_style": "owner gate 15/18, applied as the ratio "
                                       ">= 0.8333 of the scored tiles per style "
                                       "(this run: 12 tiles)",
            "readability_median": f">= {READABILITY_MEDIAN_GATE}/5",
            "absolute_passed": "the report also prints raw counts so the owner "
                               "can apply 14/18 and 15/18 literally if they extend "
                               "the run to three seeds",
        },
        "per_style": per_style,
        "gates": gates,
        "note": "OWNER_GATED means scoring.csv is not finished; nothing is "
                "recommended and no style is locked on incomplete data.",
    }
    return report


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--mapping", default=str(DEFAULT_MAPPING))
    ap.add_argument("--checks", default=str(DEFAULT_CHECKS))
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    rep = tally(Path(args.csv), Path(args.mapping),
                Path(args.checks) if args.checks else None)
    text = json.dumps(rep, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    print(text)
    return 0 if rep["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    sys.exit(main())
