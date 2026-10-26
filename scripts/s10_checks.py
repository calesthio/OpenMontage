#!/usr/bin/env python3
"""S10-4: objective, non-aesthetic flags for the 54 style-test images.

No beauty, no anatomy, no style verdict — flags only:

  * resolution        - vs the requested 1024x1024
  * blur              - Laplacian variance: an absolute floor plus an outlier
                        test against the median of the SAME scene+style (a flat
                        style is legitimately smoother than a gouache plate, so
                        the scene-wide median would flag the whole style)
  * duplicates        - 64-bit dHash, hamming <= 6 inside a scene / <= 4 anywhere
  * caption area      - bottom band of the image (where a burned-in subtitle
                        lives): mean luma, std, dark fraction, edge density and
                        a "white text would read" flag (dark fraction >= 0.35)
  * colour spread     - hue histogram spread over saturated pixels: occupied hue
                        bins, entropy, dominant-bin share, unique colours and a
                        monotone flag (occupied < 4 bins or entropy < 1.5 bits)
  * text-like         - the S7 heuristic, informational only (it is known to
                        over- and under-fire; the report says so)

The captioned blind sheets are measured too, but on the PLAIN sheet panel (the
image area where the caption goes), so the metric is not polluted by the white
glyphs themselves.

Usage:
  python scripts/s10_checks.py \
      --images /tmp/kilo/s10_out/klein/s10_bakeoff_klein/images \
      --manifest /tmp/kilo/s10_out/klein/s10_bakeoff_klein/manifest.json \
      --mapping projects/s10_blind/mapping.json \
      --out docs/openmontage/image_gen/S10_CHECKS.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import s7_checks as _base  # noqa: E402 - reuse the verified S7 primitives

EXPECTED_SIZE = (1024, 1024)
BLUR_ABS_FLOOR = 15.0          # same absolute floor as S7
BLUR_REL_RATIO = 0.35          # same relative ratio as S7
DUP_SAME_SCENE = 6             # same as S7
DUP_ANY = 4                    # same as S7
CAPTION_BAND_FRACTION = 0.28   # matches scripts/s10_blind_pack.py
CAPTION_DARK_LEVEL = 128       # luma below this is "dark enough for white text"
CAPTION_MIN_DARK = 0.35        # minimum dark fraction for a readable white caption
CAPTION_MAX_BUSY = 0.35        # edge-density ceiling in the caption band
HUE_BINS = 36
HUE_SAT_MIN = 0.15
HUE_BIN_MIN_SHARE = 0.01
COLOUR_MIN_BINS = 4
COLOUR_MIN_ENTROPY = 1.5
UNIQUE_QUANT = 5               # bits per channel for the unique-colour count


def _rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def _gray(path: Path) -> np.ndarray:
    return _base._gray(path)


def caption_band_metrics(path: Path,
                         fraction: float = CAPTION_BAND_FRACTION) -> Dict[str, Any]:
    """Metrics for the bottom band where a burned-in subtitle would sit."""
    arr = _rgb(path)
    h = arr.shape[0]
    band = arr[h - max(1, int(round(h * fraction))):, :, :]
    luma = band.astype(np.float32) @ np.array([0.299, 0.587, 0.114],
                                              dtype=np.float32)
    gy, gx = np.gradient(luma)
    edges = np.abs(gx) + np.abs(gy)
    busy = float((edges > max(1.0, float(edges.max()) * 0.25)).mean()) \
        if edges.max() > 0 else 0.0
    dark_fraction = float((luma < CAPTION_DARK_LEVEL).mean())
    readable = bool(dark_fraction >= CAPTION_MIN_DARK and busy <= CAPTION_MAX_BUSY)
    return {
        "band_fraction": fraction,
        "band_px": int(band.shape[0]),
        "mean_luma": round(float(luma.mean()), 2),
        "std_luma": round(float(luma.std()), 2),
        "dark_fraction": round(dark_fraction, 3),
        "busy_fraction": round(busy, 3),
        "white_text_contrast_flag": readable,
        # flag form (True = look at this panel before captioning it)
        "caption_contrast_flag": not readable,
    }


def colour_metrics(path: Path) -> Dict[str, Any]:
    """Hue spread + unique colours, to catch monotone plates."""
    arr = _rgb(path)
    with Image.open(path) as im:
        small = np.asarray(im.convert("RGB").resize((64, 64), Image.LANCZOS),
                           dtype=np.uint8)
        hsv = np.asarray(im.convert("HSV"), dtype=np.float32)
    hue = hsv[:, :, 0] / 255.0 * 360.0
    sat = hsv[:, :, 1] / 255.0
    val = hsv[:, :, 2] / 255.0
    mask = (sat >= HUE_SAT_MIN) & (val >= 0.10)
    n = int(mask.sum())
    if n == 0:
        bins = np.zeros(HUE_BINS, dtype=np.float64)
    else:
        idx = np.clip((hue[mask] / (360.0 / HUE_BINS)).astype(int), 0, HUE_BINS - 1)
        bins = np.bincount(idx, minlength=HUE_BINS).astype(np.float64) / n
    p = bins[bins > 0]
    entropy = float(-(p * np.log2(p)).sum()) if p.size else 0.0
    occupied = int((bins >= HUE_BIN_MIN_SHARE).sum())
    quant = (small >> (8 - UNIQUE_QUANT)) << (8 - UNIQUE_QUANT)
    keys = (quant[:, :, 0].astype(np.int32) << 16) | \
           (quant[:, :, 1].astype(np.int32) << 8) | quant[:, :, 2].astype(np.int32)
    unique = int(np.unique(keys).size)
    spread_flag = bool(occupied < COLOUR_MIN_BINS or entropy < COLOUR_MIN_ENTROPY)
    return {
        "hue_bins_occupied": occupied,
        "hue_entropy_bits": round(entropy, 3),
        "dominant_hue_share": round(float(bins.max()) if bins.size else 0.0, 3),
        "saturated_pixel_share": round(n / float(mask.size), 3),
        "mean_saturation": round(float(sat.mean()), 2),
        "unique_colours_64px": unique,
        "colour_spread_flag": spread_flag,
    }


def check_image(path: Path) -> Dict[str, Any]:
    gray = _gray(path)
    with Image.open(path) as im:
        size = im.size
    text_score = _base.text_like_score(gray)
    out = {
        "file": path.name,
        "width": size[0],
        "height": size[1],
        "resolution_ok": list(size) == list(EXPECTED_SIZE),
        "laplacian_var": round(_base.laplacian_variance(gray), 3),
        "text_like_score": round(text_score, 3),
        "text_like_flag": bool(text_score >= _base.TEXT_ROW_FRACTION),
        "contrast_rms": round(float(gray.std()), 2),
        "dhash": _base.dhash(path),
    }
    out.update(caption_band_metrics(path))
    out.update(colour_metrics(path))
    return out


def _pct(values: List[float]) -> Optional[float]:
    return round(float(np.mean(values)), 3) if values else None


def run(images_dir: Path, manifest_path: Path, out_path: Path,
        mapping_path: Optional[Path] = None,
        sheets_dir: Optional[Path] = None) -> Dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    images_dir = Path(images_dir)
    rows: List[Dict[str, Any]] = []
    missing: List[str] = []
    for entry in manifest.get("images", []):
        if not entry.get("file"):
            missing.append(entry.get("render_id"))
            continue
        path = images_dir / entry["file"]
        if not path.is_file():
            missing.append(entry["file"])
            continue
        c = check_image(path)
        c.update({
            "render_id": entry["render_id"],
            "scene_id": entry.get("scene_id"),
            "style": entry.get("style") or entry.get("variant"),
            "seed": entry.get("seed"),
            "manifest_sha256": entry.get("sha256"),
            "manifest_seconds": entry.get("seconds"),
        })
        rows.append(c)

    # blur: relative to the same scene+style median (a flat style is smoother)
    by_cell: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in rows:
        by_cell.setdefault((r["scene_id"], r["style"]), []).append(r)
    for cell, items in by_cell.items():
        vals = [i["laplacian_var"] for i in items]
        median = float(np.median(vals)) if vals else 0.0
        for i in items:
            i["cell_median_laplacian"] = round(median, 3)
            i["blur_flag_absolute"] = bool(i["laplacian_var"] < BLUR_ABS_FLOOR)
            i["blur_flag_relative"] = bool(
                median > 0 and i["laplacian_var"] < BLUR_REL_RATIO * median)

    # duplicates
    duplicates: List[Dict[str, Any]] = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            d = _base.hamming(a["dhash"], b["dhash"])
            same_scene = a.get("scene_id") == b.get("scene_id")
            if d <= (DUP_SAME_SCENE if same_scene else DUP_ANY):
                duplicates.append({
                    "a": f"{a['style']}:{a['render_id']}",
                    "b": f"{b['style']}:{b['render_id']}",
                    "hamming": d,
                    "same_scene": same_scene,
                })

    # aggregates
    per_style: Dict[str, Any] = {}
    for style in sorted({r["style"] for r in rows}):
        items = [r for r in rows if r["style"] == style]
        per_style[style] = {
            "images": len(items),
            "resolution_bad": sum(1 for i in items if not i["resolution_ok"]),
            "blur_absolute": sum(1 for i in items if i["blur_flag_absolute"]),
            "blur_relative": sum(1 for i in items if i["blur_flag_relative"]),
            "colour_spread_flagged": sum(1 for i in items
                                         if i["colour_spread_flag"]),
            "caption_contrast_flagged": sum(
                1 for i in items if not i["white_text_contrast_flag"]),
            "text_like_flagged": sum(1 for i in items if i["text_like_flag"]),
            "mean_laplacian_var": _pct([i["laplacian_var"] for i in items]),
            "mean_saturation": _pct([i["mean_saturation"] for i in items]),
            "mean_hue_bins": _pct([i["hue_bins_occupied"] for i in items]),
            "mean_hue_entropy_bits": _pct([i["hue_entropy_bits"] for i in items]),
            "mean_caption_dark_fraction": _pct(
                [i["dark_fraction"] for i in items]),
            "mean_seconds": _pct([i["manifest_seconds"] for i in items
                                  if i.get("manifest_seconds")]),
        }
    per_scene: Dict[str, Any] = {}
    for scene in sorted({r["scene_id"] for r in rows}):
        per_scene[scene] = {
            style: {
                "images": len([r for r in rows
                               if r["scene_id"] == scene and r["style"] == style]),
                "colour_spread_flagged": sum(
                    1 for r in rows if r["scene_id"] == scene
                    and r["style"] == style and r["colour_spread_flag"]),
                "caption_contrast_flagged": sum(
                    1 for r in rows if r["scene_id"] == scene
                    and r["style"] == style
                    and not r["white_text_contrast_flag"]),
            }
            for style in sorted({r["style"] for r in rows
                                 if r["scene_id"] == scene})
        }

    # caption area as the owner sees it: the PLAIN sheet panel band
    sheet_rows: List[Dict[str, Any]] = []
    if mapping_path and Path(mapping_path).is_file():
        mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
        base_dir = Path(sheets_dir) if sheets_dir else Path(mapping_path).parent
        for sheet in mapping.get("sheets", []):
            scene = sheet["scene"]
            plain = base_dir / sheet["plain"]
            if not plain.is_file():
                sheet_rows.append({"scene": scene, "file": sheet["plain"],
                                   "missing": True})
                continue
            arr = _rgb(plain)
            for label, panel in mapping.get("panels", {}).get(scene, {}).items():
                x0, y0, x1, y1 = panel["caption_box"]
                crop = arr[y0:y1, x0:x1, :]
                luma = crop.astype(np.float32) @ np.array(
                    [0.299, 0.587, 0.114], dtype=np.float32)
                gy, gx = np.gradient(luma)
                edges = np.abs(gx) + np.abs(gy)
                busy = float((edges > max(1.0, float(edges.max()) * 0.25)).mean()) \
                    if edges.max() > 0 else 0.0
                dark = float((luma < CAPTION_DARK_LEVEL).mean())
                sheet_rows.append({
                    "scene": scene,
                    "sheet": sheet["plain"],
                    "panel": label,
                    "style": panel["style"],
                    "mean_luma": round(float(luma.mean()), 2),
                    "std_luma": round(float(luma.std()), 2),
                    "dark_fraction": round(dark, 3),
                    "busy_fraction": round(busy, 3),
                    "white_text_contrast_flag": bool(
                        dark >= CAPTION_MIN_DARK and busy <= CAPTION_MAX_BUSY),
                })

    report = {
        "schema_version": "1.0",
        "milestone": "S10-4",
        "note": "objective flags only; the owner's blind judgement decides the "
                "style. A flag is 'look at this frame', never a verdict.",
        "job_id": manifest.get("job_id"),
        "model": manifest.get("model"),
        "images_requested": manifest.get("requested"),
        "images_checked": len(rows),
        "missing_files": missing,
        "thresholds": {
            "blur_abs_laplacian_floor": BLUR_ABS_FLOOR,
            "blur_rel_ratio_of_scene_style_median": BLUR_REL_RATIO,
            "dup_hamming_same_scene": DUP_SAME_SCENE,
            "dup_hamming_any": DUP_ANY,
            "caption_band_fraction": CAPTION_BAND_FRACTION,
            "caption_dark_level": CAPTION_DARK_LEVEL,
            "caption_min_dark_fraction": CAPTION_MIN_DARK,
            "caption_max_busy_fraction": CAPTION_MAX_BUSY,
            "hue_bins": HUE_BINS,
            "hue_saturation_floor": HUE_SAT_MIN,
            "hue_bin_min_share": HUE_BIN_MIN_SHARE,
            "colour_min_occupied_bins": COLOUR_MIN_BINS,
            "colour_min_entropy_bits": COLOUR_MIN_ENTROPY,
        },
        "images": rows,
        "duplicates": duplicates,
        "per_style": per_style,
        "per_scene": per_scene,
        "sheet_caption_bands": sheet_rows,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for style, d in per_style.items():
        print(f"{style}: {d['images']} images, res_bad={d['resolution_bad']}, "
              f"blur_abs={d['blur_absolute']}, blur_rel={d['blur_relative']}, "
              f"colour_flagged={d['colour_spread_flagged']}, "
              f"caption_flagged={d['caption_contrast_flagged']}, "
              f"lap_var={d['mean_laplacian_var']}, "
              f"hue_bins={d['mean_hue_bins']}")
    print(f"duplicates: {len(duplicates)}")
    print(f"wrote {out_path}")
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out",
                    default=str(REPO / "docs/openmontage/image_gen/S10_CHECKS.json"))
    ap.add_argument("--mapping", default="")
    ap.add_argument("--sheets-dir", default="")
    args = ap.parse_args(argv)
    run(Path(args.images), Path(args.manifest), Path(args.out),
        Path(args.mapping) if args.mapping else None,
        Path(args.sheets_dir) if args.sheets_dir else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
