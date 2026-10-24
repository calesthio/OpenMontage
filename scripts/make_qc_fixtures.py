#!/usr/bin/env python3
"""scripts/make_qc_fixtures.py - synthetic QC fixtures (P4).

Generates a labelled fixture set for the image QC:

  * `text`      - images that contain lettering (the detector must flag them),
  * `clean`     - flat art, line art, noise, panels (must not be flagged),
  * `ambiguous` - glyph-like marks that are not lettering (dashes, a barcode).

No new dependency: Pillow (with its scalable default font) and numpy only.
The images are synthetic - no model output is used.

  python scripts/make_qc_fixtures.py --out /tmp/kilo/qc_fixtures
  python scripts/make_qc_fixtures.py --out tests/fixtures/qc --commit-copy
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

W, H = 1024, 576
PALETTE = {
    "deep_teal": (0x14, 0x45, 0x5C),
    "bioluminescent_lime": (0xA8, 0xE0, 0x6F),
    "basalt_charcoal": (0x3B, 0x44, 0x4B),
    "pale_bone": (0xED, 0xE7, 0xD8),
}


def _font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _flat_background(color) -> Image.Image:
    return Image.new("RGB", (W, H), color)


def _draw_text(img: Image.Image, xy, text: str, size: int, fill) -> None:
    draw = ImageDraw.Draw(img)
    draw.text(xy, text, font=_font(size), fill=fill)


def _fixture_text_dark_on_light() -> Image.Image:
    img = _flat_background(PALETTE["pale_bone"])
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, W - 40, H - 40], fill=(0xF7, 0xF4, 0xEC))
    _draw_text(img, (120, 200), "VENT GRAZER", 64, (20, 20, 20))
    return img


def _fixture_text_light_on_dark() -> Image.Image:
    img = _flat_background((10, 16, 24))
    _draw_text(img, (90, 180), "FILTER DRIFTER", 56, (235, 235, 235))
    return img


def _fixture_text_small() -> Image.Image:
    img = _flat_background((250, 250, 250))
    _draw_text(img, (60, 120), "ICE BURROWER", 18, (30, 30, 30))
    _draw_text(img, (60, 150), "SPECULATIVE ILLUSTRATION", 14, (60, 60, 60))
    return img


def _fixture_text_center() -> Image.Image:
    img = _flat_background(PALETTE["deep_teal"])
    _draw_text(img, (200, 260), "UNDER ICE CAVERN", 44, (240, 240, 240))
    return img


def _fixture_text_corner() -> Image.Image:
    img = _flat_background(PALETTE["basalt_charcoal"])
    _draw_text(img, (24, 24), "CHAPTER 2", 22, (230, 230, 230))
    return img


def _fixture_caption_chip() -> Image.Image:
    """A caption chip: a wide light band with dark lettering (the case the
    old heuristic was built for - it must still be flagged)."""
    img = _flat_background(PALETTE["deep_teal"])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, H - 90, W, H - 20], fill=(250, 250, 250))
    _draw_text(img, (40, H - 80), "CHIMOSYNTHESIS", 34, (10, 10, 10))
    return img


def _fixture_text_wide_tracking() -> Image.Image:
    img = _flat_background((255, 255, 255))
    _draw_text(img, (40, 240), "S P E C U L A T I O N", 30, (15, 15, 15))
    return img


def _fixture_flat_two_tone() -> Image.Image:
    img = _flat_background(PALETTE["pale_bone"])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, H // 2], fill=PALETTE["deep_teal"])
    draw.ellipse([W // 3, H // 3, 2 * W // 3, 2 * H // 3],
                 fill=PALETTE["bioluminescent_lime"])
    return img


def _fixture_flat_wide_light_band() -> Image.Image:
    """Flat art with a wide near-white band across the image: the case that
    over-fired in the live job."""
    img = _flat_background(PALETTE["deep_teal"])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, H // 2 - 20, W, H // 2 + 20], fill=(250, 250, 250))
    draw.rectangle([0, H // 2 + 40, W, H], fill=PALETTE["basalt_charcoal"])
    return img


def _fixture_flat_panels() -> Image.Image:
    img = _flat_background((255, 255, 255))
    draw = ImageDraw.Draw(img)
    for i in range(5):
        draw.rectangle([40 + i * 190, 120, 200 + i * 190, 430],
                       fill=PALETTE["basalt_charcoal"])
    return img


def _fixture_line_art() -> Image.Image:
    img = _flat_background((252, 250, 246))
    draw = ImageDraw.Draw(img)
    for i in range(12):
        draw.ellipse([100 + i * 60, 200, 160 + i * 60, 420],
                     outline=(30, 30, 30), width=3)
    return img


def _fixture_dots_grid() -> Image.Image:
    img = _flat_background((250, 250, 250))
    draw = ImageDraw.Draw(img)
    for row in range(8):
        for col in range(24):
            x, y = 30 + col * 42, 40 + row * 64
            draw.ellipse([x, y, x + 8, y + 8], fill=(40, 40, 40))
    return img


def _fixture_gradient() -> Image.Image:
    img = Image.new("RGB", (W, H))
    pixels = img.load()
    for x in range(W):
        shade = int(255 * x / W)
        for y in range(H):
            pixels[x, y] = (shade, 60, 255 - shade)
    return img


def _fixture_noise() -> Image.Image:
    rnd = random.Random(7)
    img = Image.new("RGB", (W, H))
    pixels = img.load()
    for y in range(H):
        for x in range(W):
            v = rnd.randint(0, 255)
            pixels[x, y] = (v, v, v)
    return img


def _fixture_dashes() -> Image.Image:
    """A row of dashes: glyph-like but not lettering (ambiguous)."""
    img = _flat_background((255, 255, 255))
    draw = ImageDraw.Draw(img)
    for i in range(24):
        x = 60 + i * 38
        draw.rectangle([x, 280, x + 22, 292], fill=(25, 25, 25))
    return img


def _fixture_barcode() -> Image.Image:
    """A barcode: machine-readable bars, not lettering (ambiguous)."""
    img = _flat_background((255, 255, 255))
    draw = ImageDraw.Draw(img)
    rnd = random.Random(3)
    x = 80
    while x < W - 80:
        width = rnd.choice([2, 3, 5, 7])
        draw.rectangle([x, 150, x + width, 400], fill=(10, 10, 10))
        x += width + rnd.choice([3, 4, 6, 9])
    return img


def _fixture_bright_blobs_row() -> Image.Image:
    """A row of small bright blobs on a dark ground: the shape that a naive
    connected-component text detector mistakes for lettering."""
    img = _flat_background((18, 24, 32))
    draw = ImageDraw.Draw(img)
    rnd = random.Random(11)
    for i in range(14):
        x = 120 + i * 46
        r = rnd.randint(7, 13)
        draw.ellipse([x - r, 270 - r, x + r, 270 + r], fill=(214, 240, 120))
    return img


def _fixture_text_over_texture() -> Image.Image:
    """Lettering over a textured ground (a harder positive case)."""
    img = _flat_background((232, 228, 216))
    draw = ImageDraw.Draw(img)
    rnd = random.Random(5)
    for i in range(260):
        x, y = rnd.randint(0, W - 1), rnd.randint(0, H - 1)
        shade = rnd.randint(150, 210)
        draw.rectangle([x, y, x + 6, y + 4], fill=(shade, shade - 8, shade - 20))
    _draw_text(img, (150, 250), "CHIMOSYNTHESIS", 40, (20, 20, 20))
    return img


FIXTURES = [
    ("text_dark_on_light", "text", 1),
    ("text_light_on_dark", "text", 1),
    ("text_small", "text", 1),
    ("text_center", "text", 1),
    ("text_corner", "text", 1),
    ("caption_chip", "text", 1),
    ("text_wide_tracking", "text", 1),
    ("flat_two_tone", "clean", 0),
    ("flat_wide_light_band", "clean", 0),
    ("flat_panels", "clean", 0),
    ("line_art", "clean", 0),
    ("dots_grid", "clean", 0),
    ("gradient", "clean", 0),
    ("noise", "clean", 0),
    ("bright_blobs_row", "clean", 0),
    ("text_over_texture", "text", 1),
    ("dashes", "ambiguous", None),
    ("barcode", "ambiguous", None),
]

BUILDERS = {
    "text_dark_on_light": _fixture_text_dark_on_light,
    "text_light_on_dark": _fixture_text_light_on_dark,
    "text_small": _fixture_text_small,
    "text_center": _fixture_text_center,
    "text_corner": _fixture_text_corner,
    "caption_chip": _fixture_caption_chip,
    "text_wide_tracking": _fixture_text_wide_tracking,
    "flat_two_tone": _fixture_flat_two_tone,
    "flat_wide_light_band": _fixture_flat_wide_light_band,
    "flat_panels": _fixture_flat_panels,
    "line_art": _fixture_line_art,
    "dots_grid": _fixture_dots_grid,
    "gradient": _fixture_gradient,
    "noise": _fixture_noise,
    "bright_blobs_row": _fixture_bright_blobs_row,
    "text_over_texture": _fixture_text_over_texture,
    "dashes": _fixture_dashes,
    "barcode": _fixture_barcode,
}


def build(out_dir: str | Path) -> Dict[str, Any]:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    index = []
    for name, category, label in FIXTURES:
        path = directory / f"{name}.png"
        BUILDERS[name]().save(path)
        index.append({"name": name, "file": path.name, "category": category,
                      "label": label, "width": W, "height": H})
    manifest = {"schema_version": 1, "width": W, "height": H,
                "fixtures": index}
    (directory / "fixtures.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/tmp/kilo/qc_fixtures")
    args = ap.parse_args(argv)
    manifest = build(args.out)
    print(f"fixtures: {len(manifest['fixtures'])} -> {args.out}")
    for item in manifest["fixtures"]:
        print(f"  {item['name']:28s} {item['category']:10s} label={item['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
