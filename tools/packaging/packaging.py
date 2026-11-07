#!/usr/bin/env python3
"""tools/packaging/packaging.py — YouTube packaging module (M6).

Thumbnail generator (own graphics, no emblems/people), titles/description/
credits block, and a disclosure checklist citing official YouTube pages.
No network, no paid routes, no AI upscaling. Pillow only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

PALETTE = {
    "navy": (11, 16, 33),
    "slate": (27, 38, 59),
    "cyan": (79, 195, 247),
    "teal": (42, 157, 143),
    "amber": (233, 196, 106),
    "grey": (141, 153, 174),
    "magenta": (194, 59, 34),
    "paper": (244, 241, 222),
    "ink": (34, 34, 59),
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    cands = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
             else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
             else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    for c in cands:
        if Path(c).is_file():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_thumbnail(out_path, title: str, subtitle: str = "",
                       accent: Tuple[int, int, int] = (79, 195, 247),
                       size: Tuple[int, int] = (1280, 720)) -> Dict[str, Any]:
    """Generate a thumbnail from OWN graphics only (flat vector per style bible).

    No emblems, no people, no logos, no third-party credit. Returns a result
    dict with ok, size, and emblem/people detection flags (always False here
    because the thumbnail is generated procedurally from shapes).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    img = Image.new("RGB", (w, h), PALETTE["navy"])
    d = ImageDraw.Draw(img)
    # flat vector "orbit arc" + "window" graphic (own geometry, not an emblem)
    cx, cy = w // 2, int(h * 0.55)
    d.arc([cx - 180, cy - 180, cx + 180, cy + 180], start=200, end=340,
          fill=PALETTE["cyan"], width=10)
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=PALETTE["amber"])
    # horizon band
    d.rectangle([0, int(h * 0.78), w, h], fill=PALETTE["slate"])
    d.rectangle([0, int(h * 0.72), w, int(h * 0.78)], fill=PALETTE["teal"])
    # title text
    f_title = _font(56, bold=True)
    f_sub = _font(32)
    d.text((60, 60), title, font=f_title, fill=PALETTE["paper"])
    if subtitle:
        d.text((60, 150), subtitle, font=f_sub, fill=PALETTE["cyan"])
    img.save(out_path, quality=92)
    return {
        "ok": True,
        "path": str(out_path),
        "size": img.size,
        "emblem_detected": False,
        "people_detected": False,
        "rights_basis": "own_graphics",
    }


def build_metadata_block(title: str, description: str, tags: List[str],
                         credits: Dict[str, str],
                         ai_disclosure: bool = False,
                         category: str = "Education") -> Dict[str, Any]:
    """Build the titles/description/credits block for upload."""
    return {
        "title": title[:100],
        "description": description,
        "tags": tags[:30],
        "credits": dict(credits),
        "category": category,
        "ai_disclosure": ai_disclosure,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def disclosure_checklist(ai_illustration: bool = False,
                         paid_promotion: bool = False,
                         altered_content: bool = False) -> List[Dict[str, Any]]:
    """Disclosure checklist citing official YouTube support pages.

    Returns list of {topic, url, required, satisfied}.
    """
    items = [
        {
            "topic": "Custom thumbnail requirements",
            "url": "https://support.google.com/youtube/answer/9126714",
            "required": True,
            "satisfied": True,
        },
        {
            "topic": "Paid promotion disclosure",
            "url": "https://support.google.com/youtube/answer/6129482",
            "required": paid_promotion,
            "satisfied": not paid_promotion,
        },
        {
            "topic": "Altered or synthetic content (AI) disclosure",
            "url": "https://support.google.com/youtube/answer/13643031",
            "required": ai_illustration or altered_content,
            "satisfied": not (ai_illustration or altered_content),
        },
        {
            "topic": "Community guidelines — spam, deceptive practices",
            "url": "https://support.google.com/youtube/answer/2801942",
            "required": True,
            "satisfied": True,
        },
    ]
    return items
