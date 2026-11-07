#!/usr/bin/env python3
"""S12: build the blind contact-sheet scoring pack under projects/s12_blind/.

54 images (3 models x 6 scenes x 3 seeds) are shuffled with a fixed salt and
coded A1..A54. Sheets carry NO model names and NO style names. The code->
model/scene/seed mapping lives in a SEPARATE mapping.json (do not open it
before the scoring CSV is filled - the test is blind).

Each sheet is phone-sized (750x1334) with 6 tiles; every tile has a blank
caption-zone band at the bottom where a burned-in caption would sit.

Outputs:
  projects/s12_blind/sheet_01.png ... sheet_09.png   (plain sheets)
  projects/s12_blind/mapping.json                    (code -> model/scene/seed)
  projects/s12_blind/scoring.csv                     (template for the owner)
  projects/s12_blind/INSTRUCTIONS.txt
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

SHEET_W, SHEET_H = 750, 1334
COLS, ROWS = 3, 4
TILES_PER_SHEET = COLS * ROWS
MARGIN = 20
GAP = 12
CODE_SIZE = 40
CAPTION_FRACTION = 0.22  # blank caption-zone band at the bottom of each tile

MODEL_ORDER = ["klein", "dreamshaper-xl-lightning", "dreamshaper-xl-1-0"]
SEEDS = [1001, 2027, 4409]
SCENES = ["s01", "s03", "s05", "s06", "s10", "s12"]

CSV_HEADER = "code,scene_id,seed,correct_part_count,caption_space,comment\n"
# correct_part_count / caption_space: yes/no, left blank for the owner to fill.


def load_image_items() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for model in MODEL_ORDER:
        man_path = Path(f"/tmp/kilo/s12_out/{model}/s12_bakeoff_{model}/manifest.json")
        import json as _json
        manifest = _json.loads(man_path.read_text(encoding="utf-8"))
        for img in manifest.get("images", []):
            png = Path(f"/tmp/kilo/s12_out/{model}/s12_bakeoff_{model}/images/{img['file']}")
            if not png.is_file():
                raise SystemExit(f"BLOCKED: missing image {png}")
            items.append({
                "render_id": img["render_id"],
                "model": model,
                "scene_id": img["scene_id"],
                "seed": int(img["seed"]),
                "output_file": img["file"],
                "path": png,
            })
    if len(items) != 54:
        raise SystemExit(f"BLOCKED: {len(items)} images, expected 54")
    return items


def assign_codes(items: List[Dict[str, Any]], salt: str = "s12") -> List[Dict[str, Any]]:
    digest = hashlib.sha256(salt.encode()).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    order = list(range(len(items)))
    rng.shuffle(order)
    for i, idx in enumerate(order):
        items[idx]["code"] = f"A{i + 1}"
    return sorted(items, key=lambda it: it["code"])


def build(items: List[Dict[str, Any]], out_dir: Path) -> None:
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

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
        return ImageFont.load_default(size=size) if hasattr(ImageFont, "load_default") else ImageFont.load_default()

    tile_w = (SHEET_W - 2 * MARGIN - (COLS - 1) * GAP) // COLS
    tile_h = (SHEET_H - 2 * MARGIN - (ROWS - 1) * GAP - CODE_SIZE - 10) // ROWS
    img_box = int(tile_w * 0.82)
    caption_px = int(round(tile_h * CAPTION_FRACTION))

    mapping: Dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "S12",
        "note": "BLIND: this file unblinds the contact sheets. Do not open it "
                "before scoring.csv is filled.",
        "layout": {"sheet_w": SHEET_W, "sheet_h": SHEET_H,
                   "cols": COLS, "rows": ROWS,
                   "caption_fraction": CAPTION_FRACTION},
        "scenes": SCENES,
        "seeds": SEEDS,
        "models": MODEL_ORDER,
        "codes": [],
    }

    sheet_index = 0
    for start in range(0, len(items), TILES_PER_SHEET):
        chunk = items[start:start + TILES_PER_SHEET]
        sheet_index += 1
        sheet_path = out_dir / f"sheet_{sheet_index:02d}.png"
        sheet = Image.new("RGB", (SHEET_W, SHEET_H), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        draw.text((MARGIN, 10), f"S12 model bake-off - sheet {sheet_index:02d}",
                  fill=(40, 40, 40), font=font(26))
        draw.text((SHEET_W - MARGIN - 220, 10), "code  |  caption zone below",
                  fill=(120, 120, 120), font=font(20))

        for pos, it in enumerate(chunk):
            col = pos % COLS
            row = pos // COLS
            x0 = MARGIN + col * (tile_w + GAP)
            y0 = 52 + MARGIN + row * (tile_h + GAP)
            code = it["code"]
            # image
            with Image.open(it["path"]) as im:
                tile = im.convert("RGB")
                tile.thumbnail((img_box, img_box))
            tw, th = tile.size
            ix = x0 + (tile_w - tw) // 2
            iy = y0 + 34
            sheet.paste(tile, (ix, iy))
            # code label
            draw.text((x0 + 6, iy + th + 6), code, fill=(10, 10, 10), font=font(CODE_SIZE))
            # caption-zone overlay: blank band at the bottom of the tile
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
            mapping["codes"].append({
                "code": code,
                "sheet": sheet_path.name,
                "tile": pos + 1,
                "render_id": it["render_id"],
                "model": it["model"],
                "scene_id": it["scene_id"],
                "seed": it["seed"],
                "output_file": it["output_file"],
            })
        sheet.save(sheet_path, optimize=True)

    # scoring template: code order A1..A54
    lines = [CSV_HEADER]
    for it in items:
        lines.append(f"{it['code']},{it['scene_id']},{it['seed']},,,\n")
    (out_dir / "scoring.csv").write_text("".join(lines), encoding="utf-8")
    (out_dir / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n",
                                            encoding="utf-8")
    (out_dir / "INSTRUCTIONS.txt").write_text(
        "S12 model bake-off - blind scoring (about 15 minutes)\n"
        "=====================================================\n"
        "\n"
        "9 sheets, 6 tiles each, codes A1..A54 in a fixed random order.\n"
        "No model names or style names appear on the sheets - that is the point.\n"
        "\n"
        "For every tile fill scoring.csv:\n"
        "  correct_part_count : yes if the anatomy (limbs / eyes / horns for the\n"
        "                       scene spec) is right, no otherwise. Habitat and\n"
        "                       wide scenes have 0 parts - judge on that basis.\n"
        "  caption_space      : yes if the blank caption zone beneath the tile\n"
        "                       could carry a readable burned-in caption.\n"
        "  comment            : optional one-liner.\n"
        "\n"
        "mapping.json (code -> model / scene / seed) is separate. Do not open it\n"
        "until scoring.csv is complete. Then run: python scripts/s12_tally.py\n"
        "\n"
        "Sheets: sheet_01.png ... sheet_09.png (phone-sized, 750x1334).\n",
        encoding="utf-8")
    print(f"sheets: {sheet_index} x {TILES_PER_SHEET} tiles in {out_dir}")
    print("owner fills scoring.csv, then: python scripts/s12_tally.py")


def main() -> int:
    items = load_image_items()
    items = assign_codes(items)
    build(items, REPO / "projects/s12_blind")
    return 0


if __name__ == "__main__":
    import json  # noqa: E402
    sys.exit(main())
