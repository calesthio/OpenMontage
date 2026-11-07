#!/usr/bin/env python3
"""S5-4: build the owner's blind pack (projects/s5_blind/, gitignored).

For each of the 10 scenes:
  * take that scene's image from each of the 3 models,
  * shuffle them into 3 panels labelled A / B / C (random order per scene,
    deterministic for a given salt so the pack can be rebuilt),
  * lay the panels side by side at <= 1600 px wide (phone-readable),
  * write the panel -> model mapping to projects/s5_blind/mapping.json, which
    lives beside the sheets but is never part of what the owner looks at.

Also writes:
  results.csv   template the owner fills (scene,best_panel,worst_panel,comment,
                anatomy_ok_A,anatomy_ok_B,anatomy_ok_C)
  INSTRUCTIONS.txt  what to do on a phone, in plain words

Usage:
  python scripts/s5_blind_pack.py --root /tmp/kilo/s5_out
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
PANEL = 512
GAP = 8
LABEL_H = 56
MARGIN = 8
MAX_WIDTH = 1600
MODEL_ORDER = ["sdxl", "zimage", "klein"]
CSV_HEADER = ("scene,best_panel,worst_panel,comment,"
              "anatomy_ok_A,anatomy_ok_B,anatomy_ok_C")


def _font(size: int = 40):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def panel_order(scene: str, salt: str = "s5") -> List[str]:
    """Random-but-reproducible model order for one scene -> ['A','B','C'] models."""
    digest = hashlib.sha256(f"{salt}:{scene}".encode()).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    models = MODEL_ORDER[:]
    rng.shuffle(models)
    return models


def build_sheet(images: Dict[str, Path], order: Dict[str, str],
                out_path: Path) -> tuple[int, int]:
    """Compose one comparison sheet; returns (width, height)."""
    width = MARGIN + 3 * PANEL + 2 * GAP + MARGIN
    if width > MAX_WIDTH:
        raise ValueError(f"sheet width {width} exceeds {MAX_WIDTH}")
    height = MARGIN + LABEL_H + PANEL + MARGIN
    sheet = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    font = _font(40)
    for i, label in enumerate("ABC"):
        model = order[label]
        x = MARGIN + i * (PANEL + GAP)
        with Image.open(images[model]) as im:
            panel = im.convert("RGB").resize((PANEL, PANEL), Image.LANCZOS)
        sheet.paste(panel, (x, MARGIN + LABEL_H))
        draw.text((x + 8, MARGIN + 4), label, fill=(0, 0, 0), font=font)
        draw.rectangle([x - 1, MARGIN + LABEL_H - 1,
                        x + PANEL, MARGIN + LABEL_H + PANEL],
                       outline=(200, 200, 200))
    sheet.save(out_path, optimize=True)
    return sheet.size


def collect(root: Path) -> tuple[Dict[str, Dict[str, Path]], Dict[str, Any]]:
    """(scene -> {model: image}, model metrics) from the kernel manifests."""
    by_scene: Dict[str, Dict[str, Path]] = {}
    metrics: Dict[str, Any] = {}
    manifests = sorted(root.glob("s5_bakeoff_*/manifest.json"))
    if not manifests:
        raise SystemExit(f"no s5_bakeoff_*/manifest.json under {root}")
    for mp in manifests:
        man = json.loads(mp.read_text(encoding="utf-8"))
        model = man["model"]
        metrics[model] = {
            "load_seconds": man.get("load_seconds"),
            "steady_state_sec_per_image": man.get("steady_state_sec_per_image"),
            "mean_sec_per_image": man.get("mean_sec_per_image"),
            "peak_vram_mb": man.get("peak_vram_mb"),
            "black_count": man.get("black_count"),
            "nan_count": man.get("nan_count"),
            "oom_count": man.get("oom_count"),
            "pipeline_class": man.get("pipeline_class"),
            "versions": man.get("versions"),
        }
        img_dir = mp.parent / "images"
        for entry in man.get("images", []):
            if not entry.get("file"):
                continue
            if entry.get("variant") == "N":
                continue  # neutral fairness-check images are packed separately
            path = img_dir / entry["file"]
            if path.is_file():
                by_scene.setdefault(entry["scene_id"], {})[model] = path
    return by_scene, metrics


def write_csv_template(out_dir: Path, scenes: List[str]) -> Path:
    p = out_dir / "results.csv"
    lines = [CSV_HEADER]
    for s in scenes:
        lines.append(f"{s},,,,,,")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def instructions(scenes: List[str]) -> str:
    return (
        "S5 blind pack — how to review (5-10 minutes)\n"
        "=============================================\n\n"
        "1. Open sheet_s01.png ... sheet_s12.png on your phone (10 sheets).\n"
        "   Each sheet shows the SAME scene from the 3 models, panels A / B / C,\n"
        "   in a different random order on every sheet. Model names are not\n"
        "   shown anywhere on the sheets.\n\n"
        "2. On each sheet decide:\n"
        "   - best_panel: the panel you would actually use\n"
        "   - worst_panel: the panel you would throw away\n"
        "   - anatomy_ok_X: for EACH panel, yes if the creature's limbs / eyes /\n"
        "     horns look like the brief (6 limbs, 2 eyes, 0 horns for the vent\n"
        "     grazer; no limbs + a wide filter mouth for the filter drifter;\n"
        "     no limbs + segmented body for the ice burrower) and no obvious\n"
        "     extra/missing limbs, fused bodies or duplicated subjects.\n"
        "   - comment: optional, one short line (what is wrong / what works).\n\n"
        "3. Fill results.csv in any CSV editor or spreadsheet. Allowed values:\n"
        "   best_panel / worst_panel: A, B or C (worst may be left empty)\n"
        "   anatomy_ok_A/B/C: yes or no\n"
        "   Do not edit the scene column.\n\n"
        "4. Then run:  python scripts/s5_tally.py\n"
        "   It prints wins / losses / anatomy-ok per model plus the speed and\n"
        "   VRAM table, says TIE when the best two are within 1 win, and names a\n"
        "   recommended model purely from your CSV.\n\n"
        "Notes\n"
        "-----\n"
        "- mapping.json (which panel is which model) is in this folder. Do not\n"
        "  open it until after you have filled the CSV, or the test is no longer\n"
        "  blind.\n"
        "- sheet_*_neutral.png are the fairness check: the same prompt text was\n"
        "  given to all three models, so those sheets test the model, not the\n"
        "  prompt format. Same rules, just for information.\n"
        f"- Scenes: {', '.join(scenes)}\n"
    )


def run(root: Path, out_dir: Path, salt: str = "s5") -> Dict[str, Any]:
    by_scene, metrics = collect(root)
    scenes = sorted(by_scene)
    complete = [s for s in scenes if len(by_scene[s]) == 3]
    partial = [s for s in scenes if len(by_scene[s]) < 3]

    out_dir.mkdir(parents=True, exist_ok=True)
    mapping: Dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "S5",
        "salt": salt,
        "scenes": {},
        "model_metrics": metrics,
        "sheets": [],
        "partial_scenes": partial,
    }
    for scene in complete:
        order = {label: model for label, model in zip("ABC", panel_order(scene, salt))}
        sheet_path = out_dir / f"sheet_{scene}.png"
        size = build_sheet(by_scene[scene], order, sheet_path)
        mapping["scenes"][scene] = order
        mapping["sheets"].append({"scene": scene, "file": sheet_path.name,
                                  "width": size[0], "height": size[1]})

    write_csv_template(out_dir, complete)
    (out_dir / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n",
                                          encoding="utf-8")
    (out_dir / "INSTRUCTIONS.txt").write_text(instructions(complete), encoding="utf-8")
    return mapping


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="/tmp/kilo/s5_out")
    ap.add_argument("--out", default=str(REPO / "projects/s5_blind"))
    ap.add_argument("--salt", default="s5")
    args = ap.parse_args(argv)
    m = run(Path(args.root), Path(args.out), args.salt)
    print(f"sheets: {len(m['sheets'])} in {args.out}")
    if m["partial_scenes"]:
        print(f"PARTIAL scenes (missing a model, no sheet): {m['partial_scenes']}")
    print("owner fills results.csv, then: python scripts/s5_tally.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
