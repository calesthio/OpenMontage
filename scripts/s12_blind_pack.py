#!/usr/bin/env python3
"""S12: build the owner's blind bake-off pack in projects/s12_blind/.

One sheet per scene+seed (6 scenes x 3 seeds = 18 sheets). Each sheet shows
the SAME scene+seed rendered by the three models, one panel per model, in a
different random order on every sheet. Panels are coded `<letter><sheet>`
(e.g. A3, B3, C3) - the letter is a fresh shuffle per sheet, so you cannot
learn "A is always model X". No model name, no model id, no ranking appears
anywhere on a sheet.

Two files per sheet:
  s12_sheet_<nn>.png           plain, with a dashed caption-safe-zone overlay
  s12_sheet_<nn>_caption.png   same panels with plain white subtitle text
                               burned into the bottom band

Nothing here judges anatomy, quality or "usability": those are the owner's
blind call, recorded in results.csv.

Usage:
  python scripts/s12_blind_pack.py \
      --out projects/s12_blind --salt s12
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs/openmontage/image_gen"
OUT_ROOT = Path("/tmp/kilo/s12_out")

PANEL = 400          # phone-sized panel: 3 x 400 + gaps = 1232 px sheet
GAP = 8
LABEL_H = 56
MARGIN = 8
HEADER_H = 34
MAX_WIDTH = 1280
LABELS = "ABC"
CAPTION_BAND_FRACTION = 0.28

SCENES = ["s01", "s03", "s05", "s06", "s10", "s12"]
SEEDS = [1001, 2027, 4409]
CAPTIONS: Dict[str, str] = {
    "s01": "The vent grazer crops bacterial mats at the chimney rim.",
    "s03": "Filter drifters sieve microbes from the open water column.",
    "s05": "Chimney fields vent mineral-rich water onto the sea floor.",
    "s06": "Melt pools glow beneath the frozen ice shell.",
    "s10": "Chemosynthetic bacteria feed the whole vent food web.",
    "s12": "Plumes break through the ice crust of the frozen ocean world.",
}
#: Scenes whose subject has a checkable part count (limbs/eyes/horns).
PART_COUNT_SCENES = {"s01": "6 limbs, 2 eyes, 0 horns",
                     "s03": "0 limbs, 0 eyes, 0 horns",
                     "s10": "6 limbs, 2 eyes, 0 horns"}

CSV_FIELDS = [
    "sheet", "scene", "seed", "best_panel", "worst_panel",
    "anatomy_ok_A", "anatomy_ok_B", "anatomy_ok_C",
    "usable_A", "usable_B", "usable_C",
    "caption_space_A", "caption_space_B", "caption_space_C",
    "comment",
]

_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


def _font(size: int):
    for path in _FONTS:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def panel_order(scene: str, seed: int, models: Sequence[str],
                salt: str = "s12") -> List[str]:
    digest = hashlib.sha256(f"{salt}:{scene}:{seed}".encode()).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    order = list(models)
    rng.shuffle(order)
    return order


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
    lines: List[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_caption(draw, text: str, width: int):
    for size in (32, 28, 24, 20):
        font = _font(size)
        lines = _wrap(draw, text, font, width - 16)
        if len(lines) <= 3:
            return font, lines, size
    font = _font(20)
    return font, _wrap(draw, text, font, width - 16)[:3], 20


def build_sheet(images: Dict[str, Path], model_ids: Dict[str, str],
                scene: str, seed: int, sheet_no: int, order: Dict[str, str],
                out_path: Path, caption: Optional[str] = None) -> Dict[str, Any]:
    width = MARGIN + len(LABELS) * PANEL + (len(LABELS) - 1) * GAP + MARGIN
    if width > MAX_WIDTH:
        raise ValueError(f"sheet width {width} exceeds {MAX_WIDTH}")
    height = HEADER_H + LABEL_H + PANEL + MARGIN
    sheet = Image.new("RGB", (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    head_font = _font(20)
    label_font = _font(30)
    boxes: Dict[str, List[int]] = {}

    draw.text((MARGIN, 6),
              f"Sheet {sheet_no}  |  scene {scene}  |  seed {seed}  |  "
              f"judge anatomy, usability and caption space per panel",
              fill=(20, 20, 20), font=head_font)

    for i, label in enumerate(LABELS):
        model = order[label]
        code = f"{label}{sheet_no}"
        x = MARGIN + i * (PANEL + GAP)
        y = HEADER_H + LABEL_H
        with Image.open(images[model]) as im:
            tile = im.convert("RGB").resize((PANEL, PANEL), Image.LANCZOS)
        sheet.paste(tile, (x, y))
        draw.text((x + 6, HEADER_H + 8), code, fill=(0, 0, 0), font=label_font)
        draw.rectangle([x - 1, y - 1, x + PANEL, y + PANEL],
                       outline=(170, 170, 170))
        boxes[code] = [x, y, x + PANEL, y + PANEL]

    band_px = int(round(PANEL * CAPTION_BAND_FRACTION))
    if caption is None:
        # dashed overlay: where a caption would sit
        for code in boxes:
            x0, y0, x1, y1 = boxes[code]
            top = y1 - band_px
            for xx in range(x0, x1, 14):
                draw.line([(xx, top), (min(xx + 7, x1), top)],
                          fill=(255, 255, 255), width=2)
            draw.text((x0 + 6, top + 4), "caption zone", fill=(255, 255, 255),
                      font=_font(18))
        caption_meta = {"text": None, "mode": "dashed_zone", "band_px": band_px}
    else:
        font, lines, size = _fit_caption(draw, caption, PANEL)
        line_h = int(round(size * 1.18))
        block_h = line_h * len(lines)
        for code in boxes:
            x0, _y0, x1, y1 = boxes[code]
            top = y1 - block_h - 10
            for n, line in enumerate(lines):
                tw = draw.textlength(line, font=font)
                draw.text((x0 + (PANEL - tw) / 2, top + n * line_h), line,
                          fill=(255, 255, 255), font=font)
        caption_meta = {"text": caption, "mode": "burned", "font_px": size,
                        "lines": lines, "band_px": band_px}

    sheet.save(out_path, optimize=True)
    return {
        "file": out_path.name,
        "sheet_no": sheet_no,
        "scene": scene,
        "seed": seed,
        "width": width,
        "height": height,
        "panel": PANEL,
        "panel_boxes": boxes,
        "caption": caption_meta,
        "codes": {f"{label}{sheet_no}": {"model_key": order[label],
                                         "model_id": model_ids[order[label]]}
                  for label in LABELS},
    }


def gather() -> Tuple[Dict[str, Dict[Tuple[str, int], Path]],
                      Dict[str, str]]:
    """model_key -> {(scene, seed): png}, plus model_key -> model_id."""
    images: Dict[str, Dict[Tuple[str, int], Path]] = {}
    model_ids: Dict[str, str] = {}
    for summary_path in sorted(DOCS.glob("S12_MODEL_*.json")):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        key = summary["model_key"]
        man_path = Path(summary["images_dir"]).parent / "manifest.json"
        if not man_path.is_file():
            raise SystemExit(f"BLOCKED: {key}: missing {man_path}")
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
        model_ids[key] = manifest.get("model_id") or summary["model_id"]
        slot: Dict[Tuple[str, int], Path] = {}
        for entry in manifest.get("images", []):
            if not entry.get("file"):
                continue
            p = Path(summary["images_dir"]) / entry["file"]
            if not p.is_file():
                raise SystemExit(f"BLOCKED: {key}: missing {p}")
            slot[(entry["scene_id"], int(entry["seed"]))] = p
        images[key] = slot
    if len(images) != 3:
        raise SystemExit(f"BLOCKED: need all 3 models collected, have "
                         f"{sorted(images)}")
    for key, slot in images.items():
        need = {(s, sd) for s in SCENES for sd in SEEDS}
        missing = need - set(slot)
        if missing:
            raise SystemExit(f"BLOCKED: {key} missing {sorted(missing)}")
    return images, model_ids


def run(out_dir: Path, salt: str = "s12") -> Dict[str, Any]:
    images, model_ids = gather()
    models = sorted(images)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mapping: Dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "S12",
        "salt": salt,
        "note": "BLIND: this file unblinds the sheets. Do not open it before "
                "results.csv is filled.",
        "layout": {"panel": PANEL, "gap": GAP, "label_height": LABEL_H,
                   "margin": MARGIN, "header_height": HEADER_H,
                   "max_width": MAX_WIDTH},
        "caption_band_fraction": CAPTION_BAND_FRACTION,
        "panels_per_sheet": 3,
        "sheets": [],
        "codes": {},
        "model_ids": model_ids,
    }
    rows: List[Dict[str, Any]] = []
    sheet_no = 0
    for scene in SCENES:
        for seed in SEEDS:
            sheet_no += 1
            order = dict(zip(LABELS, panel_order(scene, seed, models, salt)))
            picked = {label: images[order[label]][(scene, seed)]
                      for label in LABELS}
            stem = f"s12_sheet_{sheet_no:02d}"
            plain = build_sheet(picked, model_ids, scene, seed, sheet_no, order,
                                out_dir / f"{stem}.png", caption=None)
            capt = build_sheet(picked, model_ids, scene, seed, sheet_no, order,
                               out_dir / f"{stem}_caption.png",
                               caption=CAPTIONS[scene])
            mapping["sheets"].append({
                "sheet_no": sheet_no,
                "scene": scene,
                "seed": seed,
                "plain": plain["file"],
                "captioned": capt["file"],
                "parts_expected": PART_COUNT_SCENES.get(scene),
                "caption": capt["caption"],
                "codes": {code: order[code] for code in
                          (f"{l}{sheet_no}" for l in LABELS)},
            })
            for label in LABELS:
                code = f"{label}{sheet_no}"
                mapping["codes"][code] = {
                    "model_key": order[label],
                    "model_id": model_ids[order[label]],
                    "scene": scene,
                    "seed": seed,
                    "panel_box": plain["panel_boxes"][code],
                    "file": images[order[label]][(scene, seed)].name,
                }
            rows.append({f: "" for f in CSV_FIELDS} | {
                "sheet": f"{sheet_no:02d}", "scene": scene, "seed": seed})

    _write_csv(out_dir / "results.csv", rows)
    (out_dir / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n",
                                          encoding="utf-8")
    (out_dir / "INSTRUCTIONS.txt").write_text(_instructions(), encoding="utf-8")
    return mapping


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    import csv as _csv
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})


def _instructions() -> str:
    return """S12 model bake-off - how to review on a phone (15-20 minutes)
