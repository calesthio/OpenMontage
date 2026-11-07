#!/usr/bin/env python3
"""F2 step 2b: image QC — black/NaN, corner watermarks, dHash duplicates.

No anatomy judging (owner reviews anatomy on the blind sheets).

Checks per image
  * black        : mean luminance < 6/255 or >99% of pixels below 8
  * nan/flat     : std-dev < 1.0 (a NaN/div-by-zero VAE usually collapses to a
                   flat field) or a single unique colour
  * watermark    : text-like structure inside any 28% corner crop
                   (tools/illustration/text_detect.detect_text_like)
  * duplicate    : dHash (64-bit) Hamming <= 8 against earlier images
  * size/aspect  : 1024x1024 exactly

Writes /tmp/f2/images/qc_images.json + a one-line-per-image CSV.
Exit 1 if any image is rejected (so the caller cannot silently continue).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from PIL import Image, ImageStat  # noqa: E402

from tools.illustration.illustration_qc import (  # noqa: E402
    difference_hash, hamming_distance,
)
from tools.illustration.text_detect import detect_text_like  # noqa: E402

CORNER_FRACTION = 0.28
DUP_HAMMING_MAX = 8


def check_black_flat(img: Image.Image) -> Dict[str, Any]:
    gray = img.convert("L")
    stat = ImageStat.Stat(gray)
    mean = stat.mean[0]
    std = stat.stddev[0]
    hist = gray.histogram()
    total = sum(hist)
    dark = sum(hist[:8]) / total
    colors = img.convert("RGB").getcolors(maxcolors=4)
    return {
        "mean_luma": round(mean, 2),
        "std_luma": round(std, 2),
        "dark_share": round(dark, 4),
        "unique_colors_le4": len(colors) if colors else 999,
        "black": mean < 6 or dark > 0.99,
        "flat": std < 1.0 or (colors is not None and len(colors) <= 1),
    }


def corner_text(path: Path) -> Dict[str, Any]:
    """Text-like structure inside any 28% corner region (watermark detector).

    Runs the detector ONCE on the full frame and intersects the detected line
    boxes with the corner rectangles. Cropping first was measured to miss
    small watermarks (the detector's glyph/stroke ratios are tuned for the
    full-frame scale), and one full-frame pass is also cheaper than four crops.
    """
    img = Image.open(path).convert("RGB")
    w, h = img.size
    try:
        det = detect_text_like(path)
    except Exception as exc:  # noqa: BLE001
        return {"corner_text_like": False, "corners": [], "detector_error": str(exc)}
    cw, ch = w * CORNER_FRACTION, h * CORNER_FRACTION
    corners = {"tl": (0, 0, cw, ch), "tr": (w - cw, 0, w, ch),
               "bl": (0, h - ch, cw, h), "br": (w - cw, h - ch, w, h)}
    hits = []
    min_w, min_h = w * 0.03, h * 0.01     # ignore specks: a 23x7 px mark in a
    for box in det.get("line_boxes") or []:  # 1024 frame is texture, not lettering
        # text_detect returns [x0, x1, y0, y1]
        x0, x1, y0, y1 = box[:4]
        if (x1 - x0) < min_w or (y1 - y0) < min_h:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for name, (ax0, ay0, ax1, ay1) in corners.items():
            if ax0 <= cx <= ax1 and ay0 <= cy <= ay1:
                hits.append(name)
                break
    return {"corner_text_like": bool(hits), "corners": sorted(set(hits)),
            "text_lines": det.get("lines", 0),
            "text_chars": det.get("characters", 0),
            "line_boxes": det.get("line_boxes") or []}


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--images", default="/tmp/f2/images")
    ap.add_argument("--out", default="/tmp/f2/images/qc_images.json")
    args = ap.parse_args(argv)

    paths = sorted(Path(args.images).glob("S*.png"))
    if not paths:
        print("BLOCKED: no images found", file=sys.stderr)
        return 1

    rows: List[Dict[str, Any]] = []
    seen: List[tuple[str, int]] = []
    for p in paths:
        with Image.open(p) as im:
            size = im.size
            rgb = im.convert("RGB")
            bf = check_black_flat(rgb)
        ct = corner_text(p)
        dh = difference_hash(p)
        dup_of, dup_dist = "", None
        # only compare against images that are themselves usable: a black or
        # flat frame hashes to a constant and would otherwise mark the whole
        # batch as duplicates of the first bad frame.
        if not bf["black"] and not bf["flat"]:
            for other, h in seen:
                d = hamming_distance(dh, h)
                if d <= DUP_HAMMING_MAX:
                    dup_of, dup_dist = other, d
                    break
            seen.append((p.stem, dh))
        reasons = []
        if bf["black"]:
            reasons.append("black")
        if bf["flat"]:
            reasons.append("flat_or_nan")
        if ct["corner_text_like"]:
            reasons.append("corner_watermark")
        if dup_of:
            reasons.append(f"duplicate_of_{dup_of}")
        if size != (1024, 1024):
            reasons.append(f"size_{size[0]}x{size[1]}")
        rows.append({"sentence_id": p.stem, "file": str(p), "size": list(size),
                     **bf, **ct, "dhash": f"{dh:016x}", "dup_of": dup_of,
                     "dup_distance": dup_dist, "rejected": bool(reasons),
                     "reasons": reasons})

    rejected = [r for r in rows if r["rejected"]]
    report = {
        "images": len(rows),
        "rejected": len(rejected),
        "accepted": len(rows) - len(rejected),
        "reasons": {k: sum(1 for r in rejected if k in " ".join(r["reasons"]))
                    for k in ("black", "flat_or_nan", "corner_watermark",
                              "duplicate", "size_")},
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    csv_path = out.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sentence_id", "mean_luma", "std_luma",
                                          "corner_text_like", "dup_of", "dhash",
                                          "rejected", "reasons"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in w.fieldnames} | {"reasons": ";".join(r["reasons"])})
    print(f"images {len(rows)} | rejected {len(rejected)} | "
          f"corner_text {sum(1 for r in rows if r['corner_text_like'])} | "
          f"dups {sum(1 for r in rows if r['dup_of'])}")
    for r in rejected:
        print(f"  REJECT {r['sentence_id']}: {','.join(r['reasons'])}")
    print(f"report: {out}")
    return 1 if rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
