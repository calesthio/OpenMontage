#!/usr/bin/env python3
"""S15: build the owner's blind pack for the 42 style-lock images.

Design:
  * every image gets a coded tile K1..K42; the code -> image assignment is
    randomised (seeded salt) and lives ONLY in mapping.json;
  * square sheets: 6 tiles per sheet (2 x 3) at 520 px, sheets are phone-sized;
  * wide (16:9) images: 2 tiles per sheet stacked at full sheet width;
  * every tile carries the CAPTION-ZONE overlay (translucent band over the
    bottom fifth) and a second "_captioned" variant burns a sample subtitle
    into that band so legibility can be judged on a phone;
  * no style, seed, model or scene name appears in any file name or tile label.

Outputs (default projects/s15/blind/, gitignored):
  sheets/sheet_01.png ...             plain sheets with the caption-zone band
  sheets/sheet_01_captioned.png ...   same sheets + sample caption text
  mapping.json                        code -> style/scene/seed (SEALED)
  scoring.csv                         owner's scoring template
  INSTRUCTIONS.txt                    how to score on a phone

Usage:
  python scripts/s15_blind_pack.py \
      --manifest /tmp/kilo/s15_out/s15-style-lock-1/s15_style_lock_dreamshaper-xl-1-0/manifest.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = Path(
    "/tmp/kilo/s15_out/s15-style-lock-1/s15_style_lock_dreamshaper-xl-1-0/"
    "manifest.json")
OUT_DIR = REPO / "projects/s15/blind"

SALT = "s15"
SQUARE_TILE = 520
WIDE_WIDTH = 1040
GAP = 8
MARGIN = 8
LABEL_H = 40
SQUARE_PER_SHEET = 6
WIDE_PER_SHEET = 2
CAPTION_BAND_FRACTION = 0.20      # the bottom fifth the prompt reserves
COLUMNS = 2

CAPTIONS: Dict[str, str] = {
    "s01": "The vent grazer crops bacterial mats at the chimney rim.",
    "s03": "Filter drifters sieve microbes from the open water column.",
    "s05": "Chimney fields vent mineral-rich water onto the sea floor.",
    "s06": "Melt pools glow beneath the frozen ice shell.",
    "s10": "Chemosynthetic bacteria feed the whole vent food web.",
    "s12": "Plumes break through the ice crust of the frozen ocean world.",
}

SCORING_HEADER = ["code", "scene", "anatomy_ok", "caption_space_ok",
                  "readability_1_5", "notes"]

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


def _font(size: int):
    for path in _FONT_CANDIDATES:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_caption(draw: ImageDraw.ImageDraw, text: str, width: int) -> Tuple[Any, List[str], int]:
    for size in (34, 30, 26, 22, 18):
        font = _font(size)
        lines = _wrap(draw, text, font, width - 24)
        if len(lines) <= 2:
            return font, lines, size
    font = _font(18)
    return font, _wrap(draw, text, font, width - 24)[:2], 18


def _load_tiles(manifest: Dict[str, Any], images_dir: Path) -> List[Dict[str, Any]]:
    tiles: List[Dict[str, Any]] = []
    for entry in manifest.get("images", []):
        f = entry.get("file")
        if not f:
            raise SystemExit(f"BLOCKED: render without file: {entry.get('render_id')}")
        path = images_dir / f
        if not path.is_file():
            raise SystemExit(f"BLOCKED: image missing on disk: {path}")
        tiles.append({
            "render_id": entry["render_id"],
            "file": f,
            "path": str(path),
            "style": entry.get("style"),
            "scene": entry.get("scene_id"),
            "seed": entry.get("seed"),
            "width": entry.get("width"),
            "height": entry.get("height"),
        })
    if len(tiles) != 42:
        raise SystemExit(f"BLOCKED: {len(tiles)} images, expected 42")
    return tiles


def _assign_codes(tiles: List[Dict[str, Any]], salt: str = SALT) -> List[Dict[str, Any]]:
    digest = hashlib.sha256(f"{salt}:order".encode()).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    order = list(tiles)
    rng.shuffle(order)
    for i, tile in enumerate(order, start=1):
        tile["code"] = f"K{i}"
    return order


def _draw_tile(sheet: Image.Image, draw: ImageDraw.ImageDraw, tile: Dict[str, Any],
               x: int, y: int, w: int, h: int, text: Optional[str]) -> List[int]:
    with Image.open(tile["path"]) as im:
        src = im.convert("RGB")
        # fit inside the tile box, letterbox with a neutral grey
        scale = min(w / src.width, h / src.height)
        nw, nh = max(1, int(round(src.width * scale))), max(1, int(round(src.height * scale)))
        fitted = src.resize((nw, nh), Image.LANCZOS)
    box = Image.new("RGB", (w, h), (232, 230, 226))
    ox, oy = x + (w - nw) // 2, y + (h - nh) // 2
    box.paste(fitted, (ox - x, oy - y))
    sheet.paste(box, (x, y))

    # caption-zone overlay: translucent band over the bottom fifth of the IMAGE
    band_h = max(8, int(round(nh * CAPTION_BAND_FRACTION)))
    band_top = oy + nh - band_h
    overlay = Image.new("RGBA", (nw, band_h), (12, 22, 30, 96))
    sheet.paste(Image.alpha_composite(
        sheet.crop((ox, band_top, ox + nw, band_top + band_h)).convert("RGBA"),
        overlay).convert("RGB"), (ox, band_top))
    draw.rectangle([ox, band_top, ox + nw - 1, band_top + band_h - 1],
                   outline=(255, 255, 255))
    if text:
        font, lines, size = _fit_caption(draw, text, nw)
        line_h = int(round(size * 1.18))
        block_h = line_h * len(lines)
        top = band_top + max(2, (band_h - block_h) // 2)
        for n, line in enumerate(lines):
            tw = draw.textlength(line, font=font)
            tx = ox + (nw - tw) / 2
            ty = top + n * line_h
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                draw.text((tx + dx, ty + dy), line, fill=(0, 0, 0), font=font)
            draw.text((tx, ty), line, fill=(255, 255, 255), font=font)
    draw.rectangle([x, y, x + w - 1, y + h - 1], outline=(190, 190, 190))
    return [ox, band_top, ox + nw, band_top + band_h]


def _build_sheet(tiles: List[Dict[str, Any]], out_path: Path, mode: str,
                 square: bool) -> Dict[str, Any]:
    label_font = _font(28)
    if square:
        w = MARGIN * 2 + COLUMNS * SQUARE_TILE + (COLUMNS - 1) * GAP
        rows = (len(tiles) + COLUMNS - 1) // COLUMNS
        h = MARGIN * 2 + rows * (SQUARE_TILE + LABEL_H) + (rows - 1) * GAP
        tile_w = tile_h = SQUARE_TILE
    else:
        w = MARGIN * 2 + WIDE_WIDTH
        tile_w, tile_h = WIDE_WIDTH, int(round(WIDE_WIDTH * 9 / 16))
        rows = len(tiles)
        h = MARGIN * 2 + rows * (tile_h + LABEL_H) + (rows - 1) * GAP

    sheet = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    boxes: Dict[str, List[int]] = {}
    for idx, tile in enumerate(tiles):
        r, c = divmod(idx, COLUMNS) if square else (idx, 0)
        x = MARGIN + c * (tile_w + GAP)
        y = MARGIN + r * (tile_h + LABEL_H + GAP)
        draw.text((x + 4, y + 4), tile["code"], fill=(0, 0, 0), font=label_font)
        caption = CAPTIONS.get(tile["scene"], "") if mode == "captioned" else None
        boxes[tile["code"]] = _draw_tile(
            sheet, draw, tile, x, y + LABEL_H, tile_w, tile_h, caption)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, optimize=True)
    return {"file": out_path.name, "width": w, "height": h,
            "caption_boxes": boxes}


def run(manifest_path: Path, out_dir: Path) -> Dict[str, Any]:
    man = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    tiles = _load_tiles(man, Path(manifest_path).parent / "images")
    ordered = _assign_codes(tiles)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "sheets").mkdir(parents=True, exist_ok=True)

    square = [t for t in ordered if t["width"] == t["height"]]
    wide = [t for t in ordered if t["width"] != t["height"]]

    mapping: Dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "S15",
        "salt": SALT,
        "job_id": man.get("job_id"),
        "model": man.get("model"),
        "model_id": man.get("model_id"),
        "revision": man.get("model_revision"),
        "sealed_note": "BLIND: this file unblinds the sheets. Do not open it "
                       "until scoring.csv is complete.",
        "caption_band_fraction": CAPTION_BAND_FRACTION,
        "layout": {"square_tile": SQUARE_TILE, "wide_width": WIDE_WIDTH,
                   "columns": COLUMNS, "square_per_sheet": SQUARE_PER_SHEET,
                   "wide_per_sheet": WIDE_PER_SHEET},
        "tiles": {},
        "sheets": [],
    }

    def add_sheet(group: List[Dict[str, Any]], idx: int, square_flag: bool
                  ) -> None:
        name = f"sheet_{idx:02d}"
        plain = _build_sheet(group, out_dir / "sheets" / f"{name}.png",
                             mode="plain", square=square_flag)
        cap = _build_sheet(group, out_dir / "sheets" / f"{name}_captioned.png",
                           mode="captioned", square=square_flag)
        tile_codes = {}
        for t in group:
            mapping["tiles"][t["code"]] = {
                "style": t["style"], "scene": t["scene"], "seed": t["seed"],
                "render_id": t["render_id"], "file": t["file"],
                "size": f"{t['width']}x{t['height']}",
                "caption_text": CAPTIONS.get(t["scene"], ""),
                "caption_box": plain["caption_boxes"][t["code"]],
            }
            tile_codes[t["code"]] = t["code"]
        mapping["sheets"].append({
            "plain": f"sheets/{plain['file']}",
            "captioned": f"sheets/{cap['file']}",
            "width": plain["width"], "height": plain["height"],
            "square": square_flag,
            "tiles": {c: mapping["tiles"][c] for c in tile_codes},
        })

    idx = 0
    for i in range(0, len(square), SQUARE_PER_SHEET):
        idx += 1
        add_sheet(square[i:i + SQUARE_PER_SHEET], idx, True)
    for i in range(0, len(wide), WIDE_PER_SHEET):
        idx += 1
        add_sheet(wide[i:i + WIDE_PER_SHEET], idx, False)

    (out_dir / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n",
                                          encoding="utf-8")

    with (out_dir / "scoring.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(SCORING_HEADER)
        for t in ordered:
            w.writerow([t["code"], t["scene"], "", "", "", ""])

    (out_dir / "INSTRUCTIONS.txt").write_text(_instructions(len(ordered)),
                                              encoding="utf-8")
    print(f"tiles: {len(ordered)} (square {len(square)}, wide {len(wide)}), "
          f"sheets: {len(mapping['sheets'])} x 2 variants")
    print(f"wrote {out_dir/'mapping.json'}")
    print(f"wrote {out_dir/'scoring.csv'}")
    return mapping


def _instructions(n: int) -> str:
    return f"""S15 style-lock review - how to score on a phone ({n} tiles)
