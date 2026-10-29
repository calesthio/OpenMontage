#!/usr/bin/env python3
"""S15: objective, non-aesthetic flags for the 42 style-lock images.

Reuses the verified S10/S7 primitives (no duplicated image maths):
  * black / non-finite pixels          (0 tolerance)
  * blur                               (absolute floor + relative to the
                                        same scene/style/size median)
  * duplicates                         (64-bit dHash, same-scene and global)
  * caption space                      (bottom FIFTH of the frame, per the S15
                                        prompt contract; the S10 0.28 band is
                                        reported too)
  * corner watermark artefact probe    (four corners: faint periodic structure
                                        or text-like marks -> "suspect")

Nothing here judges anatomy, style or beauty. A flag is "look at this frame",
never a verdict; the owner decides what a "suspect" corner means.

Usage:
  python scripts/s15_checks.py \
      --manifest /tmp/kilo/s15_out/s15-style-lock-1/s15_style_lock_dreamshaper-xl-1-0/manifest.json \
      --mapping projects/s15/blind/mapping.json \
      --out docs/openmontage/image_gen/S15_CHECKS.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import s7_checks as _base          # noqa: E402
import s10_checks as _s10          # noqa: E402

DEFAULT_MANIFEST = Path(
    "/tmp/kilo/s15_out/s15-style-lock-1/s15_style_lock_dreamshaper-xl-1-0/"
    "manifest.json")
OUT_PATH = REPO / "docs/openmontage/image_gen/S15_CHECKS.json"

CAPTION_BAND_FRACTION = 0.20       # S15 asks for the bottom FIFTH
LEGACY_BAND_FRACTION = 0.28        # S10 comparison band
BLUR_ABS_FLOOR = 15.0
BLUR_REL_RATIO = 0.35
DUP_SAME_SCENE = 6
DUP_ANY = 4

# corner probe
CORNER_FRACTION = 0.14             # patch side as a share of min(w, h)
PERIODICITY_MIN = 0.40             # 2-D autocorr peak off both axes (lattice)
FINE_ENERGY_MIN = 0.6              # residual amplitude floor (out of 255)
FINE_ENERGY_MAX = 14.0             # above this it is real texture, not a faint mark
TEXT_LIKE_MIN = 0.60               # >= 5 similar blobs aligned like a text row
CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")


def _rgb(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def _gray(path: Path) -> np.ndarray:
    return _base._gray(path)


def _corner_patch(gray: np.ndarray, corner: str) -> np.ndarray:
    h, w = gray.shape
    s = max(24, int(round(min(h, w) * CORNER_FRACTION)))
    if corner == "top_left":
        return gray[:s, :s]
    if corner == "top_right":
        return gray[:s, w - s:]
    if corner == "bottom_left":
        return gray[h - s:, :s]
    return gray[h - s:, w - s:]


def _components(mask: np.ndarray) -> List[Dict[str, int]]:
    """4-connected components of a boolean mask (pure numpy, no scipy)."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    comps: List[Dict[str, int]] = []
    for y0 in range(h):
        for x0 in range(w):
            if not mask[y0, x0] or seen[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            ys: List[int] = []
            xs: List[int] = []
            while stack:
                y, x = stack.pop()
                ys.append(y)
                xs.append(x)
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] \
                            and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            comps.append({"x0": min(xs), "x1": max(xs), "y0": min(ys),
                          "y1": max(ys),
                          "h": max(ys) - min(ys) + 1,
                          "w": max(xs) - min(xs) + 1,
                          "n": len(ys)})
    return comps


