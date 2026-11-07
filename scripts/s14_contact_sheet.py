#!/usr/bin/env python3
"""S14: build ONE blind contact sheet (phone-sized, coded tiles, no model
names, mapping kept separate).

Collects generated images from the 3 S14 kernel outputs (only models that
produced images appear). Assigns codes A1..An in a fixed order, tiles them on
phone-sized sheets (750x1334) with a blank caption-zone band under every tile.
The code -> model/seed mapping lives in a SEPARATE mapping.json (do not open
it before scoring).

Outputs (gitignored projects/s14_blind/):
  sheet_01.png ...                   plain contact sheets
  mapping.json                       code -> model/seed/output_file (SEPARATE)
  scoring.csv                        template for the owner
  INSTRUCTIONS.txt
"""
from __future__ import annotations

import json, shutil, sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
FETCH = Path("/tmp/kilo/s14_out")
OUT = REPO / "projects/s14_blind"
SHEET_W, SHEET_H = 750, 1334
COLS, ROWS = 3, 4
TILES_PER_SHEET = COLS * ROWS
MARGIN = 20
GAP = 12
CODE_SIZE = 40
CAPTION_FRACTION = 0.22


def collect_images() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not FETCH.is_dir():
        return items
    for model_dir in sorted(FETCH.iterdir()):
        if not model_dir.is_dir():
            continue
        smoke = None
        for sub in model_dir.iterdir():
            if sub.is_dir() and sub.name.startswith("s14_smoke_"):
                smoke = sub
                break
        if smoke is None:
            continue
        img_dir = smoke / "images"
        if not img_dir.is_dir():
            continue
        man_path = smoke / "manifest.json"
        man = None
        if man_path.is_file():
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
            except Exception:
                man = None
        for png in sorted(img_dir.glob("*.png")):
            items.append({
                "model": model_dir.name.replace("s14_", ""),
                "output_file": png.name,
                "path": png,
                "manifest": man,
            })
    return items


def build(items: List[Dict[str, Any]]) -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

    # fixed order: by model then seed
    items.sort(key=lambda it: (it["model"], it["output_file"]))
    for i, it in enumerate(items):
        it["code"] = f"A{i + 1}"

    from PIL import Image, ImageDraw, ImageFont

    def font(size: int):
        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
            if Path(p).is_file():
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    continue
        return ImageFont.load_default()

    tile_w = (SHEET_W - 2 * MARGIN - (COLS - 1) * GAP) // COLS
    tile_h = (SHEET_H - 2 * MARGIN - (ROWS - 1) * GAP - CODE_SIZE - 10) // ROWS
    img_box = int(tile_w * 0.82)
    caption_px = int(round(tile_h * CAPTION_FRACTION))

    mapping: Dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "S14",
        "note": "BLIND: this file unblinds the contact sheets. Do not open it "
                "before scoring.csv is filled.",
        "layout": {"sheet_w": SHEET_W, "sheet_h": SHEET_H,
                   "cols": COLS, "rows": ROWS,
                   "caption_fraction": CAPTION_FRACTION},
        "tiles": [],
    }

    sheet_index = 0
    for start in range(0, len(items), TILES_PER_SHEET):
        chunk = items[start:start + TILES_PER_SHEET]
        sheet_index += 1
        sheet_path = OUT / f"sheet_{sheet_index:02d}.png"
        sheet = Image.new("RGB", (SHEET_W, SHEET_H), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        draw.text((MARGIN, 10), f"S14 smoke test - sheet {sheet_index:02d}",
                  fill=(40, 40, 40), font=font(26))
        draw.text((SHEET_W - MARGIN - 220, 10), "code  |  caption zone below",
                  fill=(120, 120, 120), font=font(20))

        for pos, it in enumerate(chunk):
            col = pos % COLS
            row = pos // COLS
            x0 = MARGIN + col * (tile_w + GAP)
            y0 = 52 + MARGIN + row * (tile_h + GAP)
            code = it["code"]
            with Image.open(it["path"]) as im:
                tile = im.convert("RGB")
                tile.thumbnail((img_box, img_box))
            tw, th = tile.size
            ix = x0 + (tile_w - tw) // 2
            iy = y0 + 34
            sheet.paste(tile, (ix, iy))
            draw.text((x0 + 6, iy + th + 6), code, fill=(10, 10, 10),
                      font=font(CODE_SIZE))
            cz_y = iy + th + 34 + CODE_SIZE + 6
            cz_h = tile_h - 34 - CODE_SIZE - 14 - caption_px
            if cz_h < 0:
                cz_h = 0
            draw.rectangle([x0, cz_y, x0 + tile_w, cz_y + cz_h],
                           fill=(235, 235, 235))
            draw.rectangle([x0 - 1, iy - 1, x0 + tile_w, iy + tile_h - 1],
                           outline=(170, 170, 170))
            draw.text((x0 + 6, cz_y + 6), "caption zone", fill=(150, 150, 150),
                      font=font(18))
            man = it.get("manifest") or {}
            imrec = None
            if man and man.get("images"):
                for imrecx in man["images"]:
                    if imrecx.get("output_file") == it["output_file"]:
                        imrec = imrecx
                        break
            mapping["tiles"].append({
                "code": code,
                "sheet": sheet_path.name,
                "tile": pos + 1,
                "model": it["model"],
                "output_file": it["output_file"],
                "seed": imrec.get("seed") if imrec else None,
                "seconds": imrec.get("seconds") if imrec else None,
                "black_or_nan": imrec.get("black_or_nan") if imrec else None,
                "error": imrec.get("error") if imrec else None,
            })
        sheet.save(sheet_path, optimize=True)

    lines = ["code,image_ok,black_frame,comment\n"]
    for it in items:
        lines.append(f"{it['code']},,,\n")
    (OUT / "scoring.csv").write_text("".join(lines), encoding="utf-8")
    (OUT / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n",
                                        encoding="utf-8")
    (OUT / "INSTRUCTIONS.txt").write_text(
        "S14 smoke test - blind contact sheet\n"
        "======================================\n"
        "\n"
        "Coded tiles A1..An, NO model names. The code -> model/seed mapping lives\n"
        "in mapping.json (SEPARATE - do not open before scoring.csv is filled).\n"
        "\n"
        "Each tile has a blank caption-zone band beneath it where a burned-in\n"
        "caption would sit.\n"
        "\n"
        "The owner fills scoring.csv (comment column) and then unblinds via\n"
        "mapping.json.\n",
        encoding="utf-8")
    print(f"sheets: {sheet_index}, tiles: {len(items)} in {OUT}")


def main() -> int:
    items = collect_images()
    if not items:
        print("No generated images found; contact sheet will be empty.")
        build([])
        return 0
    build(items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
