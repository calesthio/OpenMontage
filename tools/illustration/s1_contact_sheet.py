#!/usr/bin/env python3
"""S1-5 contact sheet builder: 12-frame contact sheet from selected stills.

Builds a 3x4 (or 4x3) contact sheet PNG from a list of image paths. Neutral
filenames (sheet_01..sheet_12) for blind comparison. Stdlib + Pillow only;
no network, no paid routes, no media committed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image  # noqa: E402 - Pillow is a project dependency


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(path: Path, size: Tuple[int, int]) -> Image.Image:
    with Image.open(path).convert("RGB") as img:
        return img.resize(size, Image.LANCZOS)


def build_contact_sheet(
    image_paths: List[Path],
    out_path: Path,
    cols: int = 4,
    rows: int = 3,
    thumb_w: int = 320,
    thumb_h: int = 180,
    pad: int = 10,
    label: bool = True,
) -> Dict[str, Any]:
    """Build a contact sheet. Returns {sheet_path, sha256, bytes, frames[]}."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = min(len(image_paths), cols * rows)
    used = image_paths[:n]
    sheet_w = cols * thumb_w + (cols + 1) * pad
    sheet_h = rows * thumb_h + (rows + 1) * pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (240, 240, 240))

    frames: List[Dict[str, Any]] = []
    for i, p in enumerate(used):
        r, c = divmod(i, cols)
        x = pad + c * (thumb_w + pad)
        y = pad + r * (thumb_h + pad)
        thumb = _load(p, (thumb_w, thumb_h))
        sheet.paste(thumb, (x, y))
        if label:
            from PIL import ImageDraw, ImageFont  # noqa: E402
            d = ImageDraw.Draw(sheet)
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
                )
            except Exception:
                font = ImageFont.load_default()
            name = f"sheet_{i+1:02d}"
            d.text((x + 6, y + 6), name, fill=(0, 0, 0), font=font)
        frames.append(
            {
                "index": i + 1,
                "sheet_name": f"sheet_{i+1:02d}",
                "source": p.name,
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
                "box": [x, y, thumb_w, thumb_h],
            }
        )

    sheet.save(out_path, optimize=True)
    data = out_path.read_bytes()
    return {
        "sheet_path": str(out_path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "frames": frames,
        "cols": cols,
        "rows": rows,
    }


def write_mapping(frames: List[Dict[str, Any]], mapping_path: Path) -> None:
    """Neutral-name -> source mapping (kept separate from contact sheet)."""
    mapping_path = Path(mapping_path)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping = {
        f["sheet_name"]: {"source": f["source"], "sha256": f["sha256"]}
        for f in frames
    }
    mapping_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
