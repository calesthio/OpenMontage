#!/usr/bin/env python3
"""S7-7: build the owner's blind pack (projects/s7_blind/, gitignored).

For each of the 10 scenes:
  * take that scene's image from each of the 3 models,
  * shuffle them into 3 panels labelled A / B / C (random order per scene,
    reproducible from a salt so the pack can be rebuilt),
  * lay the panels side by side at <= 1600 px wide (phone-readable),
  * write the panel -> model mapping to projects/s7_blind/mapping.json.

The sheets carry NO model names and NO agent ranking — the owner sees only
A / B / C.

Also writes:
  results.csv       template the owner fills
                    (scene,best_panel,worst_panel,anatomy_ok_A,anatomy_ok_B,
                     anatomy_ok_C,comment)
  INSTRUCTIONS.txt  what to do on a phone, in plain words

Usage:
  python scripts/s7_blind_pack.py --root /tmp/kilo/s7_out
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
MODEL_ORDER = ["sdxl", "klein", "zimage"]
CSV_HEADER = ("scene,best_panel,worst_panel,anatomy_ok_A,anatomy_ok_B,"
              "anatomy_ok_C,comment")


def _font(size: int = 40):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def panel_order(scene: str, salt: str = "s7",
                models: Optional[List[str]] = None) -> List[str]:
    """Random-but-reproducible model order for one scene.

    With three models the panels are A/B/C; with a blocked model only the
    models that actually produced frames are compared, so the owner still
    gets a blind choice between the models that worked.
    """
    digest = hashlib.sha256(f"{salt}:{scene}".encode()).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    order = list(models) if models else MODEL_ORDER[:]
    rng.shuffle(order)
    return order


def build_sheet(images: Dict[str, Path], order: Dict[str, str],
                out_path: Path) -> tuple[int, int]:
    """Compose one comparison sheet; returns (width, height).

    Every model in `order` gets a panel: with 4 or 5 models the panel shrinks
    so the sheet stays inside MAX_WIDTH (1600 px, phone-friendly). Dropping a
    panel would silently blind the owner to a model.
    """
    labels = "ABCDE"[:len(order)]
    if len(labels) != len(order):
        raise ValueError(f"cannot show {len(order)} panels on one sheet")
    panel = min(PANEL, (MAX_WIDTH - 2 * MARGIN - (len(labels) - 1) * GAP)
                // len(labels))
    width = MARGIN + len(labels) * panel + (len(labels) - 1) * GAP + MARGIN
    if width > MAX_WIDTH:
        raise ValueError(f"sheet width {width} exceeds {MAX_WIDTH}")
    height = MARGIN + LABEL_H + panel + MARGIN
    sheet = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    font = _font(40)
    for i, label in enumerate(labels):
        model = order[label]
        x = MARGIN + i * (panel + GAP)
        with Image.open(images[model]) as im:
            tile = im.convert("RGB").resize((panel, panel), Image.LANCZOS)
        sheet.paste(tile, (x, MARGIN + LABEL_H))
        draw.text((x + 8, MARGIN + 4), label, fill=(0, 0, 0), font=font)
        draw.rectangle([x - 1, MARGIN + LABEL_H - 1,
                        x + panel, MARGIN + LABEL_H + panel],
                       outline=(200, 200, 200))
    sheet.save(out_path, optimize=True)
    return sheet.size


def collect(root: Path) -> tuple[Dict[str, Dict[str, Path]], Dict[str, Any]]:
    """(scene -> {model: image}, model metrics) from the kernel manifests."""
    by_scene: Dict[str, Dict[str, Path]] = {}
    metrics: Dict[str, Any] = {}
    manifests = sorted(root.glob("s7_bakeoff_*/manifest.json"))
    if not manifests:
        raise SystemExit(f"no s7_bakeoff_*/manifest.json under {root}")
    for mp in manifests:
        man = json.loads(mp.read_text(encoding="utf-8"))
        model = man["model"]
        metrics[model] = {
            "job_id": man.get("job_id"),
            "load_seconds": man.get("load_seconds"),
            "steady_state_sec_per_image": man.get("steady_state_sec_per_image"),
            "mean_sec_per_image": man.get("mean_sec_per_image"),
            "usable_images_per_minute": man.get("usable_images_per_minute"),
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
            path = img_dir / entry["file"]
            if path.is_file():
                by_scene.setdefault(entry["scene_id"], {})[model] = path
    return by_scene, metrics


def csv_header(n_panels: int, with_second_best: bool = False) -> str:
    labels = "ABCDE"[:n_panels]
    cols = ["scene", "best_panel"]
    if with_second_best:
        cols.append("second_best")
    cols += ["worst_panel"]
    cols += [f"anatomy_ok_{l}" for l in labels] + ["comment"]
    return ",".join(cols)


def write_csv_template(out_dir: Path, scenes: List[str], n_panels: int = 3,
                       with_second_best: bool = False) -> Path:
    p = out_dir / "results.csv"
    lines = [csv_header(n_panels, with_second_best)]
    for s in scenes:
        lines.append(f"{s},,,,,,")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def instructions(scenes: List[str], n_panels: int = 3,
                 blocked_note: str = "", with_second_best: bool = False) -> str:
    panel_list = list("ABCDE"[:n_panels])
    labels = " / ".join(panel_list)
    return (
        "S7 blind pack - how to review (5-10 minutes)\n"
        "===========================================\n\n"
        f"1. Open sheet_{scenes[0]}.png ... on your phone ({len(scenes)} sheets).\n"
        f"   Each sheet shows the SAME scene drawn by {n_panels} different models,\n"
        f"   panels {labels}, in a different random order on every sheet.\n"
        "   No model names are shown anywhere on the sheets.\n\n"
        "2. On each sheet decide:\n"
        "   - best_panel: the panel you would actually use\n"
        "   - worst_panel: the panel you would throw away\n"
        + ("   - second_best: the runner-up panel for this scene\n"
           if with_second_best else "")
        + f"   - anatomy_ok_<panel>: for EACH panel, yes if the creature's limbs /\n"
        "     eyes / horns match the scene brief and there are no obvious extra /\n"
        "     missing limbs, fused bodies, duplicated heads or duplicated subjects.\n"
        "   - comment: optional, one short line (what is wrong / what works).\n\n"
        "3. Fill results.csv in any CSV editor or spreadsheet. Allowed values:\n"
        f"   best_panel / worst_panel: {' or '.join(panel_list)} "
        "(worst may be left empty)\n"
        f"   anatomy_ok_<panel>: yes or no (one column per panel: "
        f"{', '.join('anatomy_ok_' + l for l in panel_list)})\n"
        "   Do not edit the scene column.\n\n"
        "4. Then run:  python scripts/s7_tally.py\n"
        "   It prints wins / losses / anatomy-ok per model plus the speed and\n"
        "   VRAM table, and compares your result with the agent's advisory pick.\n\n"
        "Notes\n"
        "-----\n"
        "- mapping.json (which panel is which model) is in this folder. Do not\n"
        "  open it until after you have filled the CSV, or the test is no longer\n"
        "  blind.\n"
        f"- Scenes: {', '.join(scenes)}\n"
        + (f"- {blocked_note}\n" if blocked_note else "")
    )


def run(root: Path, out_dir: Path, salt: str = "s7",
        blocked_note: str = "", with_second_best: bool = False) -> Dict[str, Any]:
    by_scene, metrics = collect(root)
    scenes = sorted(by_scene)
    # Only the models that produced a frame for EVERY scene are compared, so a
    # blocked model never shows up as an empty/black panel.
    common: set = set.intersection(*[set(v) for v in by_scene.values()]) \
        if by_scene else set()
    pack_models = [m for m in MODEL_ORDER if m in common] + \
        sorted(common - set(MODEL_ORDER))
    complete = [s for s in scenes if set(by_scene[s]) == set(pack_models)]
    partial = [s for s in scenes if set(by_scene[s]) != set(pack_models)]

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mapping: Dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "S7",
        "salt": salt,
        "pack_models": pack_models,
        "blocked_note": blocked_note,
        "note": "BLIND: this file unblinds the sheets. The owner must not open "
                "it before filling results.csv.",
        "scenes": {},
        "model_metrics": metrics,
        "sheets": [],
        "partial_scenes": partial,
    }
    # one panel per compared model: A/B for 2 models, A..E for 5
    panel_labels = list("ABCDE"[:len(pack_models)])
    for scene in complete:
        order = {label: model for label, model
                 in zip(panel_labels, panel_order(scene, salt, pack_models))}
        sheet_path = out_dir / f"sheet_{scene}.png"
        size = build_sheet(by_scene[scene], order, sheet_path)
        mapping["scenes"][scene] = order
        mapping["sheets"].append({"scene": scene, "file": sheet_path.name,
                                  "width": size[0], "height": size[1]})

    write_csv_template(out_dir, complete, len(pack_models), with_second_best)
    (out_dir / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n",
                                          encoding="utf-8")
    (out_dir / "INSTRUCTIONS.txt").write_text(
        instructions(complete, len(pack_models), blocked_note,
                     with_second_best), encoding="utf-8")
    return mapping


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="/tmp/kilo/s7_out")
    ap.add_argument("--out", default=str(REPO / "projects/s7_blind"))
    ap.add_argument("--salt", default="s7")
    ap.add_argument("--blocked-note", default="",
                    help="one line naming a model that could not produce frames")
    ap.add_argument("--with-second-best", action="store_true",
                    help="add a second_best column to the CSV template (S8)")
    args = ap.parse_args(argv)
    m = run(Path(args.root), Path(args.out), args.salt, args.blocked_note,
            args.with_second_best)
    print(f"sheets: {len(m['sheets'])} in {args.out}")
    if m["partial_scenes"]:
        print(f"PARTIAL scenes (missing a model, no sheet): {m['partial_scenes']}")
    print("owner fills results.csv, then: python scripts/s7_tally.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
