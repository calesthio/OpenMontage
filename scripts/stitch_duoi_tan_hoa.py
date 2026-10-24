"""Stitch the eight 'Dưới tán hoa — Ngày 10' shots into the 9:16 master.

The two Vietnamese cards are burned in here rather than kept in a sidecar
subtitle file: the deliverable is a vertical short that gets uploaded straight
to a feed, and feeds do not carry .srt. There is no voice-over — no TTS
provider on this machine speaks Vietnamese — so these cards and the shop logo
on the final marker carry the entire text of the piece.

    python scripts/stitch_duoi_tan_hoa.py [--dir <clip-dir>] [--out <mp4>]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

FONT = "C\:/Windows/Fonts/arial.ttf"
OPEN_TEXT = "10 ngày trước khi hoa nở…"      # overridable per episode
# The shop name is not drawn as text any more: shot 8's marker carries the real
# logo, printed into the frame Flow animated. A caption repeating it would sit
# on top of the sign saying the same thing twice.
END_SMALL = "CÒN 10 NGÀY"
FADE = 0.6                     # seconds each card takes to appear and leave


def probe_duration(clip: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(clip)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


# White on Ngày 9 and 10 sat over dark tilled soil and read cleanly. Ngày 8 moved
# indoors onto a cream tablecloth in full sunrise, where white text on white cloth
# is invisible — so the colour is a flag now, defaulting to the old value so
# re-running the earlier episodes is unchanged.
CARD_COLOUR = "white"
CARD_SHADOW = "black@0.35"


def card(text: str, size: int, y: str, start: float, end: float) -> str:
    """One drawtext filter that fades in, holds, and fades out."""
    safe = text.replace(":", r"\:").replace("'", r"\'").replace(",", r"\,")
    alpha = (f"if(lt(t,{start}),0,"
             f"if(lt(t,{start + FADE}),(t-{start})/{FADE},"
             f"if(lt(t,{end - FADE}),1,"
             f"if(lt(t,{end}),({end}-t)/{FADE},0))))")
    return (f"drawtext=fontfile='{FONT}':text='{safe}':fontsize={size}:"
            f"fontcolor={CARD_COLOUR}:alpha='{alpha}':x=(w-text_w)/2:y={y}:"
            f"shadowcolor={CARD_SHADOW}:shadowx=1:shadowy=1")


def main() -> int:
    global CARD_COLOUR, CARD_SHADOW

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", default="projects/duoi-tan-hoa-ngay-10/assets/v2/video")
    parser.add_argument("--out", default=None)
    parser.add_argument("--open-text", default=OPEN_TEXT,
                        help="the card over the first shot")
    parser.add_argument("--card-colour", default=CARD_COLOUR,
                        help="drawtext fontcolor for both cards")
    parser.add_argument("--card-shadow", default=CARD_SHADOW,
                        help="drawtext shadowcolor, e.g. white@0.6")
    parser.add_argument("--dissolve-into", type=int, default=None, metavar="N",
                        help="cross-dissolve into clip N (1-based); every other seam "
                             "stays a hard cut, matching the published episodes")
    parser.add_argument("--dissolve", type=float, default=0.45,
                        help="dissolve length in seconds (reference measured 0.47)")
    parser.add_argument("--expect", type=int, default=None, metavar="N",
                        help="fail unless exactly N numbered clips are found; the "
                             "count differs per episode, so there is no default")
    parser.add_argument("--end-text", default=END_SMALL,
                        help="the card over the last shot")
    args = parser.parse_args()
    CARD_COLOUR, CARD_SHADOW = args.card_colour, args.card_shadow

    clip_dir = Path(args.dir)
    clips = sorted(c for c in clip_dir.glob("*.mp4")
                   if len(c.stem) > 2 and c.stem[:2].isdigit())
    if len(clips) < 2:
        raise SystemExit(f"need at least 2 numbered clips in {clip_dir}, found {len(clips)}")
    if args.expect is not None and len(clips) != args.expect:
        raise SystemExit(f"expected {args.expect} numbered clips in {clip_dir}, "
                         f"found {len(clips)}: {', '.join(c.stem for c in clips)}")

    out = Path(args.out or (clip_dir / "duoi_tan_hoa_ngay10_9x16.mp4"))
    # The concat demuxer needs a list file; ffmpeg resolves its paths relative
    # to the list, so write it beside the clips.
    listing = clip_dir / "_concat.txt"

    spans = [probe_duration(c) for c in clips]

    # Transitions, measured off the published episode rather than chosen: five of
    # its six seams are hard cuts of one or two frames, and exactly one is a soft
    # ~0.47s dissolve — the seam joining its two underground shots, i.e. two views
    # of the same world in the same moment. Putting an effect on every seam is not
    # "adding polish", it is leaving the series' grammar.
    #
    # So --dissolve-into N names the ONE clip a dissolve leads into (1-based), and
    # every other seam stays a straight cut. The dissolve overlaps, so the master
    # comes out shorter by its duration; that is reported, not hidden.
    seam = args.dissolve_into
    if seam:
        if not 2 <= seam <= len(clips):
            raise SystemExit(f"--dissolve-into must be between 2 and {len(clips)}")
        before, after = clips[:seam - 1], clips[seam - 1:]
        parts = []
        for name, group in (("_a", before), ("_b", after)):
            part_list = clip_dir / f"_concat{name}.txt"
            part_list.write_text("".join(f"file '{c.name}'\n" for c in group),
                                 encoding="utf-8")
            part = clip_dir / f"_part{name}.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                            "-i", str(part_list), "-c", "copy", str(part)], check=True)
            part_list.unlink()
            parts.append(part)

        head_len = probe_duration(parts[0])
        faded = clip_dir / "_faded.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(parts[0]), "-i", str(parts[1]),
             "-filter_complex",
             f"[0:v][1:v]xfade=transition=fade:duration={args.dissolve}:"
             f"offset={head_len - args.dissolve}[v];"
             f"[0:a][1:a]acrossfade=d={args.dissolve}[a]",
             "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "slow", "-crf", "18",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", str(faded)],
            check=True)
        for part in parts:
            part.unlink()
        listing.write_text(f"file '{faded.name}'\n", encoding="utf-8")
        spans = [probe_duration(faded)]
    else:
        listing.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")

    total = sum(spans)
    last_start = total - spans[-1]

    # Ngày 8's end card is two lines, Ngày 10's was one. Rather than teach the
    # caller a layout, "--end-text a|b" stacks b under a; a plain string still
    # renders exactly as it did before.
    #
    # An empty text drops that card entirely. Burned-in captions are the editing
    # step's business, not this one's, and a master that already carries them
    # cannot be re-captioned — so `--open-text "" --end-text ""` is how a clean
    # deliverable comes out, and drawtext is skipped rather than asked to render
    # nothing.
    head, _, tail = args.end_text.partition("|")
    cards = [
        (args.open_text, 26, "h*0.80", 0.8, spans[0] - 0.7),
        (head, 24, "h*0.82", last_start + 1.6, total),
        (tail, 19, "h*0.86", last_start + 2.2, total),
    ]
    filters = ",".join(card(text.strip(), *rest)
                       for text, *rest in cards if text.strip())

    command = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
               "-i", str(listing)]
    if filters:
        command += ["-vf", filters]
    command += ["-c:v", "libx264", "-preset", "slow", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", str(out)]
    subprocess.run(command, check=True)
    listing.unlink()
    faded = clip_dir / "_faded.mp4"
    if faded.is_file():
        faded.unlink()

    size_mb = out.stat().st_size / 1_048_576
    print(f"{out}  {probe_duration(out):.2f}s  {size_mb:.1f} MiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
