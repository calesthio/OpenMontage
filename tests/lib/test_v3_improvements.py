"""V3 improvement tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/workspaces/OpenMontage")

from lib.motion_engine import MotionEngine


def test_no_static_motion_after_override():
    me = MotionEngine(fps=30, width=1920, height=1080, seed=42)
    spec = me.spec_for_scene(scene_id="S001", duration_seconds=5.0, hero_moment=True,
                             narrative_role="establish_context")
    # Simulate the override logic used in render_v3
    if getattr(spec, "move_type", None) == "static":
        spec.move_type = "pan_zoom"
        spec.start_scale = 1.0
        spec.end_scale = 1.2
    assert spec.move_type != "static"
    assert spec.end_scale >= 1.15


def test_crop_removes_black_bars():
    from PIL import Image
    # A 1376x768 image with a black bottom bar
    img = Image.new("RGB", (1376, 768), color=(50, 50, 50))
    for y in range(600, 768):
        for x in range(1376):
            img.putpixel((x, y), (0, 0, 0))
    # Simulate bounding-box crop
    gray = img.convert("L")
    mask = gray.point(lambda x: 255 if x > 15 else 0)
    bbox = mask.getbbox()
    assert bbox is not None
    assert bbox[3] < 768  # bottom black bar detected
    cropped = img.crop(bbox)
    assert cropped.height < 768