def _text_like_row(patch: np.ndarray) -> Tuple[float, int]:
    """Faint marks aligned like a line of text: many similar small blobs.

    This is deliberately stricter than s7's block-edge score: it needs at least
    5 similarly sized blobs whose vertical centres line up, which real
    illustration texture rarely produces in a 14% corner patch.
    """
    blurred = np.asarray(
        Image.fromarray(patch.astype(np.uint8)).filter(
            _image_filter_gaussian(4.0)), dtype=np.float32)
    residual = np.abs(patch - blurred)
    if residual.max() <= 1.0:
        return 0.0, 0
    thr = max(3.0, float(residual.mean()) + 3.0 * float(residual.std()))
    comps = [c for c in _components(residual > thr)
             if 2 <= c["h"] <= patch.shape[0] // 6
             and 2 <= c["w"] <= patch.shape[0] // 2
             and c["n"] >= 6]
    if len(comps) < 5:
        return 0.0, len(comps)
    heights = np.array([c["h"] for c in comps], dtype=np.float32)
    med_h = float(np.median(heights))
    if med_h <= 0:
        return 0.0, len(comps)
    similar = [c for c in comps if 0.5 * med_h <= c["h"] <= 2.0 * med_h]
    if len(similar) < 5:
        return 0.0, len(comps)
    centres = np.array([(c["y0"] + c["y1"]) / 2.0 for c in similar],
                       dtype=np.float32)
    bin_h = max(2.0, med_h)
    bins = np.round(centres / bin_h).astype(int)
    _, counts = np.unique(bins, return_counts=True)
    aligned = int(counts.max()) if counts.size else 0
    score = float(aligned) / 8.0
    return min(1.0, score), len(comps)


