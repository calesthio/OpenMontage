"""Burn a caption onto a synthetic 1080p frame and measure where the text lands."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import render_tutorial as RT  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
Image = pytest.importorskip("PIL.Image")


def _burn_frame(tmp_path: Path, srt_text: str, recipe: dict):
    srt = tmp_path / "subs.srt"
    srt.write_text(srt_text)
    ass = RT.build_ass_file(srt, tmp_path / "captions.ass", recipe=recipe, target=(1920, 1080))
    png = tmp_path / "frame.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x2b3a4a:s=1920x1080:d=1",
         "-vf", f"subtitles={ass.name}", "-frames:v", "1", str(png)],
        cwd=str(tmp_path), check=True,
    )
    return Image.open(png).convert("L")


def _bright_bbox(im) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of pixels brighter than 200 (the white glyphs)."""
    w, h = im.size
    px = im.load()
    xs, ys = [], []
    for y in range(h):
        for x in range(0, w, 2):
            if px[x, y] > 200:
                xs.append(x)
                ys.append(y)
    assert xs, "no caption pixels found"
    return min(xs), min(ys), max(xs), max(ys)


ONE_LINE = "1\n00:00:00,000 --> 00:00:05,000\nOpen the Sales area and pick the auction\n"
LONG = ("1\n00:00:00,000 --> 00:00:05,000\n"
        "Each row is a ticket with its status and description. Click it to read the full conversation now\n")


def test_single_line_caption_size_and_position(tmp_path):
    left, top, right, bottom = _bright_bbox(_burn_frame(tmp_path, ONE_LINE, {}))
    text_h = bottom - top
    assert 30 <= text_h <= 60, f"glyph block {text_h}px tall; want ~31px cap height"  # was ~80
    assert 1080 - bottom <= 110, f"text bottom is {1080 - bottom}px above the edge; want < 110"  # was ~180
    assert 1080 - bottom >= 60
    assert left >= 160 and right <= 1760
    assert abs((left + right) / 2 - 960) < 40  # centred


def test_two_line_cue_stays_above_margin(tmp_path):
    left, top, right, bottom = _bright_bbox(_burn_frame(tmp_path, LONG, {}))
    assert left >= 160 and right <= 1760
    assert bottom <= 1080 - 60
    assert 80 <= bottom - top <= 140  # two lines (measured 88px at size 60)


def test_recipe_override_changes_size(tmp_path):
    _, top, _, bottom = _bright_bbox(_burn_frame(tmp_path, ONE_LINE, {"caption_style": {"size_px": 80}}))
    assert bottom - top > 45
