#!/usr/bin/env python3
"""S5-5: tally the owner's blind-pack CSV into a per-model result table.

Reads ONLY two files:
  1. the owner-filled CSV (scene,best_panel,worst_panel,comment,
     anatomy_ok_A,anatomy_ok_B,anatomy_ok_C)
  2. projects/s5_blind/mapping.json (panel -> model per scene + model metrics)

It reports wins, losses, anatomy-ok count out of 10 and the speed/VRAM table.
The recommended model is taken from the owner's wins, never from this script's
own opinion. It prints TIE when the best two models differ by <= 1 win, and it
refuses to recommend anything while the CSV is incomplete.

Usage:
  python scripts/s5_tally.py [--csv projects/s5_blind/results.csv]
                             [--mapping projects/s5_blind/mapping.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO / "projects/s5_blind/results.csv"
DEFAULT_MAPPING = REPO / "projects/s5_blind/mapping.json"
MODEL_ORDER = ["sdxl", "zimage", "klein"]
PANELS = ("A", "B", "C")


def _panel(value: str, field: str, scene: str, allow_blank: bool = False) -> str:
    v = (value or "").strip().upper()
    if not v and allow_blank:
        return ""
    if v not in PANELS:
        raise ValueError(
            f"{field} for scene {scene} is {value!r}; expected one of A|B|C")
    return v


def _yes(value: str) -> Optional[bool]:
    v = (value or "").strip().lower()
    if v in {"yes", "y", "true", "1"}:
        return True
    if v in {"no", "n", "false", "0"}:
        return False
    return None  # blank / unreadable -> not counted


def load_mapping(path: Path | str | Dict[str, Any] = DEFAULT_MAPPING) -> Dict[str, Any]:
    if isinstance(path, dict):
        doc = path
    else:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    scenes = doc.get("scenes") or {}
    for scene, panels in scenes.items():
        models = set(panels.values())
        if len(models) != 3:
            raise ValueError(f"mapping for {scene} must give 3 distinct models, got {panels}")
    return {
        "panels_by_scene": scenes,
        "model_metrics": doc.get("model_metrics") or {},
        "raw": doc,
    }


def load_results(path: Path | str = DEFAULT_CSV) -> List[Dict[str, Any]]:
    p = Path(path)
    with p.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    out: List[Dict[str, Any]] = []
    for row in rows:
        scene = (row.get("scene") or "").strip()
        if not scene:
            continue
        best = _panel(row.get("best_panel", ""), "best_panel", scene, allow_blank=True)
        worst = _panel(row.get("worst_panel", ""), "worst_panel", scene, allow_blank=True)
        if best and worst and best == worst:
            raise ValueError(
                f"scene {scene}: best_panel and worst_panel are both {best!r}")
        out.append({
            "scene": scene,
            "best": best,
            "worst": worst,
            "comment": (row.get("comment") or "").strip(),
            "anatomy": {p_: _yes(row.get(f"anatomy_ok_{p_}", "")) for p_ in PANELS},
        })
    if not out:
        raise ValueError(f"{p} has no scene rows")
    return out


def _panels(mapping: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Accept either load_mapping()'s normalised form or the raw JSON document."""
    if "panels_by_scene" in mapping:
        return mapping["panels_by_scene"]
    if "scenes" in mapping:
        return mapping["scenes"] or {}
    # a bare {scene: {"A": model, ...}} map
    return mapping


def tally(results: List[Dict[str, Any]],
          mapping: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    panels = _panels(mapping)
    stats: Dict[str, Dict[str, Any]] = {
        m: {"wins": 0, "losses": 0, "anatomy_ok": 0, "anatomy_judged": 0,
            "scenes_won": []}
        for m in MODEL_ORDER
    }
    for row in results:
        scene = row["scene"]
        if scene not in panels:
            raise ValueError(f"scene {scene} is not in the blind mapping")
        if row["best"]:
            model = panels[scene][row["best"]]
            stats[model]["wins"] += 1
            stats[model]["scenes_won"].append(scene)
        if row["worst"]:
            model = panels[scene][row["worst"]]
            stats[model]["losses"] += 1
        for panel, verdict in row["anatomy"].items():
            if verdict is None:
                continue
            model = panels[scene][panel]
            stats[model]["anatomy_judged"] += 1
            stats[model]["anatomy_ok"] += int(verdict)
    for m, s in stats.items():
        s["anatomy_out_of"] = 10  # fixed test set size (S5-1)
    return stats


def _fmt(v: Any, digits: int = 2) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def render_report(results: List[Dict[str, Any]],
                  mapping: Dict[str, Any]) -> str:
    panels = _panels(mapping)
    total_scenes = len(panels)
    filled = sum(1 for r in results if r["best"])
    stats = tally(results, mapping)
    lines: List[str] = []

    lines.append(f"S5 blind-pack tally — {filled}/{total_scenes} scenes filled")
    lines.append("")
    lines.append("| model | wins | losses | anatomy ok |")
    lines.append("|---|---|---|---|")
    for m in MODEL_ORDER:
        s = stats[m]
        lines.append(f"| {m} | {s['wins']} | {s['losses']} | "
                     f"{s['anatomy_ok']}/{s['anatomy_out_of']} |")
    lines.append("")

    metrics = mapping.get("model_metrics") or {}
    lines.append("| model | s/image (steady) | peak VRAM MB | black/NaN/OOM | load s |")
    lines.append("|---|---|---|---|---|")
    for m in MODEL_ORDER:
        mm = metrics.get(m) or {}
        issues = "-".join(_fmt(mm.get(k)) for k in
                          ("black_count", "nan_count", "oom_count"))
        lines.append(
            f"| {m} | {_fmt(mm.get('steady_state_sec_per_image'), 2)} | "
            f"{_fmt(mm.get('peak_vram_mb'))} | {issues} | "
            f"{_fmt(mm.get('load_seconds'), 1)} |")
    lines.append("")

    if filled < total_scenes:
        lines.append(f"PARTIAL: {filled}/{total_scenes} scenes filled — "
                     "no recommendation until every scene has a best_panel.")
        return "\n".join(lines) + "\n"

    ranked = sorted(MODEL_ORDER, key=lambda m: (-stats[m]["wins"], m))
    top, second = ranked[0], ranked[1]
    gap = stats[top]["wins"] - stats[second]["wins"]
    if gap <= 1:
        lines.append(f"TIE — {top} ({stats[top]['wins']}) and {second} "
                     f"({stats[second]['wins']}) differ by {gap} win(s); "
                     "no single recommended model.")
    else:
        lines.append(f"recommended model: {top} "
                     f"({stats[top]['wins']}/{total_scenes} scene wins, "
                     f"owner's CSV only)")
    lines.append("")
    lines.append("Anatomy is the owner's yes/no judgement, not the script's.")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--mapping", default=str(DEFAULT_MAPPING))
    args = ap.parse_args(argv)

    try:
        mapping = load_mapping(args.mapping)
        results = load_results(args.csv)
    except FileNotFoundError as exc:
        print(f"BLOCKED: {exc}. Fill the CSV first "
              f"(see {DEFAULT_CSV.parent}/INSTRUCTIONS.txt).")
        return 2
    except ValueError as exc:
        print(f"BLOCKED: {exc}")
        return 2

    print(render_report(results, mapping))
    return 0


if __name__ == "__main__":
    sys.exit(main())
