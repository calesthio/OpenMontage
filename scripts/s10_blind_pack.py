#!/usr/bin/env python3
"""S10-3: build the owner's blind pack (projects/s10_blind/, gitignored).

For each of the six scenes:
  * take ONE image per style (the scene's first seed — the same seed index for
    all three styles, so the comparison is apples-to-apples),
  * shuffle the three styles into panels A / B / C in a different random order
    per scene (reproducible from a salt),
  * lay the panels side by side at <= 1600 px wide (phone-readable),
  * write a second, captioned version of the same sheet with plain white
    subtitle text burned into the bottom of every panel (caption-legibility
    test), and
  * keep the panel -> style mapping in a SEPARATE mapping.json.

The sheets carry no style names, no model names and no ranking. Nothing here
judges beauty, anatomy or style: that is the owner's blind call.

Also writes:
  results.csv      template (scene,best_panel,worst_panel,
                   readable_with_captions_A/B/C,comment)
  INSTRUCTIONS.txt what to review on a phone, in plain words

Usage:
  python scripts/s10_blind_pack.py \
      --images /tmp/kilo/s10_out/klein/s10_bakeoff_klein/images \
      --manifest /tmp/kilo/s10_out/klein/s10_bakeoff_klein/manifest.json \
      --out projects/s10_blind
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

PANEL = 512
GAP = 8
LABEL_H = 48
MARGIN = 8
MAX_WIDTH = 1600
LABELS = "ABC"
#: The bottom band of every panel where a burned-in subtitle lives.
CAPTION_BAND_FRACTION = 0.28

CSV_HEADER = ("scene,best_panel,worst_panel,readable_with_captions_A,"
              "readable_with_captions_B,readable_with_captions_C,comment")

DEFAULT_CAPTIONS: Dict[str, str] = {
    "s01": "The vent grazer crops bacterial mats at the chimney rim.",
    "s03": "Filter drifters sieve microbes from the open water column.",
    "s05": "Chimney fields vent mineral-rich water onto the sea floor.",
    "s06": "Melt pools glow beneath the frozen ice shell.",
    "s10": "Chemosynthetic bacteria feed the whole vent food web.",
    "s12": "Plumes break through the ice crust of the frozen ocean world.",
}

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
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def panel_order(scene: str, salt: str = "s10",
                styles: Optional[Sequence[str]] = None) -> List[str]:
    digest = hashlib.sha256(f"{salt}:{scene}".encode()).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    order = list(styles) if styles else ["S-A", "S-B", "S-C"]
    rng.shuffle(order)
    return order


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


def _fit_caption(draw: ImageDraw.ImageDraw, text: str, panel: int
                 ) -> Tuple[Any, List[str], int]:
    """Pick the largest font (<= 40 px) whose wrap fits 3 lines."""
    for size in (40, 36, 32, 28, 24):
        font = _font(size)
        lines = _wrap(draw, text, font, panel - 16)
        if len(lines) <= 3:
            return font, lines, size
    font = _font(24)
    return font, _wrap(draw, text, font, panel - 16)[:3], 24


def build_sheet(images: Dict[str, Path], scene: str, order: Dict[str, str],
                out_path: Path, caption: Optional[str] = None
                ) -> Dict[str, Any]:
    """Compose one sheet (plain or captioned); returns its geometry."""
    panel = PANEL
    width = MARGIN + len(LABELS) * panel + (len(LABELS) - 1) * GAP + MARGIN
    if width > MAX_WIDTH:
        raise ValueError(f"sheet width {width} exceeds {MAX_WIDTH}")
    height = MARGIN + LABEL_H + panel + MARGIN
    sheet = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    label_font = _font(36)
    boxes: Dict[str, List[int]] = {}
    for i, label in enumerate(LABELS):
        style = order[label]
        x = MARGIN + i * (panel + GAP)
        y = MARGIN + LABEL_H
        with Image.open(images[style]) as im:
            tile = im.convert("RGB").resize((panel, panel), Image.LANCZOS)
        sheet.paste(tile, (x, y))
        draw.text((x + 8, MARGIN + 2), label, fill=(0, 0, 0), font=label_font)
        draw.rectangle([x - 1, y - 1, x + panel, y + panel],
                       outline=(190, 190, 190))
        boxes[label] = [x, y, x + panel, y + panel]

    caption_px = int(round(panel * CAPTION_BAND_FRACTION))
    if caption is not None:
        font, lines, size = _fit_caption(draw, caption, panel)
        line_h = int(round(size * 1.18))
        block_h = line_h * len(lines)
        for label in LABELS:
            x0, y0, x1, y1 = boxes[label]
            top = y1 - block_h - 10
            for n, line in enumerate(lines):
                tw = draw.textlength(line, font=font)
                draw.text((x0 + (panel - tw) / 2, top + n * line_h), line,
                          fill=(255, 255, 255), font=font)
        caption_meta = {"text": caption, "font_px": size, "lines": lines,
                        "band_px": caption_px}
    else:
        caption_meta = None

    sheet.save(out_path, optimize=True)
    return {
        "file": out_path.name,
        "scene": scene,
        "width": width,
        "height": height,
        "panel": panel,
        "panel_boxes": boxes,
        "caption": caption_meta,
        "order": {label: order[label] for label in LABELS},
    }


def select_panels(manifest: Dict[str, Any], images_dir: Path
                  ) -> Tuple[Dict[str, Dict[str, Path]], Dict[str, Any]]:
    """scene -> {style: image} using each scene's FIRST seed for every style."""
    by_scene: Dict[str, Dict[str, Any]] = {}
    for entry in manifest.get("images", []):
        if not entry.get("file"):
            continue
        path = images_dir / entry["file"]
        if not path.is_file():
            continue
        scene = entry.get("scene_id")
        style = entry.get("style") or entry.get("variant")
        if not scene or not style:
            raise SystemExit(f"BLOCKED: manifest entry without scene/style: {entry}")
        slot = by_scene.setdefault(scene, {})
        current = slot.get(style)
        if current is None or int(entry["seed"]) < int(current["seed"]):
            slot[style] = {"path": path, "seed": int(entry["seed"]),
                           "render_id": entry["render_id"],
                           "file": entry["file"]}

    picked: Dict[str, Dict[str, Path]] = {}
    detail: Dict[str, Any] = {}
    for scene in sorted(by_scene):
        slot = by_scene[scene]
        missing = {"S-A", "S-B", "S-C"} - set(slot)
        if missing:
            raise SystemExit(f"BLOCKED: scene {scene} missing styles {sorted(missing)}")
        # every style of a scene must use the same seed index
        seeds = {style: slot[style]["seed"] for style in ("S-A", "S-B", "S-C")}
        if len(set(seeds.values())) != 1:
            raise SystemExit(
                f"BLOCKED: scene {scene} does not share one seed across styles: "
                f"{seeds}")
        picked[scene] = {style: slot[style]["path"] for style in slot}
        detail[scene] = {style: {"render_id": slot[style]["render_id"],
                                 "file": slot[style]["file"],
                                 "seed": slot[style]["seed"]}
                         for style in slot}
    if not picked:
        raise SystemExit("BLOCKED: no usable images in the manifest")
    return picked, detail


