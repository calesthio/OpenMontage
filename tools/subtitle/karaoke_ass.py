#!/usr/bin/env python3
"""Word-level karaoke ASS subtitle generator for vertical (TikTok) video.

Converts word timestamps -- as produced by ``tools/analysis/transcriber.py``
(``word_timestamps``: a list of ``{"word", "start", "end", "probability"}``) --
into an ASS file whose lines highlight word-by-word using inline ``\\k``/``\\kf``
karaoke tags.

A plain ``.srt`` is accepted as a degraded fallback: without word timings each
subtitle line sweeps as a single unit (segment-level highlight).

Deliberately stdlib-only and NOT a ``BaseTool`` subclass, so it stays runnable
as a bare CLI with no project imports.

ASS karaoke colour semantics (easy to invert -- verify visually):
    SecondaryColour = the not-yet-spoken fill  -> white base
    PrimaryColour   = the already-spoken fill  -> saturated accent

Usage:
    python tools/subtitle/karaoke_ass.py transcript.json -o out.ass
    python tools/subtitle/karaoke_ass.py captions.srt -o out.ass --alignment 8
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --- Defaults tuned for 1080x1920 -------------------------------------------
# Usable width = 1080 - 2*MARGIN_H. Arial Bold averages ~0.55 * font size per
# character, so ~24 chars at 64px fills roughly 845px of the 920px usable band.
PLAY_RES_X = 1080
PLAY_RES_Y = 1920
DEFAULT_FONT = "Arial"
DEFAULT_FONT_SIZE = 64
DEFAULT_MAX_WORDS = 5
DEFAULT_MAX_CHARS = 24
DEFAULT_MARGIN_H = 80
DEFAULT_MARGIN_V = 320
DEFAULT_ALIGNMENT = 2  # numpad: 2 = bottom-centre, 5 = middle, 8 = top
DEFAULT_BASE_RGB = "FFFFFF"
DEFAULT_HIGHLIGHT_RGB = "FFD400"
DEFAULT_OUTLINE_RGB = "000000"
DEFAULT_OUTLINE = 5.0
DEFAULT_SHADOW = 3.0
DEFAULT_BAND_RGB = "000000"
DEFAULT_BAND_OPACITY = 0.65
DEFAULT_BAND_PAD = 14.0
# BorderStyle 4 = libass "background box": one box behind the whole line,
# text outline preserved. BorderStyle 3 = classic VSFilter opaque box, which
# fills with OutlineColour and therefore replaces the text outline.
DEFAULT_BAND_STYLE = 4
DEFAULT_MASK_RGB = "000000"
DEFAULT_MASK_OPACITY = 1.0
DEFAULT_MASK_PAD = 18.0
DEFAULT_MASK_WIDTH_PCT = 100.0
# Nominal line box as a multiple of font size, used only to size the full-width
# mask. Tune the result with --mask-pad / --mask-offset rather than this.
LINE_HEIGHT_RATIO = 1.2
# Bridge mask events across gaps shorter than this so the bar does not flicker
# between consecutive caption lines.
MASK_MERGE_SECONDS = 0.6
# Captions sit on layer 1 so the mask bar on layer 0 renders underneath them.
TEXT_LAYER = 1
# Split a line when speech pauses longer than this, so a held line does not
# straddle a silence.
GAP_SPLIT_SECONDS = 0.7
# Hold the fully-highlighted line briefly so it does not blink out on the beat.
LINE_TAIL_SECONDS = 0.15
# Minimum silence between consecutive events. Zero-length or overlapping events
# trigger libass collision stacking, which moves the caption off its margin.
LINE_GAP_SECONDS = 0.01
# Rough Arial-Bold advance width as a fraction of font size, for the
# overflow warning only. Never used to rescale text.
AVG_CHAR_WIDTH_RATIO = 0.55

_SRT_TIME = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})"
)


# --- Formatting helpers ------------------------------------------------------

def ass_timestamp(seconds: float) -> str:
    """Format seconds as an ASS timestamp: H:MM:SS.cc (centisecond precision)."""
    total_cs = int(round(max(0.0, seconds) * 100))
    h, rem = divmod(total_cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, cs = divmod(rem, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _bgr(rgb: str) -> str:
    """Normalise an RRGGBB hex string to the BBGGRR order ASS uses."""
    value = rgb.strip().removeprefix("#").removeprefix("&H").removeprefix("&h").upper()
    if len(value) != 6 or any(c not in "0123456789ABCDEF" for c in value):
        raise ValueError(f"Colour must be 6 hex digits (RRGGBB), got: {rgb!r}")
    return f"{value[4:6]}{value[2:4]}{value[0:2]}"


def ass_colour(rgb: str, alpha: str = "00") -> str:
    """Convert an RRGGBB hex string to a style-field &HAABBGGRR colour."""
    return f"&H{alpha}{_bgr(rgb)}"


def inline_colour(rgb: str) -> str:
    """Convert an RRGGBB hex string to an inline override &HBBGGRR& colour."""
    return f"&H{_bgr(rgb)}&"


def alpha_hex(opacity: float) -> str:
    """Convert 0.0-1.0 opacity to an ASS alpha byte (00 = opaque)."""
    return format(max(0, min(255, round(255 * (1.0 - opacity)))), "02X")


def sanitize(text: str) -> str:
    """Neutralise characters that would be parsed as ASS override syntax."""
    return (
        text.replace("\\", "/")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )


# --- Input loading -----------------------------------------------------------

def load_words(path: Path) -> list[dict]:
    """Load word timings from a transcriber JSON file.

    Accepts the transcriber's top-level dict (``word_timestamps``, or
    ``segments[].words``) as well as a bare list of word dicts.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(raw, list):
        candidates = raw
    elif isinstance(raw, dict):
        candidates = raw.get("word_timestamps") or []
        if not candidates:
            candidates = [
                word
                for segment in raw.get("segments", [])
                for word in segment.get("words", [])
            ]
    else:
        raise ValueError(f"Unsupported JSON root type: {type(raw).__name__}")

    words = []
    for entry in candidates:
        # faster-whisper emits word.word with a leading space; keep the strip.
        text = sanitize(str(entry.get("word", "")))
        if not text:
            continue
        try:
            start = float(entry["start"])
            end = float(entry["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Word entry missing usable start/end: {entry!r}") from exc
        word = {"word": text, "start": start, "end": max(end, start)}
        if entry.get("line_id") is not None:
            word["line_id"] = entry["line_id"]
        words.append(word)

    if not words:
        raise ValueError(f"No word timestamps found in {path}")
    return words


def load_srt_segments(path: Path) -> list[dict]:
    """Load segment-level cues from a .srt file (degraded fallback)."""
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip())
    segments = []
    for block in blocks:
        lines = block.split("\n")
        time_index = next((i for i, l in enumerate(lines) if _SRT_TIME.search(l)), None)
        if time_index is None:
            continue
        g = _SRT_TIME.search(lines[time_index]).groups()
        nums = [int(x.ljust(3, "0")) if i in (3, 7) else int(x) for i, x in enumerate(g)]
        start = nums[0] * 3600 + nums[1] * 60 + nums[2] + nums[3] / 1000.0
        end = nums[4] * 3600 + nums[5] * 60 + nums[6] + nums[7] / 1000.0
        text = sanitize(" ".join(lines[time_index + 1:]))
        if text:
            segments.append({"text": text, "start": start, "end": max(end, start)})

    if not segments:
        raise ValueError(f"No cues found in {path}")
    return segments


