"""SRT -> ASS caption conversion with real-pixel styling (no ffmpeg needed here)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lib import captions as C  # noqa: E402

SRT = """1
00:00:00,000 --> 00:00:02,853
New in version 3.5: your support requests

2
00:00:02,853 --> 00:00:05,705
to the Circuit Auction team, right inside
the backoffice.

3
01:02:03,456 --> 01:02:04,999
<b>Tagged</b> text {with} braces \\ and a backslash
"""


def test_parse_srt():
    cues = C.parse_srt(SRT)
    assert len(cues) == 3
    assert cues[0] == (0.0, 2.853, "New in version 3.5: your support requests")
    assert cues[1][2] == "to the Circuit Auction team, right inside\nthe backoffice."


def test_srt_to_ass_timestamps():
    assert C.ass_timestamp(0.0) == "0:00:00.00"
    assert C.ass_timestamp(2.853) == "0:00:02.85"
    assert C.ass_timestamp(3723.456) == "1:02:03.46"
    assert C.ass_timestamp(4.999) == "0:00:05.00"


def test_ass_header_declares_real_resolution_and_pixel_style():
    ass = C.srt_to_ass(SRT, size=(1920, 1080), style=C.CaptionStyle())
    assert "PlayResX: 1920" in ass and "PlayResY: 1080" in ass
    style = next(l for l in ass.splitlines() if l.startswith("Style: Caption,"))
    fields = style[len("Style: "):].split(",")
    # Format: Name, Fontname, Fontsize, Primary, Secondary, Outline, Back, Bold, Italic,
    # Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline,
    # Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    assert fields[1] == "Noto Sans" and fields[2] == "60" and fields[7] == "-1"
    # BorderStyle 3 = opaque box; the "outline" is the box padding and must be the
    # box colour (BorderStyle 4 keeps a per-glyph outline in OutlineColour).
    assert fields[15] == "3" and fields[16] == "12" and fields[17] == "0"
    assert fields[5] == fields[6]
    assert fields[18] == "2" and fields[19:22] == ["160", "160", "64"]
    # BackColour alpha: 0.7 opacity -> 0x4D transparency (255*0.3 = 76.5 rounds up) (&HAABBGGRR, alpha = 255*(1-0.7))
    assert fields[6].upper() == "&H4D181410"
    assert fields[3].upper() == "&H00FFFFFF"


def test_ass_events_and_line_breaks():
    ass = C.srt_to_ass(SRT, size=(1920, 1080), style=C.CaptionStyle())
    events = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert events[0] == "Dialogue: 0,0:00:00.00,0:00:02.85,Caption,,0,0,0,,New in version 3.5: your support requests"
    assert events[1].endswith(",,to the Circuit Auction team, right inside\\Nthe backoffice.")


def test_ass_escapes_override_characters():
    ass = C.srt_to_ass(SRT, size=(1920, 1080), style=C.CaptionStyle())
    last = [l for l in ass.splitlines() if l.startswith("Dialogue:")][-1]
    text = last.split(",,", 1)[1]
    assert "<b>" not in text and "Tagged text" in text
    assert "{" not in text and "}" not in text  # braces neutralised
    assert "\\" not in text.replace("\\N", "")  # lone backslashes removed


def test_caption_style_from_recipe_and_scaling():
    s = C.CaptionStyle.from_recipe({"caption_style": {"size_px": 40, "font": "Inter", "bold": False}})
    assert (s.size_px, s.font, s.bold, s.margin_bottom_px) == (40, "Inter", False, 64)
    assert C.CaptionStyle.from_recipe({}) == C.CaptionStyle()
    half = C.CaptionStyle().scaled(540)
    assert (half.size_px, half.margin_bottom_px, half.margin_side_px, half.box_pad_px) == (30, 32, 80, 6)


def test_caption_style_rejects_unknown_keys():
    with pytest.raises(ValueError, match="caption_style"):
        C.CaptionStyle.from_recipe({"caption_style": {"fontsize": 40}})
    with pytest.raises(ValueError, match="size_px"):
        C.CaptionStyle.from_recipe({"caption_style": {"size_px": "big"}})
    with pytest.raises(ValueError, match="box_alpha"):
        C.CaptionStyle.from_recipe({"caption_style": {"box_alpha": 1.5}})


def test_caption_style_rejects_malformed_strings_and_ranges():
    for bad in ("Noto Sans,Bold", "X\nDialogue: 0,0:00:00.00,0:00:01.00,Caption,,0,0,0,,INJECTED", "A{B}", ""):
        with pytest.raises(ValueError, match="font"):
            C.CaptionStyle.from_recipe({"caption_style": {"font": bad}})
    for key in ("text_color", "box_color"):
        for bad in ("red", "#101418", "10141", "GGGGGG"):
            with pytest.raises(ValueError, match=key):
                C.CaptionStyle.from_recipe({"caption_style": {key: bad}})
        assert getattr(C.CaptionStyle.from_recipe({"caption_style": {key: "abcdef"}}), key) == "ABCDEF"
    with pytest.raises(ValueError, match="size_px"):
        C.CaptionStyle.from_recipe({"caption_style": {"size_px": 0}})
    for key in ("margin_bottom_px", "margin_side_px", "box_pad_px"):
        with pytest.raises(ValueError, match=key):
            C.CaptionStyle.from_recipe({"caption_style": {key: -1}})
