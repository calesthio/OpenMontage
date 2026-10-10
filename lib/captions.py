"""Burned-in caption styling for the ffmpeg tutorial runtime.

Why ASS and not `subtitles=x.srt:force_style=...`: libass gives an SRT a
default PlayRes of 384x288 and scales every style value by video_height/288.
At 1080p that turns FontSize=22 into ~82 px and MarginV=48 into ~180 px — the
"too big / too high" captions. Declaring PlayResX/PlayResY = the real frame
size makes every value below a real pixel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Mapping

_SRT_TIME = re.compile(r"(\d+):(\d\d):(\d\d)[,.](\d{1,3})")
_TAG = re.compile(r"<[^>]+>")
_ALLOWED_RECIPE_KEYS = {
    "font": str, "size_px": int, "bold": bool, "margin_bottom_px": int,
    "margin_side_px": int, "box_alpha": float, "box_pad_px": int,
    "text_color": str, "box_color": str,
}


@dataclass(frozen=True)
class CaptionStyle:
    font: str = "Noto Sans"
    # libass applies Fontsize to the font's line height (ascent+descent), not
    # the em size: 60 here ≈ a 44 px em / ~31 px cap height at 1080p.
    size_px: int = 60
    bold: bool = True
    margin_bottom_px: int = 64
    margin_side_px: int = 160
    box_alpha: float = 0.7         # box opacity 0..1 (the UI behind is mostly white)
    box_pad_px: int = 12
    text_color: str = "FFFFFF"     # RRGGBB
    box_color: str = "101418"      # RRGGBB

    @classmethod
    def from_recipe(cls, recipe: Mapping[str, Any]) -> "CaptionStyle":
        raw = recipe.get("caption_style") or {}
        if not isinstance(raw, Mapping):
            raise ValueError("recipe caption_style must be an object")
        unknown = set(raw) - set(_ALLOWED_RECIPE_KEYS)
        if unknown:
            raise ValueError(f"unknown caption_style keys: {', '.join(sorted(unknown))}")
        clean: dict[str, Any] = {}
        for key, val in raw.items():
            typ = _ALLOWED_RECIPE_KEYS[key]
            if typ is float and isinstance(val, int) and not isinstance(val, bool):
                val = float(val)
            if typ is int and isinstance(val, bool):
                raise ValueError(f"caption_style.{key} must be an integer")
            if not isinstance(val, typ):
                raise ValueError(f"caption_style.{key} must be {typ.__name__}")
            clean[key] = val
        if "box_alpha" in clean and not 0.0 <= clean["box_alpha"] <= 1.0:
            raise ValueError("caption_style.box_alpha must be between 0 and 1")
        return replace(cls(), **clean)

    def scaled(self, height: int) -> "CaptionStyle":
        f = height / 1080.0
        return replace(
            self,
            size_px=max(1, round(self.size_px * f)),
            margin_bottom_px=round(self.margin_bottom_px * f),
            margin_side_px=round(self.margin_side_px * f),
            box_pad_px=round(self.box_pad_px * f),
        )

    def ass_style_line(self) -> str:
        primary = _ass_color(self.text_color, 0.0)
        back = _ass_color(self.box_color, 1.0 - self.box_alpha)
        return (
            "Style: Caption," f"{self.font},{self.size_px},{primary},&H000000FF,&H00000000,{back},"
            f"{-1 if self.bold else 0},0,0,0,100,100,0,0,"
            f"4,{self.box_pad_px},0,2,{self.margin_side_px},{self.margin_side_px},{self.margin_bottom_px},1"
        )


def _ass_color(rrggbb: str, transparency: float) -> str:
    """ASS colours are &HAABBGGRR with AA = transparency (00 opaque, FF invisible)."""
    rr, gg, bb = rrggbb[0:2], rrggbb[2:4], rrggbb[4:6]
    aa = max(0, min(255, round(255 * transparency)))
    return f"&H{aa:02X}{bb}{gg}{rr}".upper()


def ass_timestamp(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def parse_srt(srt_text: str) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    for block in re.split(r"\n\s*\n", srt_text.strip().replace("\r\n", "\n")):
        lines = block.split("\n")
        if len(lines) < 2:
            continue
        # Line 0 is the index (may be absent in sloppy SRTs); find the timing line.
        t_idx = 1 if "-->" in lines[1] else (0 if "-->" in lines[0] else -1)
        if t_idx < 0:
            continue
        times = _SRT_TIME.findall(lines[t_idx])
        if len(times) < 2:
            continue
        start, end = (_to_seconds(t) for t in times[:2])
        text = "\n".join(l.rstrip() for l in lines[t_idx + 1:]).strip()
        if text:
            cues.append((start, end, text))
    return cues


def _to_seconds(t: tuple[str, str, str, str]) -> float:
    h, m, s, ms = t
    return round(int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0, 3)


def _ass_text(text: str) -> str:
    text = _TAG.sub("", text)
    text = text.replace("\\", "")           # a lone backslash starts an override
    text = text.replace("{", "(").replace("}", ")")  # braces delimit override blocks
    return text.replace("\n", "\\N")


def srt_to_ass(srt_text: str, *, size: tuple[int, int], style: CaptionStyle) -> str:
    w, h = size
    head = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {w}",
        f"PlayResY: {h}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style.ass_style_line(),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = [
        f"Dialogue: 0,{ass_timestamp(s)},{ass_timestamp(e)},Caption,,0,0,0,,{_ass_text(t)}"
        for s, e, t in parse_srt(srt_text)
    ]
    return "\n".join(head + events) + "\n"
