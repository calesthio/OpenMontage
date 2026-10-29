"""Burn the Ngày 8 captions, sized for a phone screen.

The .ass is written by hand rather than handed to libass as an .srt. Converting
an .srt assumes PlayResY=288, so every FontSize and MarginV is silently scaled by
1280/288: the first attempt asked for a 25px font 112px off the bottom and got
one big enough to re-wrap into four lines, sitting in the middle of the frame
over the subject. Declaring the real frame size makes every number here pixels.

Contrast, for footage that is almost entirely cream and pale gold: white fill,
near-black outline five pixels thick, plus a shadow. A thin outline disappears
into a bright background — this is the one place where more is correct.

    python scripts/_caption_ngay8.py
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import textwrap
from pathlib import Path

W, H = 720, 1280
FONT_PX = 52
# TikTok's own UI — caption, username, side buttons — covers roughly the bottom
# fifth. 250px clears it while keeping the text low enough not to sit on the
# subject's face.
MARGIN_V = 250
WRAP = 20                     # characters per line before a break
BREAK = chr(92) + "N"         # the ASS line break, kept out of an f-string

HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Segoe UI Black,{FONT_PX},&H00FFFFFF,&H00FFFFFF,&H00101010,&HB0000000,0,0,0,0,100,100,0.6,0,1,5,2,2,60,60,{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def stamp(seconds: float) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{int(hours):d}:{int(minutes):02d}:{secs:05.2f}"


def wrap(text: str) -> str:
    """Break at WRAP characters and stop there.

    An earlier version forced everything to two lines by splitting at the
    midpoint. That is not a decision this function gets to make: at 52px there
    is room for about 22 characters between the margins, so a forced 28-character
    line just gets re-wrapped by libass anyway — and the result was a three-line
    caption that the code claimed could not happen. Wrapping once, at a width
    that actually fits, means what is written here is what appears.
    """
    return BREAK.join(textwrap.wrap(text, width=WRAP, break_long_words=False))


SRT_TIME = re.compile(r"(\d\d):(\d\d):(\d\d),(\d\d\d) --> (\d\d):(\d\d):(\d\d),(\d\d\d)")


def read_srt(path: Path) -> list[tuple[float, float, str]]:
    """Cues from an .srt, as (start, end, text)."""
    cues = []
    for chunk in path.read_text(encoding="utf-8").replace("\r", "").split("\n\n"):
        lines = [l for l in chunk.split("\n") if l.strip()]
        stamped = next((i for i, l in enumerate(lines) if SRT_TIME.search(l)), None)
        if stamped is None or len(lines) <= stamped + 1:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (
            int(g) for g in SRT_TIME.search(lines[stamped]).groups())
        cues.append((h1 * 3600 + m1 * 60 + s1 + ms1 / 1000,
                     h2 * 3600 + m2 * 60 + s2 + ms2 / 1000,
                     " ".join(lines[stamped + 1:])))
    return cues


def shift_after(cues, seam: float, amount: float):
    """Pull cues back across a dissolve.

    A cross-dissolve overlaps its two clips, so every frame after the seam
    arrives `amount` earlier than in the cut the subtitles were written against.
    Leaving the .srt alone drifts the whole second half late and pushes the last
    line past the end of the picture.
    """
    def move(t):
        return max(0.0, t - amount) if t > seam else t
    return [(move(a), move(b), text) for a, b, text in cues]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--assets", default="projects/duoi-tan-hoa-ngay-8/assets")
    parser.add_argument("--srt", default=None,
                        help="subtitles to burn; without it, cues.json is used")
    parser.add_argument("--in", dest="source", default="_cut_vo.mp4")
    parser.add_argument("--out", default="_cut_cap.mp4")
    parser.add_argument("--seam", type=float, default=None,
                        help="seconds at which a dissolve shortens the cut")
    parser.add_argument("--overlap", type=float, default=0.45,
                        help="length of that dissolve")
    args = parser.parse_args()

    assets = Path(args.assets)
    if args.srt:
        cues = read_srt(Path(args.srt))
    else:
        cues = [tuple(c) for c in
                json.loads((assets / "cues.json").read_text(encoding="utf-8"))]
    if args.seam is not None:
        cues = shift_after(cues, args.seam, args.overlap)

    events = [f"Dialogue: 0,{stamp(a)},{stamp(b)},Cap,,0,0,0,,{wrap(text)}"
              for a, b, text in cues]
    (assets / "captions.ass").write_text(HEAD + "\n".join(events) + "\n",
                                         encoding="utf-8")
    print(f"captions.ass — {len(events)} cues, last ends {cues[-1][1]:.2f}s, "
          f"{FONT_PX}px, {MARGIN_V}px off the bottom")

    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", args.source,
                    "-vf", "ass=captions.ass",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "19",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", args.out],
                   cwd=assets, check=True)
    print(f"burned -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