========================================================

Files
  sheets/sheet_NN.png            plain sheet, every tile has a thin band over
                                 its bottom fifth = the caption zone
  sheets/sheet_NN_captioned.png  same sheet with a sample subtitle burned in
  scoring.csv                    fill this
  mapping.json                   SEALED: code -> style/scene/seed

The tiles are coded K1..K{n} in random order. Sheet composition is random: a
sheet may mix scenes, styles and seeds. Nothing on a sheet names a style,
seed or scene type, and no file name carries one either.

Score every tile, in this order:

1. anatomy_ok  (creature/scene tiles only; Y / N / NA)
   Y  = the creature has the anatomy the scene asks for (S10 anatomy spec:
        the grazer has exactly six separate tendrils and two pairs of fins;
        the drifter is limbless). For habitat/planet tiles write NA.
   N  = wrong limb/fin/tendril count, fused or duplicated creature.
   Do not judge style here. Do not judge beauty.

2. caption_space_ok  (Y / N)
   Y = the bottom-fifth band is calm enough that white captions sit on it
       without fighting the image.
   N = busy detail, high contrast clutter or a subject in the band.

3. readability_1_5  (1..5)
   Open the matching _captioned sheet at phone size. 5 = instantly readable,
   1 = lost. Judge the caption, not the art.

4. notes  optional, one short line.

Then:
  python scripts/s15_tally.py
It joins scoring.csv with mapping.json, reports per-style anatomy counts,
caption-space counts and the readability median, and applies the gates:
  0 black/NaN, >= 14/18 anatomy per style, >= 15/18 caption space,
  readability median >= 4/5.

Rules
  - Do not open mapping.json until scoring.csv is complete.
  - Do not fill rows for tiles you did not actually look at.
  - No LLM scores anatomy or style for you.
"""


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args(argv)
    run(Path(args.manifest), Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
