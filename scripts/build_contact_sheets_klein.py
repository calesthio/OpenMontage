#!/usr/bin/env python3
"""Build contact sheets 4x3 numbered from 78 Klein frames.

78 frames → 7 sheets (6×12 + 1×6). Each frame numbered 1-78 in section/bit order.
Output: tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein/
        contact_sheet_klein_01.jpg ... contact_sheet_klein_07.jpg
"""

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/workspaces/OpenMontage")
FRAME_DIR = ROOT / "tools/kaggle_bridge/jobs/pilot-render/frames_klein"
SL = ROOT / "tools/kaggle_bridge/jobs/pilot-render/shot_list.json"
OUT_DIR = ROOT / "tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein"
OUT_DIR.mkdir(parents=True, exist_ok=True)

shot_list = json.loads(SL.read_text())["shots"]
# Order by section then bit index within section
shots_sorted = sorted(shot_list, key=lambda s: (s["section"], int(s["bit_id"][1:])))

FRAMES_PER_SHEET = 12
COLS, ROWS = 4, 3
CELL_W, CELL_H = 320, 180  # 1280x720 scaled

try:
    FONT = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
except Exception:
    FONT = ImageFont.load_default()


def make_sheet(frames, sheet_num, start_num):
    sheet = Image.new("RGB", (COLS * CELL_W, ROWS * CELL_H), "white")
    draw = ImageDraw.Draw(sheet)
    for i, fpath in enumerate(frames):
        if i >= FRAMES_PER_SHEET:
            break
        img = Image.open(fpath).convert("RGB")
        img = img.resize((CELL_W, CELL_H))
        r, c = divmod(i, COLS)
        x0, y0 = c * CELL_W, r * CELL_H
        sheet.paste(img, (x0, y0))
        label = str(start_num + i)
        bbox = draw.textbbox((0, 0), label, font=FONT)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        bx = x0 + CELL_W - tw - 8
        by = y0 + 8
        draw.rectangle([bx - 4, by - 4, bx + tw + 4, by + th + 4], fill="white")
        draw.text((bx, by), label, fill="black", font=FONT)
    out = OUT_DIR / f"contact_sheet_klein_{sheet_num:02d}.jpg"
    sheet.save(out, quality=88, optimize=True)
    print(f"Sheet {sheet_num}: {out} ({out.stat().st_size} bytes), frames {start_num}-{start_num+len(frames[:FRAMES_PER_SHEET])-1}")
    return out


def main():
    frame_paths = []
    for s in shots_sorted:
        fpath = FRAME_DIR / f"s{s['section']:02d}_{s['bit_id']}.png"
        if not fpath.exists():
            raise SystemExit(f"Missing frame {fpath}")
        frame_paths.append(fpath)
    print(f"Total frames: {len(frame_paths)}")

    n_sheets = (len(frame_paths) + FRAMES_PER_SHEET - 1) // FRAMES_PER_SHEET
    sheets = []
    for sn in range(1, n_sheets + 1):
        start = (sn - 1) * FRAMES_PER_SHEET + 1
        chunk = frame_paths[(sn - 1) * FRAMES_PER_SHEET: sn * FRAMES_PER_SHEET]
        sheets.append(make_sheet(chunk, sn, start))
    print(f"\nBuilt {len(sheets)} contact sheets in {OUT_DIR}")


if __name__ == "__main__":
    main()
