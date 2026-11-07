#!/usr/bin/env python3
"""tools/illustration/text_detect.py - text-like artifact detection.

The previous heuristic (thin near-white horizontal bands in the top/bottom
thirds) missed most lettering and over-fired on flat illustrations with a
wide light band. This detector replaces it with a **connected-component**
method that works on any layout and on both polarities:

  1. grayscale, downscaled to a fixed analysis width,
  2. a local background is estimated with a box blur (integral image),
  3. "ink" = pixels that differ from the local background by more than a
     threshold (dark-on-light AND light-on-dark are both tried),
  4. connected components of the ink mask are found with a run-length
     union-find (no scipy, no OpenCV),
  5. components that look like glyphs (small, character-like aspect, filled)
     are grouped into text lines by their baseline and spacing,
  6. a line of >= 3 glyphs means "text-like".

Flat art produces large components (wrong shape) or no components, so it is
not flagged. Only numpy and Pillow are used - no new runtime dependency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image, ImageOps

#: Analysis width: every image is scaled to this width before the analysis.
ANALYSIS_WIDTH = 1024

#: A pixel is "ink" when it differs from the local background by more than
#: this value (0-255).
INK_DELTA = 14

#: Local background window (in analysis pixels). The background is a local
#: MAX (for dark-on-light) or a local MIN (for light-on-dark) - a morphological
#: opening/closing, which keeps thick strokes detectable.
BACKGROUND_WINDOW = 25

#: Glyph geometry (in analysis pixels, relative to the image height).
GLYPH_MIN_HEIGHT = 3
GLYPH_MAX_HEIGHT_RATIO = 0.09
GLYPH_MIN_WIDTH = 1
GLYPH_MAX_WIDTH_RATIO = 0.08
GLYPH_MIN_ASPECT = 0.04
GLYPH_MAX_ASPECT = 2.2
GLYPH_MIN_FILL = 0.12
GLYPH_MAX_FILL = 0.98

#: A glyph is ink that is THINNER than it is tall: the mean horizontal run
#: length of the component must be at most this fraction of its height. A
#: filled dot (a row of pebbles in a flat plate) has a run length close to
#: its height and is therefore not a character.
GLYPH_MAX_STROKE_RATIO = 0.38

#: A line whose glyphs are all exactly the same size is a repeated ornament
#: (a row of dots), not lettering.
LINE_REPEAT_MAX = 1

#: A text line needs this many glyphs ...
LINE_MIN_CHARACTERS = 3
#: ... whose heights stay within this factor of each other ...
LINE_HEIGHT_TOLERANCE = 1.7

#: ... and whose glyphs are at least this tall (analysis pixels): specks and
#: small pebbles cannot form a text line.
LINE_MIN_HEIGHT = 6

#: Lettering sits on a common baseline: the glyph bottoms of a line may
#: spread by at most this fraction of the line height.
LINE_MAX_BASELINE_SPREAD = 0.35

#: Letters in a word do not overlap horizontally; overlapping marks are a
#: cluster of shapes (a row of blobs), not lettering.
LINE_MAX_OVERLAP = 0
#: ... and whose horizontal gaps stay below this factor of the glyph height.
LINE_MAX_GAP_RATIO = 1.6


def _grayscale_array(path: str | Path) -> np.ndarray:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"image not found: {p}")
    with Image.open(p) as img:
        grey = ImageOps.grayscale(img.convert("RGB"))
        width, height = grey.size
        if width <= 0 or height <= 0:
            raise ValueError(f"invalid image size: {grey.size}")
        if width != ANALYSIS_WIDTH:
            scale = ANALYSIS_WIDTH / width
            grey = grey.resize((ANALYSIS_WIDTH, max(1, int(round(height * scale)))))
        return np.asarray(grey, dtype=np.float32)


def _local_extreme(array: np.ndarray, window: int, is_max: bool) -> np.ndarray:
    """Separable morphological dilation (max) or erosion (min).

    numpy only: the filter runs along the rows and then along the columns, so
    the memory stays at one row-band instead of a full window stack.
    """
    if window < 3:
        return array
    if window % 2 == 0:
        window += 1
    pad = window // 2
    vertical = np.pad(array, ((pad, window - 1 - pad), (0, 0)), mode="edge")
    rows = sliding_window_view(vertical, (window, 1))[:, :, 0]
    tmp = rows.max(axis=-1) if is_max else rows.min(axis=-1)
    horizontal = np.pad(tmp, ((0, 0), (pad, window - 1 - pad)), mode="edge")
    cols = sliding_window_view(horizontal, (1, window))[:, :, 0]
    return cols.max(axis=-1) if is_max else cols.min(axis=-1)


def _components(mask: np.ndarray) -> List[Tuple[int, int, int, int, int]]:
    """Connected components of a boolean mask (4-connectivity).

    Returns (x0, x1, y0, y1, pixel_count) per component. The mask is scanned
    row by row; runs are linked to overlapping runs in the previous row with a
    union-find, so the cost is proportional to the number of runs, not pixels.
    """
    height, width = mask.shape
    parent: List[int] = []

    def find(index: int) -> int:
        root = index
        while parent[root] != root:
            root = parent[root]
        while parent[index] != root:
            parent[index], index = root, parent[index]
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    runs: List[Tuple[int, int, int]] = []          # (y, x0, x1)
    prev: List[Tuple[int, int, int]] = []          # (run index, x0, x1)
    for y in range(height):
        row = mask[y]
        if not row.any():
            prev = []
            continue
        padded = np.concatenate(([False], row, [False]))
        edges = np.flatnonzero(padded[1:] != padded[:-1])
        current: List[Tuple[int, int, int]] = []
        for i in range(0, len(edges) - 1, 2):
            x0, x1 = int(edges[i]), int(edges[i + 1])
            parent.append(len(parent))
            index = len(parent) - 1
            runs.append((y, x0, x1))
            for prev_index, px0, px1 in prev:
                if px0 < x1 and x0 < px1:      # horizontal overlap
                    union(prev_index, index)
            current.append((index, x0, x1))
        prev = current

    boxes: Dict[int, List[int]] = {}
    for index, (y, x0, x1) in enumerate(runs):
        root = find(index)
        box = boxes.get(root)
        if box is None:
            boxes[root] = [x0, x1, y, y, x1 - x0, 1, x1 - x0]
        else:
            box[0] = min(box[0], x0)
            box[1] = max(box[1], x1)
            box[2] = min(box[2], y)
            box[3] = max(box[3], y)
            box[4] += x1 - x0
            box[5] += 1
            box[6] += x1 - x0
    # (x0, x1, y0, y1, pixels, runs, run_pixels)
    return [(b[0], b[1], b[2], b[3], b[4], b[5], b[6])
            for b in boxes.values()]


def _glyph_like(box: Tuple[int, int, int, int, int, int, int],
                width: int, height: int) -> bool:
    x0, x1, y0, y1, count, runs, run_pixels = box
    w = x1 - x0
    h = y1 - y0
    if h < GLYPH_MIN_HEIGHT or h > max(GLYPH_MIN_HEIGHT + 1,
                                       int(height * GLYPH_MAX_HEIGHT_RATIO)):
        return False
    if w < GLYPH_MIN_WIDTH or w > max(GLYPH_MIN_WIDTH + 1,
                                      int(width * GLYPH_MAX_WIDTH_RATIO)):
        return False
    aspect = w / float(h)
    if aspect < GLYPH_MIN_ASPECT or aspect > GLYPH_MAX_ASPECT:
        return False
    fill = count / float(max(1, w * h))
    if not (GLYPH_MIN_FILL <= fill <= GLYPH_MAX_FILL):
        return False
    stroke = run_pixels / float(max(1, runs))
    if stroke > h * GLYPH_MAX_STROKE_RATIO:
        # the ink is as thick as the shape is tall: a dot, not a letter
        return False
    return True


def _text_lines(glyphs: List[Tuple[int, int, int, int, int, int, int]],
                ) -> List[Dict[str, Any]]:
    """Group glyphs into text lines (same baseline, regular spacing)."""
    if not glyphs:
        return []
    ordered = sorted(glyphs, key=lambda g: (g[2], g[0]))
    lines: List[Dict[str, Any]] = []
    current: List[Tuple[int, int, int, int, int, int, int]] = []
    for glyph in ordered:
        if not current:
            current = [glyph]
            continue
        heights = [g[3] - g[2] for g in current]
        base = max(heights)
        height = glyph[3] - glyph[2]
        min_height = min(heights)
        same_line = (abs((glyph[2] + glyph[3]) / 2
                         - sum((g[2] + g[3]) / 2 for g in current) / len(current))
                     <= base * 0.6
                     and height <= base * LINE_HEIGHT_TOLERANCE
                     and height >= min_height / LINE_HEIGHT_TOLERANCE)
        if same_line:
            current.append(glyph)
        else:
            lines.append(_line_record(current))
            current = [glyph]
    if current:
        lines.append(_line_record(current))
    return [line for line in lines
            if line["characters"] >= LINE_MIN_CHARACTERS
            and line["height"] >= LINE_MIN_HEIGHT]


def _line_record(glyphs: List[Tuple[int, int, int, int, int, int, int]]
                 ) -> Dict[str, Any]:
    glyphs = sorted(glyphs, key=lambda g: g[0])
    heights = [g[3] - g[2] for g in glyphs]
    widths = [g[1] - g[0] for g in glyphs]
    gaps = [glyphs[i + 1][0] - glyphs[i][1] for i in range(len(glyphs) - 1)]
    shapes = {(w, h) for w, h in zip(widths, heights)}
    bottoms = [g[3] for g in glyphs]
    overlaps = sum(1 for i in range(len(glyphs) - 1)
                   if glyphs[i + 1][0] < glyphs[i][1] - 2)
    return {
        "characters": len(glyphs),
        "height": max(heights) if heights else 0,
        "max_gap": max(gaps) if gaps else 0,
        "baseline_spread": (max(bottoms) - min(bottoms)) if bottoms else 0,
        "overlaps": overlaps,
        "repeated_shape": len(shapes) == 1,
        "box": [min(g[0] for g in glyphs), max(g[1] for g in glyphs),
                min(g[2] for g in glyphs), max(g[3] for g in glyphs)],
    }


def _lines_are_text_like(lines: List[Dict[str, Any]]) -> bool:
    for line in lines:
        if line["repeated_shape"]:
            # a row of identical marks (dots, pebbles, ticks) is an ornament
            continue
        if line.get("overlaps", 0) > LINE_MAX_OVERLAP:
            # the marks overlap horizontally: a cluster of shapes, not letters
            continue
        if line["baseline_spread"] > line["height"] * LINE_MAX_BASELINE_SPREAD:
            # the glyphs do not share a baseline: scattered marks, not letters
            continue
        if line["max_gap"] <= line["height"] * LINE_MAX_GAP_RATIO:
            return True
    return False


def detect_text_like(path: str | Path) -> Dict[str, Any]:
    """Detect lettering in an image. Returns the evidence, not just a flag."""
    grey = _grayscale_array(path)
    height, width = grey.shape

    best = {"text_like": False, "lines": 0, "characters": 0, "polarity": None,
            "method": "connected_components"}

    for polarity, mask in (
            ("dark_on_light",
             (_local_extreme(grey, BACKGROUND_WINDOW, True) - grey) > INK_DELTA),
            ("light_on_dark",
             (grey - _local_extreme(grey, BACKGROUND_WINDOW, False)) > INK_DELTA)):
        # the background must not dominate the mask
        boxes = _components(mask)
        glyphs = [b for b in boxes if _glyph_like(b, width, height)]
        lines = _text_lines(glyphs)
        if not lines:
            continue
        if not _lines_are_text_like(lines):
            continue
        best = {
            "text_like": True,
            "lines": len(lines),
            "characters": max(line["characters"] for line in lines),
            "polarity": polarity,
            "method": "connected_components",
            "line_boxes": [line["box"] for line in lines[:5]],
        }
        break

    return best