def write_csv_template(out_dir: Path, scenes: Sequence[str]) -> Path:
    p = out_dir / "results.csv"
    lines = [CSV_HEADER]
    for scene in scenes:
        lines.append(f"{scene},,,,,,")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def instructions(scenes: Sequence[str], captions: Dict[str, str]) -> str:
    lines = [
        "S10 visual-style test - how to review (5-10 minutes)",
        "===================================================",
        "",
        "You are comparing THREE candidate illustration styles on the same six",
        "scenes. Each sheet shows the same scene in three styles, panels A / B /",
        "C, in a different random order on every sheet. No style names appear on",
        "the sheets.",
        "",
        "For each of the 6 scenes there are TWO files:",
        "  sheet_<scene>.png          plain sheet",
        "  sheet_<scene>_caption.png  same sheet with plain white subtitle text",
        "                             burned into the bottom of every panel",
        "",
        "1. Open the plain sheets first and fill best_panel / worst_panel:",
        "   which panel would you actually use for this channel, and which would",
        "   you throw away? Judge the STYLE only (look, colour, depth, detail),",
        "   not the anatomy of the creature.",
        "",
        "2. Then open the _caption sheets and, for EACH panel, answer",
        "   readable_with_captions_<panel>: yes if the white subtitle is easy to",
        "   read over that panel on a phone, no if it is lost in the image.",
        "",
        "3. comment: optional, one short line per scene.",
        "",
        "4. Fill results.csv (any CSV editor or spreadsheet). Allowed values:",
        "   best_panel / worst_panel : A or B or C (worst may be left empty)",
        "   readable_with_captions_X : yes or no, for each panel X = A, B, C",
        "   Do not edit the scene column.",
        "",
        "5. Then run:  python scripts/s10_tally.py",
        "   It prints wins / losses / caption-readability per style and refuses",
        "   to recommend anything while the CSV is incomplete. Nothing is",
        "   written to STYLE_BIBLE.md before your CSV is complete.",
        "",
        "Notes",
        "-----",
        "- mapping.json (which panel is which style) is in this folder. Do not",
        "  open it until after you have filled the CSV, or the test is no longer",
        "  blind.",
        "- The prompts, the objective flags and the per-scene captions are in",
        "  docs/openmontage/image_gen/STYLE_TEST_S10.md (safe to read).",
        f"- Scenes: {', '.join(scenes)}",
        "- One image per style per scene is shown (the scene's first seed); the",
        "  other two seeds per style are scored by objective flags only.",
    ]
    return "\n".join(lines) + "\n"