# --- Line grouping -----------------------------------------------------------

def group_words(words: list[dict], max_words: int, max_chars: int) -> list[list[dict]]:
    """Greedily group words into short lines that fit the vertical frame."""
    lines: list[list[dict]] = []
    current: list[dict] = []

    for word in words:
        if current:
            candidate_len = len(" ".join(w["word"] for w in current)) + 1 + len(word["word"])
            gap = word["start"] - current[-1]["end"]
            too_long = candidate_len > max_chars or len(current) >= max_words
            # A caller that already knows its caption units (e.g. a TTS script whose
            # lines were written to the caption width) tags words with line_id; never
            # merge across that boundary or the authored line breaks are lost.
            new_line = word.get("line_id") is not None and word["line_id"] != current[-1].get("line_id")
            if too_long or gap > GAP_SPLIT_SECONDS or new_line:
                lines.append(current)
                current = []
        current.append(word)

    if current:
        lines.append(current)
    return lines


def split_text(text: str, max_words: int, max_chars: int) -> list[str]:
    """Split a plain string into short lines using the same width budget."""
    chunks: list[str] = []
    current: list[str] = []
    for token in text.split():
        candidate = " ".join(current + [token])
        if current and (len(candidate) > max_chars or len(current) >= max_words):
            chunks.append(" ".join(current))
            current = []
        current.append(token)
    if current:
        chunks.append(" ".join(current))
    return chunks


