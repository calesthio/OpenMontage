"""Own-graphics cards render at the target size and are byte-deterministic."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess

import pytest

from tools.illustration.cards import make_card, make_section_cards

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


def _probe(path):
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", str(path)], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)["streams"][0]


def test_card_is_1280x720_and_deterministic(tmp_path):
    a = make_card(tmp_path / "a.png", number="01", title="Chapter 1 — The Earth analogue")
    b = make_card(tmp_path / "b.png", number="01", title="Chapter 1 — The Earth analogue")
    stream = _probe(a)
    assert (stream["width"], stream["height"]) == (1280, 720)
    ha = hashlib.sha256(a.read_bytes()).hexdigest()
    hb = hashlib.sha256(b.read_bytes()).hexdigest()
    assert ha == hb, "same inputs must produce the same card bytes"


def test_card_has_content_not_a_blank_frame(tmp_path):
    p = make_card(tmp_path / "c.png", number="07", title="A long chapter title that must wrap")
    res = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(p),
         "-vf", "signalstats,metadata=print:file=-", "-f", "null", "-"],
        capture_output=True, text=True, check=True)
    yavgs = [ln.split("=")[-1] for ln in res.stdout.splitlines()
             if "YAVG" in ln]
    assert yavgs, res.stdout[:200]
    values = [float(v) for v in yavgs]
    # Background fill plus text: the mean luma must be in a sensible range.
    assert all(0.0 <= v <= 255.0 for v in values)
    assert max(values) > 20.0


def test_section_cards_one_per_section(tmp_path):
    sections = [{"title": f"Chapter {i}"} for i in range(1, 4)]
    paths = make_section_cards(sections, tmp_path / "cards")
    assert len(paths) == 3
    assert [p.name for p in paths] == ["card_01.png", "card_02.png", "card_03.png"]
    assert all(p.is_file() and p.stat().st_size > 1000 for p in paths)


def test_empty_title_fails_closed(tmp_path):
    with pytest.raises(ValueError):
        make_card(tmp_path / "empty.png", number="01", title="   ")