def run(images_dir: Path, manifest_path: Path, out_dir: Path,
        salt: str = "s10", captions: Optional[Dict[str, str]] = None
        ) -> Dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    picked, detail = select_panels(manifest, Path(images_dir))
    scenes = sorted(picked)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = dict(DEFAULT_CAPTIONS)
    if captions:
        cap.update(captions)

    mapping: Dict[str, Any] = {
        "schema_version": "1.0",
        "milestone": "S10",
        "salt": salt,
        "model": manifest.get("model"),
        "job_id": manifest.get("job_id"),
        "note": "BLIND: this file unblinds the sheets. Do not open it before "
                "results.csv is filled.",
        "caption_band_fraction": CAPTION_BAND_FRACTION,
        "layout": {"panel": PANEL, "gap": GAP, "label_height": LABEL_H,
                   "margin": MARGIN, "max_width": MAX_WIDTH},
        "scenes": {},
        "panels": {},
        "images": detail,
        "sheets": [],
        "seed_policy": "one image per style per scene, the scene's first seed "
                       "for all three styles",
    }
    for scene in scenes:
        order = dict(zip(LABELS, panel_order(scene, salt, list(picked[scene]))))
        mapping["scenes"][scene] = order
        plain = build_sheet(picked[scene], scene, order,
                            out_dir / f"sheet_{scene}.png", caption=None)
        captioned = build_sheet(picked[scene], scene, order,
                                out_dir / f"sheet_{scene}_caption.png",
                                caption=cap.get(scene, ""))
        mapping["sheets"].append({"scene": scene, "plain": plain["file"],
                                  "captioned": captioned["file"],
                                  "width": plain["width"],
                                  "height": plain["height"],
                                  "caption": captioned["caption"]})
        mapping["panels"][scene] = {
            label: {
                "style": order[label],
                "box": plain["panel_boxes"][label],
                "caption_box": [
                    plain["panel_boxes"][label][0],
                    plain["panel_boxes"][label][3]
                    - int(round(PANEL * CAPTION_BAND_FRACTION)),
                    plain["panel_boxes"][label][2],
                    plain["panel_boxes"][label][3],
                ],
                "render_id": detail[scene][order[label]]["render_id"],
                "file": detail[scene][order[label]]["file"],
                "seed": detail[scene][order[label]]["seed"],
            }
            for label in LABELS
        }

    write_csv_template(out_dir, scenes)
    (out_dir / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n",
                                         encoding="utf-8")
    (out_dir / "INSTRUCTIONS.txt").write_text(instructions(scenes, cap),
                                             encoding="utf-8")
    return mapping


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default=str(REPO / "projects/s10_blind"))
    ap.add_argument("--salt", default="s10")
    args = ap.parse_args(argv)
    mapping = run(Path(args.images), Path(args.manifest), Path(args.out),
                  args.salt)
    print(f"sheets: {len(mapping['sheets'])} scenes x (plain + captioned) in {args.out}")
    print("owner fills results.csv, then: python scripts/s10_tally.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
