#!/usr/bin/env python3
"""Red-then-green tests for tools/packaging/packaging.py (M6).

Thumbnail generator (own graphics, no emblems/people), titles/description/
credits block, YouTube disclosure checklist citing official pages. Offline.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.packaging.packaging import (  # noqa: E402
    generate_thumbnail,
    build_metadata_block,
    disclosure_checklist,
)

TMP = Path("/tmp/kilo_packaging")
TMP.mkdir(parents=True, exist_ok=True)


def test_generate_thumbnail_own_graphics_no_emblem():
    out = TMP / "thumb.jpg"
    res = generate_thumbnail(
        out, title="ISS Earth View", subtitle="From the Cupola",
        accent=(0xE9, 0xC4, 0x6A),
    )
    assert res["ok"] is True
    assert out.is_file()
    assert res["emblem_detected"] is False
    assert res["people_detected"] is False
    assert res["size"][0] >= 1280  # 16:9 thumbnail min width


def test_build_metadata_block():
    block = build_metadata_block(
        title="ISS Earth View from the Cupola",
        description="Earth observation from the International Space Station cupola.",
        tags=["ISS", "Earth observation", "NASA"],
        credits={"footage": "NASA Image & Video Library (public domain)"},
        ai_disclosure=True,
    )
    assert block["title"] == "ISS Earth View from the Cupola"
    assert block["description"]
    assert "ISS" in block["tags"]
    assert block["credits"]["footage"]
    assert block["ai_disclosure"] is True


def test_disclosure_checklist_cites_official_urls():
    checks = disclosure_checklist(ai_illustration=True, paid_promotion=False)
    assert isinstance(checks, list)
    urls = [c["url"] for c in checks if "url" in c]
    # must cite official YouTube support pages
    assert any("support.google.com/youtube" in u for u in urls)
    # AI/synthetic disclosure present when AI used
    assert any("synthetic" in (c.get("topic", "") + c.get("url", "")).lower()
               or "ai" in c.get("topic", "").lower() for c in checks)