def _lattice_score(patch: np.ndarray) -> float:
    """Faint repeating *lattice*: 2-D autocorrelation peak away from both axes.

    A straight scene edge gives a ridge ON one axis (dx=0 or dy=0), so it never
    produces a 2-D offset peak; a tiled watermark or a repeated text row does.
    """
    blurred = np.asarray(
        Image.fromarray(patch.astype(np.uint8)).filter(
            _image_filter_gaussian(2.0)),
        dtype=np.float32)
    residual = patch - blurred
    residual = residual - residual.mean()
    if float(residual.std()) <= 1e-6:
        return 0.0
    spec = np.fft.fft2(residual)
    ac = np.fft.fftshift(np.fft.ifft2(spec * np.conj(spec)).real)
    peak0 = float(ac.max())
    if peak0 <= 0:
        return 0.0
    ac = ac / peak0
    h, w = ac.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.mgrid[0:h, 0:w]
    dx = np.abs(xx - cx)
    dy = np.abs(yy - cy)
    band = (dx >= 4) & (dy >= 4) & (dx <= w // 3) & (dy <= h // 3)
    if not band.any():
        return 0.0
    return round(float(ac[band].max()), 3)


def corner_probe(path: Path) -> Dict[str, Any]:
    """Faint repeating pattern / text-like marks in the four corners."""
    gray = _gray(path)
    out: Dict[str, Any] = {}
    flagged: List[str] = []
    for corner in CORNERS:
        patch = _corner_patch(gray, corner)
        blurred = np.asarray(
            Image.fromarray(patch.astype(np.uint8)).filter(
                _image_filter_gaussian(max(2.0, patch.shape[0] * 0.05))),
            dtype=np.float32)
        fine_energy = float(np.abs(patch - blurred).mean())
        faint = FINE_ENERGY_MIN <= fine_energy <= FINE_ENERGY_MAX
        periodic = _lattice_score(patch)
        text_score, n_comps = _text_like_row(patch)
        periodic_flag = bool(faint and periodic >= PERIODICITY_MIN)
        text_flag = bool(faint and text_score >= TEXT_LIKE_MIN)
        if periodic_flag or text_flag:
            flagged.append(corner)
        out[corner] = {
            "fine_energy": round(fine_energy, 3),
            "periodic_peak": periodic,
            "text_like_score": round(text_score, 3),
            "components": n_comps,
            "periodic_flag": periodic_flag,
            "text_like_flag": text_flag,
        }
    out["flagged_corners"] = flagged
    out["suspect"] = bool(flagged)
    return out


def _image_filter_gaussian(radius: float):
    from PIL import ImageFilter
    return ImageFilter.GaussianBlur(radius=radius)


def check_image(path: Path) -> Dict[str, Any]:
    gray = _gray(path)
    with Image.open(path) as im:
        size = im.size
    cap = _s10.caption_band_metrics(path, CAPTION_BAND_FRACTION)
    cap_legacy = _s10.caption_band_metrics(path, LEGACY_BAND_FRACTION)
    col = _s10.colour_metrics(path)
    corners = corner_probe(path)
    arr = _rgb(path)
    nonfinite = bool((~np.isfinite(arr)).any())
    black = bool(arr.max() < 8.0)
    out = {
        "file": path.name,
        "width": size[0],
        "height": size[1],
        "black": black,
        "nonfinite": nonfinite,
        "laplacian_var": round(_base.laplacian_variance(gray), 3),
        "dhash": _base.dhash(path),
        "caption_fifth": cap,
        "caption_legacy_28": cap_legacy,
        "corners": corners,
    }
    out.update(col)
    return out


def _pct(values: List[float]) -> Optional[float]:
    return round(float(np.mean(values)), 3) if values else None


def run(manifest_path: Path, out_path: Path,
        mapping_path: Optional[Path] = None) -> Dict[str, Any]:
    man = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    base = Path(manifest_path).parent
    images_dir = base / "images"
    rows: List[Dict[str, Any]] = []
    missing: List[str] = []

    for entry in man.get("images", []):
        f = entry.get("file")
        if not f:
            missing.append(entry.get("render_id"))
            continue
        path = images_dir / f
        if not path.is_file():
            missing.append(f)
            continue
        c = check_image(path)
        c.update({
            "render_id": entry["render_id"],
            "scene_id": entry.get("scene_id"),
            "style": entry.get("style"),
            "seed": entry.get("seed"),
            "requested_size": f"{entry.get('width')}x{entry.get('height')}",
            "resolution_ok": (c["width"], c["height"]) == (
                entry.get("width"), entry.get("height")),
            "manifest_black": bool(entry.get("black")),
            "manifest_nonfinite": bool(entry.get("nonfinite")),
            "manifest_seconds": entry.get("seconds"),
            "manifest_sha256": entry.get("sha256"),
        })
        rows.append(c)

    # blur relative to the same scene/style/size cell
    cells: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in rows:
        cells.setdefault((r["scene_id"], r["style"], r["requested_size"]),
                         []).append(r)
    for items in cells.values():
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

    def agg(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "images": len(items),
            "black_or_nan": sum(1 for i in items if i["black"] or i["nonfinite"]),
            "black": sum(1 for i in items if i["black"]),
            "nan": sum(1 for i in items if i["nonfinite"]),
            "resolution_bad": sum(1 for i in items if not i["resolution_ok"]),
            "blur_absolute": sum(1 for i in items if i["blur_flag_absolute"]),
            "blur_relative": sum(1 for i in items if i["blur_flag_relative"]),
            "caption_fifth_flagged": sum(
                1 for i in items if not i["caption_fifth"]["white_text_contrast_flag"]),
            "caption_legacy_flagged": sum(
                1 for i in items
                if not i["caption_legacy_28"]["white_text_contrast_flag"]),
            "watermark_suspect": sum(1 for i in items if i["corners"]["suspect"]),
            "colour_spread_flagged": sum(1 for i in items
                                         if i["colour_spread_flag"]),
            "mean_laplacian_var": _pct([i["laplacian_var"] for i in items]),
            "mean_caption_dark_fraction": _pct(
                [i["caption_fifth"]["dark_fraction"] for i in items]),
            "mean_caption_busy_fraction": _pct(
                [i["caption_fifth"]["busy_fraction"] for i in items]),
            "mean_hue_bins": _pct([i["hue_bins_occupied"] for i in items]),
            "mean_hue_entropy_bits": _pct([i["hue_entropy_bits"] for i in items]),
            "mean_seconds": _pct([i["manifest_seconds"] for i in items
                                  if i.get("manifest_seconds")]),
        }

    square = [r for r in rows if r["requested_size"] == "1024x1024"]
    wide = [r for r in rows if r["requested_size"] != "1024x1024"]
    per_style = {s: agg([r for r in square if r["style"] == s])
                 for s in sorted({r["style"] for r in square})}
    per_scene = {s: agg([r for r in square if r["scene_id"] == s])
                 for s in sorted({r["scene_id"] for r in square})}

    suspects = [{"file": r["file"], "style": r["style"], "scene": r["scene_id"],
                 "seed": r["seed"], "flagged_corners": r["corners"]["flagged_corners"]}
                for r in rows if r["corners"]["suspect"]]

    # owner-facing sheet measurement (plain panels, caption box from mapping)
    sheet_rows: List[Dict[str, Any]] = []
    if mapping_path and Path(mapping_path).is_file():
        mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
        sheet_dir = Path(mapping_path).parent
        for sheet in mapping.get("sheets", []):
            plain = sheet_dir / sheet["plain"]
            if not plain.is_file():
                sheet_rows.append({"sheet": sheet["plain"], "missing": True})
                continue
            arr = _rgb(plain)
            for code, tile in sheet.get("tiles", {}).items():
                x0, y0, x1, y1 = tile["caption_box"]
                crop = arr[y0:y1, x0:x1, :]
                luma = crop.astype(np.float32) @ np.array(
                    [0.299, 0.587, 0.114], dtype=np.float32)
                gy, gx = np.gradient(luma)
                edges = np.abs(gx) + np.abs(gy)
                busy = float((edges > max(1.0, float(edges.max()) * 0.25)).mean()) \
                    if edges.max() > 0 else 0.0
                dark = float((luma < _s10.CAPTION_DARK_LEVEL).mean())
                sheet_rows.append({
                    "sheet": sheet["plain"],
                    "code": code,
                    "style": tile.get("style"),
                    "scene": tile.get("scene"),
                    "mean_luma": round(float(luma.mean()), 2),
                    "std_luma": round(float(luma.std()), 2),
                    "dark_fraction": round(dark, 3),
                    "busy_fraction": round(busy, 3),
                    "white_text_contrast_flag": bool(
                        dark >= _s10.CAPTION_MIN_DARK
                        and busy <= _s10.CAPTION_MAX_BUSY),
                })

    report = {
        "schema_version": "1.0",
        "milestone": "S15",
        "note": "objective flags only. No anatomy, style or beauty verdict is "
                "produced here; the owner's blind scoring decides. 'suspect' "
                "corners are reported for a human look, never auto-rejected.",
        "job_id": man.get("job_id"),
        "model": man.get("model"),
        "model_id": man.get("model_id"),
        "revision": man.get("model_revision"),
        "images_requested": man.get("total_requested") or man.get("requested"),
        "images_checked": len(rows),
        "missing_files": missing,
        "thresholds": {
            "caption_band_fraction": CAPTION_BAND_FRACTION,
            "caption_legacy_band_fraction": LEGACY_BAND_FRACTION,
            "caption_dark_level": _s10.CAPTION_DARK_LEVEL,
            "caption_min_dark_fraction": _s10.CAPTION_MIN_DARK,
            "caption_max_busy_fraction": _s10.CAPTION_MAX_BUSY,
            "blur_abs_laplacian_floor": BLUR_ABS_FLOOR,
            "blur_rel_ratio_of_cell_median": BLUR_REL_RATIO,
            "dup_hamming_same_scene": DUP_SAME_SCENE,
            "dup_hamming_any": DUP_ANY,
            "corner_fraction": CORNER_FRACTION,
            "corner_periodicity_min": PERIODICITY_MIN,
            "corner_fine_energy_min": FINE_ENERGY_MIN,
            "corner_fine_energy_max": FINE_ENERGY_MAX,
            "corner_text_like_min": TEXT_LIKE_MIN,
        },
        "gate_0_black_nan": {
            "black": sum(1 for r in rows if r["black"]),
            "nan": sum(1 for r in rows if r["nonfinite"]),
            "pass": not any(r["black"] or r["nonfinite"] for r in rows),
        },
        "images": rows,
        "duplicates": duplicates,
        "per_style": per_style,
        "per_scene": per_scene,
        "buckets": {"square_1024": agg(square), "wide_1344x768": agg(wide)},
        "watermark_suspects": suspects,
        "sheet_caption_bands": sheet_rows,
    }

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for style, d in per_style.items():
        print(f"{style}: {d['images']} images, black/nan={d['black_or_nan']}, "
              f"blur_abs={d['blur_absolute']}, caption_fifth_flagged="
              f"{d['caption_fifth_flagged']}, watermark_suspect="
              f"{d['watermark_suspect']}")
    print(f"duplicates: {len(duplicates)}; watermark suspects: {len(suspects)}")
    print(f"gate 0 black/NaN: {'PASS' if report['gate_0_black_nan']['pass'] else 'FAIL'}")
    print(f"wrote {out_path}")
    return report


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--mapping", default="")
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args(argv)
    run(Path(args.manifest), Path(args.out),
        Path(args.mapping) if args.mapping else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
