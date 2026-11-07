#!/usr/bin/env python3
"""S7-9: aggregate the agent's visual review into an advisory assessment.

The agent's own scores (0-2 per dimension, the OpenCode rubric from
scripts/score_rubric.py) are typed in by the agent after looking at every
image; this script does the arithmetic so the numbers cannot drift:

  * severe artifacts   = dimension scores equal to 0 (count of scores, and
                         the number of images carrying at least one 0)
  * usable share       = images with no dimension scored 0
  * repair burden      = mean(2 - score) over all dimension scores
  * ranking            = severe artifacts, then usable share, then s/image

The output is ADVISORY: the owner's blind CSV decides the winner.

Usage:
  python scripts/s7_agent_assessment.py --scores <csv> --pick klein \
      --confidence medium --out docs/openmontage/image_gen/S7_AGENT_ASSESSMENT.json
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
DIMS = ["anatomy", "geometry", "count_relation", "texture", "text", "usefulness"]
MODEL_ORDER = ["sdxl", "klein", "zimage"]
DEFAULT_OUT = REPO / "docs/openmontage/image_gen/S7_AGENT_ASSESSMENT.json"


def load_scores(path: Path) -> List[Dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [d for d in ("render_id", "model") + tuple(DIMS)
                   if d not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"BLOCKED: {path} missing columns: {missing}")
        rows: List[Dict[str, Any]] = []
        for raw in reader:
            if not (raw.get("render_id") or "").strip():
                continue
            scores: Dict[str, int] = {}
            for d in DIMS:
                try:
                    v = int((raw[d] or "").strip())
                except (TypeError, ValueError):
                    raise SystemExit(
                        f"BLOCKED: {raw.get('render_id')} {d}={raw.get(d)!r} is not an integer")
                if v < 0 or v > 2:
                    raise SystemExit(
                        f"BLOCKED: {raw.get('render_id')} {d}={v} out of range 0-2")
                scores[d] = v
            rows.append({
                "render_id": raw["render_id"].strip(),
                "scene_id": (raw.get("scene_id") or "").strip(),
                "model": raw["model"].strip(),
                "scores": scores,
                "notes": (raw.get("notes") or "").strip(),
            })
    if not rows:
        raise SystemExit(f"BLOCKED: {path} has no rows")
    return rows


def aggregate(rows: List[Dict[str, Any]], speed: Dict[str, float]
              ) -> Dict[str, Dict[str, Any]]:
    per_model: Dict[str, Dict[str, Any]] = {}
    for model in MODEL_ORDER:
        imgs = [r for r in rows if r["model"] == model]
        if not imgs:
            continue
        all_scores = [s for r in imgs for s in r["scores"].values()]
        zeros = sum(1 for s in all_scores if s == 0)
        imgs_with_zero = sum(1 for r in imgs if any(v == 0 for v in r["scores"].values()))
        usable = sum(1 for r in imgs if all(v > 0 for v in r["scores"].values()))
        per_model[model] = {
            "n_images": len(imgs),
            "severe_artifact_scores": zeros,
            "images_with_severe_artifact": imgs_with_zero,
            "usable_images": usable,
            "usable_share": round(usable / len(imgs), 4),
            "repair_burden": round(
                statistics.mean([2 - s for s in all_scores]), 4) if all_scores else None,
            "mean_score": round(statistics.mean(all_scores), 3) if all_scores else None,
            "sec_per_image": speed.get(model),
        }
    return per_model


def weakest_scenes(rows: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Scenes where a model scored 0 on any dimension, worst first."""
    out: Dict[str, List[str]] = {}
    for model in MODEL_ORDER:
        imgs = [r for r in rows if r["model"] == model]
        scored = sorted(
            imgs,
            key=lambda r: (sum(1 for v in r["scores"].values() if v == 0),
                           sum(r["scores"].values())))
        bad = [r["scene_id"] for r in scored if any(v == 0 for v in r["scores"].values())]
        out[model] = bad[:3]
    return out


def rank(per_model: Dict[str, Dict[str, Any]]) -> List[str]:
    return sorted(
        per_model,
        key=lambda m: (per_model[m]["severe_artifact_scores"],
                       -per_model[m]["usable_share"],
                       per_model[m].get("sec_per_image") or 1e9))


def emit_template(test_set: Path, out_csv: Path) -> int:
    """Write a review sheet pre-filled with render_id / scene_id / model."""
    doc = json.loads(test_set.read_text(encoding="utf-8"))
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["render_id", "scene_id", "model"] + DIMS + ["notes"])
        for r in doc["renders"]:
            w.writerow([r["render_id"], r["scene_id"], r["model"]] + [""] * len(DIMS) + [""])
    return len(doc["renders"])


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scores", help="CSV of agent rubric scores")
    ap.add_argument("--pick", help="the model the agent would pick")
    ap.add_argument("--confidence", choices=["low", "medium", "high"])
    ap.add_argument("--speed", default="", help="JSON {model: sec_per_image}")
    ap.add_argument("--emit-template", metavar="CSV",
                    help="write an empty review sheet and exit")
    ap.add_argument("--test-set", default=str(
        REPO / "docs/openmontage/image_gen/S7_TEST_SET.json"))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    if args.emit_template:
        n = emit_template(Path(args.test_set), Path(args.emit_template))
        print(f"wrote {args.emit_template} ({n} rows)")
        return 0

    if not (args.scores and args.pick and args.confidence):
        ap.error("--scores, --pick and --confidence are required")

    rows = load_scores(Path(args.scores))
    speed = json.loads(args.speed) if args.speed else {}
    per_model = aggregate(rows, speed)
    order = rank(per_model)

    doc = {
        "schema_version": "1.0",
        "milestone": "S7-9",
        "label": "agent opinion, not independent; a vision model can miss "
                 "anatomy errors and misread flat art",
        "rubric": "OpenCode rubric (scripts/score_rubric.py): 0-2 per dimension",
        "dimensions": DIMS,
        "agent_pick": args.pick,
        "confidence": args.confidence,
        "ranking_severe_then_usable_then_speed": order,
        "per_model": per_model,
        "weakest_scenes": weakest_scenes(rows),
        "images": [
            {"render_id": r["render_id"], "scene_id": r["scene_id"], "model": r["model"],
             "scores": r["scores"], "notes": r["notes"]}
            for r in rows
        ],
        "owner_decides": "The owner's blind CSV (projects/s7_blind/results.csv) "
                         "decides the winner; scripts/s7_tally.py compares it with "
                         "this advisory pick.",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    print("agent advisory ranking (severe artifacts -> usable share -> speed):")
    for m in order:
        d = per_model[m]
        print(f"  {m:8s} severe_scores={d['severe_artifact_scores']:3d} "
              f"usable={d['usable_images']}/{d['n_images']} "
              f"repair_burden={d['repair_burden']} s/img={d['sec_per_image']}")
    print(f"agent pick: {args.pick} (confidence: {args.confidence})")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
