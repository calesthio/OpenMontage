#!/usr/bin/env python3
"""Rubric scorer for the S3 prompt bake-off (S3-3).

Ingests a CSV of owner/reviewer scores (one row per image per reviewer):

    render_id,model,variant,reviewer,anatomy,geometry,count_relation,texture,text,usefulness

with each dimension scored 0-2. Outputs, per model x variant cell:
  - severe-artifact rate  = numerator / denominator   (numerator = # scores
    equal to 0; denominator = # total dimension-scores)
  - repair burden         = mean(2 - score) over all scores  (0 = perfect, 2 = rebuild)
  - usable share          = fraction of images with no dimension scored 0
  - eligible              = cell has >= 24 images

Winner table: among eligible cells, highest usable share wins; ties broken by
lowest repair burden, then lowest severe-artifact rate. If no cell has >= 24
images, prints "INSUFFICIENT" and declares no winner.

Two reviewers are supported; any dimension on which the two reviewers of the
same image disagree by > 1 is flagged in a disagreements list.

Prints a table to stdout and, with --json, writes a machine-readable report.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple

HEADER = ["render_id", "model", "variant", "reviewer"]
DIMS = ["anatomy", "geometry", "count_relation", "texture", "text", "usefulness"]
FULL_HEADER = HEADER + DIMS
MIN_IMAGES_FOR_WINNER = 24


class RubricError(ValueError):
    pass


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score prompt bake-off rubric CSV")
    p.add_argument("csv", help="path to rubric scores CSV")
    p.add_argument("--json", help="write machine-readable report to this path")
    return p.parse_args(argv)


def load_scores(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise RubricError("CSV is empty (no header)")
        missing = [c for c in FULL_HEADER if c not in reader.fieldnames]
        if missing:
            raise RubricError(f"CSV missing columns: {missing}")
        for lineno, raw in enumerate(reader, start=2):
            render_id = (raw.get("render_id") or "").strip()
            model = (raw.get("model") or "").strip()
            variant = (raw.get("variant") or "").strip().upper()
            reviewer = (raw.get("reviewer") or "").strip()
            if not render_id or not model or not variant or not reviewer:
                raise RubricError(f"line {lineno}: missing render_id/model/variant/reviewer")
            scores: Dict[str, int] = {}
            for d in DIMS:
                try:
                    v = int(raw[d])
                except (TypeError, ValueError):
                    raise RubricError(f"line {lineno}: {d} is not an integer: {raw.get(d)!r}")
                if v < 0 or v > 2:
                    raise RubricError(
                        f"line {lineno}: {d}={v} out of range 0-2 (render_id={render_id})")
                scores[d] = v
            rows.append({
                "render_id": render_id, "model": model, "variant": variant,
                "reviewer": reviewer, "scores": scores,
            })
    return rows


def analyze(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    # group images by cell
    cell_images: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
        lambda: {"render_ids": set(), "rows": [], "reviewers_per_image": defaultdict(set)}
    )
    for r in rows:
        key = (r["model"], r["variant"])
        cell_images[key]["render_ids"].add(r["render_id"])
        cell_images[key]["rows"].append(r)
        cell_images[key]["reviewers_per_image"][r["render_id"]].add(r["reviewer"])

    cells: Dict[str, Any] = {}
    all_disagreements: List[Dict[str, Any]] = []

    for key, info in cell_images.items():
        model, variant = key
        cell_key = f"{model}|{variant}"
        render_ids = sorted(info["render_ids"])
        n_images = len(render_ids)

        total_scores = 0
        zero_scores = 0
        repair_sum = 0.0
        for r in info["rows"]:
            for d in DIMS:
                s = r["scores"][d]
                total_scores += 1
                if s == 0:
                    zero_scores += 1
                repair_sum += (2 - s)

        # usable share: images with no zero dimension across ALL reviewers
        usable = 0
        for rid in render_ids:
            image_rows = [r for r in info["rows"] if r["render_id"] == rid]
            has_zero = any(r["scores"][d] == 0 for r in image_rows for d in DIMS)
            if not has_zero:
                usable += 1
        usable_share = (usable / n_images) if n_images else 0.0

        severe_rate = (zero_scores / total_scores) if total_scores else 0.0
        repair_burden = (repair_sum / total_scores) if total_scores else 0.0

        eligible = n_images >= MIN_IMAGES_FOR_WINNER

        cells[cell_key] = {
            "model": model, "variant": variant,
            "n_images": n_images,
            "eligible": eligible,
            "severe_artifact_rate": {
                "num": zero_scores, "den": total_scores,
                "rate": round(severe_rate, 6),
            },
            "repair_burden": round(repair_burden, 6),
            "usable_share": round(usable_share, 6),
            "usable_images": usable,
        }

    # disagreements between the two reviewers of the same image (diff > 1)
    by_image_render: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_image_render[r["render_id"]].append(r)
    for rid, image_rows in by_image_render.items():
        reviewers = {r["reviewer"] for r in image_rows}
        if len(reviewers) < 2:
            continue
        # compare each pair of reviewers on this image
        rev_rows = defaultdict(list)
        for r in image_rows:
            rev_rows[r["reviewer"]].append(r)
        reviewer_list = sorted(rev_rows)
        for i in range(len(reviewer_list)):
            for j in range(i + 1, len(reviewer_list)):
                a = rev_rows[reviewer_list[i]][0]
                b = rev_rows[reviewer_list[j]][0]
                for d in DIMS:
                    diff = abs(a["scores"][d] - b["scores"][d])
                    if diff > 1:
                        all_disagreements.append({
                            "render_id": rid,
                            "model": a["model"], "variant": a["variant"],
                            "reviewer_1": reviewer_list[i], "reviewer_2": reviewer_list[j],
                            "dimension": d, "score_1": a["scores"][d],
                            "score_2": b["scores"][d], "diff": diff,
                        })

    # winner among eligible cells
    eligible = [c for c in cells.values() if c["eligible"]]
    winner = None
    winner_status = "INSUFFICIENT"
    if eligible:
        ranked = sorted(
            eligible,
            key=lambda c: (-c["usable_share"], c["repair_burden"],
                           c["severe_artifact_rate"]["rate"]),
        )
        winner = ranked[0]
        winner_status = "WINNER"

    return {
        "n_images_total": len({r["render_id"] for r in rows}),
        "n_cells": len(cells),
        "min_images_for_winner": MIN_IMAGES_FOR_WINNER,
        "winner_status": winner_status,
        "winner": {
            "model": winner["model"], "variant": winner["variant"],
            "usable_share": winner["usable_share"],
            "repair_burden": winner["repair_burden"],
            "severe_artifact_rate": winner["severe_artifact_rate"]["rate"],
            "n_images": winner["n_images"],
        } if winner else None,
        "cells": cells,
        "disagreements": sorted(all_disagreements, key=lambda x: (x["render_id"], x["dimension"])),
        "n_disagreements": len(all_disagreements),
    }


def render_table(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("Rubric scorer results")
    lines.append(f"  total images: {result['n_images_total']}  "
                 f"cells: {result['n_cells']}  "
                 f"min images for winner: {result['min_images_for_winner']}")
    lines.append(f"  winner status: {result['winner_status']}")
    if result["winner"]:
        w = result["winner"]
        lines.append(
            f"  winner: {w['model']}|{w['variant']}  "
            f"usable={w['usable_share']}  repair={w['repair_burden']}  "
            f"severe={w['severe_artifact_rate']}  n_images={w['n_images']}"
        )
    else:
        lines.append("  winner: none (INSUFFICIENT: no cell has >= 24 images)")
    lines.append("")
    lines.append("Per model|variant cell:")
    lines.append(
        f"  {'cell':<14}{'n_img':>6}{'elig':>5}{'severe num/den':>15}"
        f"{'severe rate':>12}{'repair':>9}{'usable':>9}"
    )
    for key in sorted(result["cells"]):
        c = result["cells"][key]
        sr = c["severe_artifact_rate"]
        lines.append(
            f"  {key:<14}{c['n_images']:>6}{'Y' if c['eligible'] else 'n':>5}"
            f"{sr['num']}/{sr['den']:>12}{sr['rate']:>12.4f}"
            f"{c['repair_burden']:>9.4f}{c['usable_share']:>9.4f}"
        )
    if result["disagreements"]:
        lines.append("")
        lines.append(f"Reviewer disagreements (>1 on a dimension): {result['n_disagreements']}")
        for d in result["disagreements"]:
            lines.append(
                f"  {d['render_id']} {d['model']}|{d['variant']} "
                f"{d['dimension']}: R{d['reviewer_1']}={d['score_1']} "
                f"R{d['reviewer_2']}={d['score_2']} diff={d['diff']}"
            )
    else:
        lines.append("")
        lines.append("Reviewer disagreements (>1): none")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        rows = load_scores(args.csv)
    except RubricError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not rows:
        result = analyze([])
    else:
        result = analyze(rows)
    print(render_table(result))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
