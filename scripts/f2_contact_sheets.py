#!/usr/bin/env python3
"""F2 step 3: 12-tile BLIND contact sheets (owner review; no anatomy judging).

Fixes the 6-tiles-per-sheet layout used by s12/s14 (2x3 phone sheets) for the
pilot review: 12 tiles per sheet (4x3), one tile per generated still, tiles
coded A001..A214 in a fixed shuffled order so the reviewer cannot tell which
sentence a plate belongs to. The code -> sentence mapping lives in a SEPARATE
mapping.json, to be opened only after scoring.

Writes /tmp/f2/sheets/{sheet_01..NN.png, mapping.json, scoring.csv,
INSTRUCTIONS.txt}.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageDraw, ImageFont

COLS, ROWS = 4, 3
TILES = COLS * ROWS
TILE = 420
MARGIN, GAP = 18, 12
LABEL_H = 26
SALT = 4242


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--images", default="/tmp/f2/images")
    ap.add_argument("--out", default="/tmp/f2/sheets")
    ap.add_argument("--per-sheet", type=int, default=TILES)
    args = ap.parse_args(argv)

    paths = sorted(Path(args.images).glob("S*.png"))
    if not paths:
        raise SystemExit("BLOCKED: no images to sheet")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SALT)
    order = paths[:]
    rng.shuffle(order)
    codes = [f"A{i:03d}" for i in range(1, len(order) + 1)]
    mapping = {c: p.stem for c, p in zip(codes, order)}

    per = args.per_sheet
    if per != TILES:
        raise SystemExit(f"BLOCKED: 12-tile sheets only (got {per})")
    cols, rows = COLS, ROWS
    sheet_w = cols * TILE + (cols + 1) * MARGIN
    sheet_h = rows * (TILE + LABEL_H) + (rows + 1) * MARGIN

    f = font(20)
    sheets: List[Dict[str, Any]] = []
    for s_i in range(0, len(codes), TILES):
        chunk = codes[s_i:s_i + TILES]
        sheet = Image.new("RGB", (sheet_w, sheet_h), (250, 250, 250))
        d = ImageDraw.Draw(sheet)
        for j, code in enumerate(chunk):
            r, c = divmod(j, cols)
            x = MARGIN + c * (TILE + MARGIN)
            y = MARGIN + r * (TILE + LABEL_H + MARGIN)
            with Image.open(Path(args.images) / f"{mapping[code]}.png") as im:
                thumb = im.convert("RGB").resize((TILE, TILE), Image.LANCZOS)
            sheet.paste(thumb, (x, y))
            d.rectangle([x, y, x + TILE - 1, y + TILE - 1], outline=(60, 60, 60))
            d.text((x + 6, y + TILE + 4), code, fill=(0, 0, 0), font=f)
        name = f"sheet_{s_i // TILES + 1:02d}.png"
        sheet.save(out / name, optimize=True)
        sheets.append({"sheet": name, "codes": chunk})

    (out / "mapping.json").write_text(
        json.dumps({"salt": SALT, "tiles_per_sheet": TILES,
                    "mapping": mapping, "sheets": sheets}, indent=2) + "\n",
        encoding="utf-8")

    with (out / "scoring.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "reads_as_intended_subject", "limb_count_ok",
                    "silhouette_readable", "artefact_notes", "comment"])
        for code in codes:
            w.writerow([code, "", "", "", "", ""])

    (out / "INSTRUCTIONS.txt").write_text(
        "BLIND REVIEW — do not open mapping.json before scoring.csv is filled.\n\n"
        f"{len(codes)} stills on {len(sheets)} sheets, {TILES} tiles per sheet.\n"
        "Codes (A001...) are shuffled; the sentence each plate illustrates is\n"
        "hidden in mapping.json. Score each tile on the four columns of\n"
        "scoring.csv. No automated anatomy judging was run: this is the only\n"
        "anatomy check in the pipeline.\n", encoding="utf-8")

    print(f"images {len(codes)} | sheets {len(sheets)} | {TILES} tiles/sheet | "
          f"out {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