# --- Karaoke line rendering --------------------------------------------------

def karaoke_text(words: list[dict], tag: str) -> str:
    r"""Render one line's words as ``{\kf<cs>}word`` runs.

    Each word's karaoke slice runs until the *next* word starts, so pauses
    between words are absorbed rather than freezing the highlight. Centisecond
    boundaries are rounded cumulatively from the line start, so rounding error
    cannot accumulate across the line.
    """
    line_start = words[0]["start"]
    parts = []
    elapsed_cs = 0

    for index, word in enumerate(words):
        is_last = index == len(words) - 1
        boundary = word["end"] if is_last else max(word["end"], words[index + 1]["start"])
        absolute_cs = int(round((boundary - line_start) * 100))
        duration_cs = max(1, absolute_cs - elapsed_cs)
        elapsed_cs += duration_cs
        prefix = "" if index == 0 else " "
        parts.append(f"{prefix}{{\\{tag}{duration_cs}}}{word['word']}")

    return "".join(parts)


def dialogue(start: float, end: float, text: str,
             style: str = "Karaoke", layer: int = 0) -> str:
    return (
        f"Dialogue: {layer},{ass_timestamp(start)},{ass_timestamp(end)},"
        f"{style},,0,0,0,,{text}"
    )


def warn_wide_lines(texts: list[str], font_size: int, margin_h: int) -> None:
    """Warn (never rescale) when a line's estimated width exceeds the frame."""
    usable = PLAY_RES_X - 2 * margin_h
    for text in texts:
        plain = re.sub(r"\{[^}]*\}", "", text)
        estimated = len(plain) * font_size * AVG_CHAR_WIDTH_RATIO
        if estimated > usable:
            print(
                f"[warn] line may exceed {usable}px (est. {estimated:.0f}px): {plain!r}"
                "\n       lower --font-size or --max-chars; libass will wrap it otherwise.",
                file=sys.stderr,
            )


# --- ASS document ------------------------------------------------------------

def band_fields(opts: argparse.Namespace) -> tuple[int, str, str, float, float]:
    """Resolve (BorderStyle, OutlineColour, BackColour, Outline, Shadow).

    Only ``--mask text`` uses an ASS box border. ``--mask full`` keeps the plain
    outline here and draws its bar as a separate event on a lower layer.
    """
    outline = ass_colour(opts.outline_color)
    if opts.mask != "text":
        return 1, outline, ass_colour(opts.outline_color, alpha="60"), opts.outline, opts.shadow

    band = ass_colour(opts.band_color, alpha=alpha_hex(opts.band_opacity))
    # BorderStyle 3 fills the box with OutlineColour, so the band colour has to
    # go there too; BorderStyle 4 uses BackColour and keeps the text outline.
    box_outline = band if opts.band_style == 3 else outline
    # In box modes the Outline/Shadow fields act as horizontal/vertical padding.
    return opts.band_style, box_outline, band, opts.band_pad, opts.band_pad