================================================================

18 sheets. Every sheet is ONE scene + ONE seed rendered by THREE different
models - coded A<n>, B<n>, C<n> (n = sheet number). The letter order is
shuffled on every sheet, there are no model names on the sheets, and the
mapping is in mapping.json - do NOT open it until results.csv is filled.

For every panel on every sheet, three yes/no calls:

1. anatomy_ok_<panel>   Does the image show the part count the scene asks for?
                        (shown per scene below; for habitat / wide scenes with
                        no creature, mark yes if the scene's subject is
                        recognisably there and nothing extra was invented.)
2. usable_<panel>       Would you put it on screen as-is, without repairing
                        limbs, faces, seams or stray objects?
3. caption_space_<panel> Is there calm, uncluttered space where a subtitle can
                        sit without fighting the art? Check BOTH variants: the
                        plain sheet has a dashed caption zone, the _caption
                        sheet has the real caption burned in.

Then best_panel / worst_panel per sheet: which of the three you would use for
this channel, and which you would discard. comment: optional, short.

Part counts the creature scenes ask for:
  s01  vent grazer    6 limbs, 2 eyes, 0 horns
  s03  filter drifter 0 limbs, 0 eyes, 0 horns
  s10  food-web plate 6 limbs, 2 eyes, 0 horns (the grazer)
  s05, s06, s12       no creature: habitats and a wide scene

Allowed values: yes / no (lowercase is fine). Do not edit sheet/scene/seed.

When the CSV is complete:
  python scripts/s12_tally.py
It prints per-model anatomy / usable / caption-space counts, the pass gates,
wins and losses, and sec-per-accepted-image. It refuses to name a model while
the CSV is incomplete.

Files
-----
  s12_sheet_<nn>.png          plain, dashed caption-safe-zone overlay
  s12_sheet_<nn>_caption.png  same panels, white subtitle burned in
  results.csv                 fill this
  mapping.json                DO NOT OPEN until results.csv is filled
"""


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO / "projects/s12_blind"))
    ap.add_argument("--salt", default="s12")
    args = ap.parse_args(argv)
    mapping = run(Path(args.out), args.salt)
    print(f"sheets: {len(mapping['sheets'])} (plain + captioned) in {args.out}")
    print("owner fills results.csv, then: python scripts/s12_tally.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