def mask_geometry(opts: argparse.Namespace) -> tuple[float, float, float, float]:
    """Return (x, y, width, height) of the full-width mask bar, in PlayRes px.

    The vertical anchor mirrors how libass places the caption for the chosen
    alignment, so the bar lands behind the text rather than beside it.
    """
    line_height = opts.font_size * LINE_HEIGHT_RATIO
    block = opts.mask_lines * line_height
    height = block + 2 * opts.mask_pad
    width = PLAY_RES_X * opts.mask_width_pct / 100.0
    x = (PLAY_RES_X - width) / 2.0

    if opts.alignment in (7, 8, 9):          # anchored to the top edge
        top = opts.margin_v - opts.mask_pad
    elif opts.alignment in (4, 5, 6):        # vertically centred
        top = (PLAY_RES_Y - block) / 2.0 - opts.mask_pad
    else:                                    # anchored to the bottom edge
        top = PLAY_RES_Y - opts.margin_v - block - opts.mask_pad

    return x, top + opts.mask_offset, width, height


def mask_event(start: float, end: float, opts: argparse.Namespace) -> str:
    """One full-width bar, drawn with ASS drawing mode on the layer below the text."""
    x, y, width, height = mask_geometry(opts)
    # an7 + pos anchor the rectangle by its top-left corner and, because the
    # event is positioned, keeps it out of libass collision detection.
    rect = f"m 0 0 l {width:.0f} 0 l {width:.0f} {height:.0f} l 0 {height:.0f}"
    override = (
        rf"\an7\pos({x:.0f},{y:.0f})\bord0\shad0"
        rf"\1c{inline_colour(opts.mask_color)}\1a&H{alpha_hex(opts.mask_opacity)}&\p1"
    )
    return dialogue(start, end, rf"{{{override}}}{rect}{{\p0}}", style="Mask", layer=0)


def mask_events(spans: list[tuple[float, float]], opts: argparse.Namespace) -> list[str]:
    """Build mask bars, merging spans that are close enough to avoid flicker."""
    merged: list[list[float]] = []
    for start, end in spans:
        if merged and start - merged[-1][1] <= MASK_MERGE_SECONDS:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [mask_event(start, end, opts) for start, end in merged]


def with_mask(spans: list[tuple[float, float]], events: list[str],
              opts: argparse.Namespace) -> list[str]:
    """Prepend the full-width mask bars, when --mask full is in effect."""
    if opts.mask != "full":
        return events
    return mask_events(spans, opts) + events


def build_header(opts: argparse.Namespace) -> str:
    base = ass_colour(opts.base_color)
    highlight = ass_colour(opts.highlight_color)
    border_style, outline, shadow, outline_w, shadow_w = band_fields(opts)

    return "\n".join([
        "[Script Info]",
        "; Generated by tools/subtitle/karaoke_ass.py",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        f"PlayResX: {PLAY_RES_X}",
        f"PlayResY: {PLAY_RES_Y}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
        " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut,"
        " ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow,"
        " Alignment, MarginL, MarginR, MarginV, Encoding",
        # PrimaryColour = sung/highlighted, SecondaryColour = not yet sung.
        f"Style: Karaoke,{opts.font},{opts.font_size},{highlight},{base},"
        f"{outline},{shadow},-1,0,0,0,100,100,0,0,{border_style},"
        f"{outline_w},{shadow_w},{opts.alignment},"
        f"{opts.margin_h},{opts.margin_h},{opts.margin_v},1",
        # Neutral style for the drawn mask bar: no border, no shadow, top-left
        # anchored, zero margins, so only the inline overrides shape it.
        f"Style: Mask,{opts.font},{opts.font_size},&H00FFFFFF,&H00FFFFFF,"
        "&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])


def build_events_from_words(words: list[dict], opts: argparse.Namespace) -> list[str]:
    tag = "k" if opts.flash else "kf"
    lines = group_words(words, opts.max_words, opts.max_chars)
    events, texts, spans = [], [], []

    for index, line in enumerate(lines):
        text = karaoke_text(line, tag)
        texts.append(text)
        # The tail must never run into the next line. Overlapping events trip
        # libass collision resolution, which lifts the later line into a second
        # slot for its whole duration -- the caption block visibly jumps.
        end = line[-1]["end"] + LINE_TAIL_SECONDS
        if index + 1 < len(lines):
            end = min(end, lines[index + 1][0]["start"] - LINE_GAP_SECONDS)
        start = line[0]["start"]
        end = max(end, start + 0.01)
        spans.append((start, end))
        events.append(dialogue(start, end, text, layer=TEXT_LAYER))

    warn_wide_lines(texts, opts.font_size, opts.margin_h)
    return with_mask(spans, events, opts)


def build_events_from_segments(segments: list[dict], opts: argparse.Namespace) -> list[str]:
    """Segment-level fallback: each line sweeps as one unit, no word timings."""
    tag = "k" if opts.flash else "kf"
    events, texts, spans = [], [], []
    for segment in segments:
        chunks = split_text(segment["text"], opts.max_words, opts.max_chars)
        total_chars = sum(len(c) for c in chunks) or 1
        span = max(0.0, segment["end"] - segment["start"])
        cursor = segment["start"]
        for chunk in chunks:
            duration = span * len(chunk) / total_chars
            duration_cs = max(1, int(round(duration * 100)))
            text = f"{{\\{tag}{duration_cs}}}{chunk}"
            texts.append(text)
            end = cursor + duration - LINE_GAP_SECONDS
            spans.append((cursor, end))
            events.append(dialogue(cursor, end, text, layer=TEXT_LAYER))
            cursor += duration
    warn_wide_lines(texts, opts.font_size, opts.margin_h)
    return with_mask(spans, events, opts)


def build_ass(input_path: Path, opts: argparse.Namespace) -> str:
    """Build the full ASS document for a transcript JSON or .srt file."""
    if input_path.suffix.lower() == ".srt":
        print("[info] .srt input: segment-level highlight (no word timings)", file=sys.stderr)
        events = build_events_from_segments(load_srt_segments(input_path), opts)
    else:
        events = build_events_from_words(load_words(input_path), opts)
    return build_header(opts) + "\n" + "\n".join(events) + "\n"


# --- CLI ---------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert word timestamps into a karaoke .ass subtitle file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", type=Path,
                        help="Transcript .json (transcriber word_timestamps) or .srt fallback")
    parser.add_argument("-o", "--output", type=Path,
                        help="Output .ass path (default: input with .ass suffix)")
    parser.add_argument("--font", default=DEFAULT_FONT, help="Font family name")
    parser.add_argument("--font-size", type=int, default=DEFAULT_FONT_SIZE)
    parser.add_argument("--max-words", type=int, default=DEFAULT_MAX_WORDS,
                        help="Maximum words per line")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                        help="Maximum characters per line")
    parser.add_argument("--alignment", type=int, default=DEFAULT_ALIGNMENT,
                        choices=range(1, 10),
                        help="ASS numpad alignment (2=bottom, 5=middle, 8=top)")
    parser.add_argument("--margin-v", type=int, default=DEFAULT_MARGIN_V,
                        help="Vertical margin in px from the aligned edge")
    parser.add_argument("--y-pct", type=float,
                        help="Place the caption at this %% of frame height (0=top, 100=bottom); "
                             "overrides --margin-v. Requires a top or bottom --alignment")
    parser.add_argument("--margin-h", type=int, default=DEFAULT_MARGIN_H,
                        help="Left/right margin in px")
    parser.add_argument("--base-color", default=DEFAULT_BASE_RGB,
                        help="RRGGBB fill for not-yet-spoken words")
    parser.add_argument("--highlight-color", default=DEFAULT_HIGHLIGHT_RGB,
                        help="RRGGBB fill for spoken words")
    parser.add_argument("--outline-color", default=DEFAULT_OUTLINE_RGB, help="RRGGBB outline")
    parser.add_argument("--outline", type=float, default=DEFAULT_OUTLINE, help="Outline width px")
    parser.add_argument("--shadow", type=float, default=DEFAULT_SHADOW, help="Shadow depth px")
    parser.add_argument("--flash", action="store_true",
                        help="Use \\k (instant word switch) instead of \\kf (smooth sweep)")
    parser.add_argument("--band", action="store_true", default=False,
                        help="Draw a semi-transparent box behind the caption, sized to the "
                             "text block, to mask burned-in text underneath")
    parser.add_argument("--no-band", action="store_false", dest="band",
                        help="Disable the band (default)")
    parser.add_argument("--band-color", default=DEFAULT_BAND_RGB, help="RRGGBB band fill")
    parser.add_argument("--band-opacity", type=float, default=DEFAULT_BAND_OPACITY,
                        help="Band opacity, 0.0 (invisible) to 1.0 (solid)")
    parser.add_argument("--band-pad", type=float, default=DEFAULT_BAND_PAD,
                        help="Band padding in px around the text")
    parser.add_argument("--band-style", type=int, default=DEFAULT_BAND_STYLE, choices=(3, 4),
                        help="4 = libass background box (keeps text outline); "
                             "3 = classic opaque box (replaces text outline)")
    parser.add_argument("--mask", choices=("none", "text", "full"),
                        help="Backdrop behind the caption: none = outline only; "
                             "text = box hugging the text extent (BorderStyle); "
                             "full = full-bleed bar drawn under the text. "
                             "Defaults to text when --band is given, else none")
    parser.add_argument("--mask-color", default=DEFAULT_MASK_RGB, help="RRGGBB bar fill")
    parser.add_argument("--mask-opacity", type=float, default=DEFAULT_MASK_OPACITY,
                        help="Bar opacity, 0.0 to 1.0; only 1.0 fully hides what is under it")
    parser.add_argument("--mask-pad", type=float, default=DEFAULT_MASK_PAD,
                        help="Vertical padding above and below the caption block, in px")
    parser.add_argument("--mask-lines", type=int, default=1,
                        help="Caption lines the bar must be tall enough to cover")
    parser.add_argument("--mask-width-pct", type=float, default=DEFAULT_MASK_WIDTH_PCT,
                        help="Bar width as a %% of frame width (100 = full bleed)")
    parser.add_argument("--mask-offset", type=float, default=0.0,
                        help="Nudge the bar vertically in px (negative = up)")
    opts = parser.parse_args(argv)
    if opts.mask is None:
        opts.mask = "text" if opts.band else "none"
    opts.margin_v = resolve_margin_v(opts, parser)
    for name in ("band_opacity", "mask_opacity"):
        if not 0.0 <= getattr(opts, name) <= 1.0:
            parser.error(f"--{name.replace('_', '-')} must be between 0.0 and 1.0")
    if not 0.0 < opts.mask_width_pct <= 100.0:
        parser.error("--mask-width-pct must be greater than 0 and at most 100")
    if opts.mask_lines < 1:
        parser.error("--mask-lines must be at least 1")
    return opts


def resolve_margin_v(opts: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Turn --y-pct into a MarginV measured from whichever edge the style anchors to."""
    if opts.y_pct is None:
        return opts.margin_v
    if not 0.0 <= opts.y_pct <= 100.0:
        parser.error("--y-pct must be between 0 and 100")
    if opts.alignment in (4, 5, 6):
        parser.error("--y-pct needs a top (7-9) or bottom (1-3) --alignment; "
                     "middle alignments ignore MarginV")
    fraction = opts.y_pct / 100.0
    if opts.alignment in (7, 8, 9):  # MarginV measured down from the top
        return int(round(PLAY_RES_Y * fraction))
    return int(round(PLAY_RES_Y * (1.0 - fraction)))  # bottom: measured up


def main(argv: list[str] | None = None) -> int:
    opts = parse_args(argv)
    if not opts.input.exists():
        print(f"[error] input not found: {opts.input}", file=sys.stderr)
        return 1

    output = opts.output or opts.input.with_suffix(".ass")
    try:
        document = build_ass(opts.input, opts)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(f"[ok] wrote {output} ({document.count('Dialogue:')} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
