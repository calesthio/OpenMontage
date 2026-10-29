#!/usr/bin/env python3
"""tools/illustration/cards.py — own-graphics cards (title/chapter/source).

Spec L6 requires original graphics in every episode: chapter cards, key-number
cards, source cards, credit roll. These are drawn by the factory itself, so
they are rights_basis `explicit_license` (own work) rather than licensed
third-party material, and they are the only place where on-screen text is
allowed (AI illustrations must never contain text).

Pure FFmpeg: no network, no fonts beyond DejaVu, identical inputs produce a
byte-identical PNG (no timestamps, fixed drawtext, deterministic encode).
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

PALETTE = {
    "bg": "0x14455C",        # deep teal — STYLE_BIBLE palette
    "accent": "0xA8E06F",    # bioluminescent lime
    "charcoal": "0x3B444B",
    "bone": "0xEDE7D8",      # pale bone
}
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _wrap(text: str, per_line: int = 28, max_lines: int = 3) -> list[str]:
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= per_line or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines


def _drawtext(textfile: Path, x: int, y: int, size: int, color: str,
              font: str, extra: str = "") -> str:
    return (
        f"drawtext=fontfile={font}:textfile={textfile}:x={x}:y={y}:"
        f"fontsize={size}:fontcolor={color}{extra}"
    )


def make_card(
    out_path: str | Path,
    *,
    number: str,
    title: str,
    footer: str = "OPENMONTAGE · SPECULATIVE EVOLUTION · AI ILLUSTRATIONS LABELLED",
    width: int = 1280,
    height: int = 720,
    palette: dict | None = None,
) -> Path:
    """Draw one card PNG. Raises RuntimeError if ffmpeg fails (fail closed)."""
    pal = {**PALETTE, **(palette or {})}
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    title_lines = _wrap(title)
    if not title_lines:
        raise ValueError("card title is empty")

    with tempfile.TemporaryDirectory(prefix="card_") as td:
        tmp = Path(td)
        files = {}
        for name, value in (
            ("number", str(number).strip()),
            ("footer", str(footer)),
            ("title", "\n".join(title_lines)),
        ):
            f = tmp / f"{name}.txt"
            f.write_text(value, encoding="utf-8")
            files[name] = f

        filters = [
            f"drawbox=x=88:y=250:w=6:h=150:color={pal['accent']}@1.0:t=fill",
            _drawtext(files["number"], 120, 240, 30, pal["accent"], FONT_BOLD),
            _drawtext(files["title"], 120, 300, 54, pal["bone"], FONT_BOLD,
                      ":line_spacing=12"),
            f"drawbox=x=88:y=600:w=1104:h=2:color={pal['charcoal']}@1.0:t=fill",
            _drawtext(files["footer"], 88, 620, 20, pal["bone"], FONT_REGULAR),
        ]
        cmd = [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi",
            "-i", f"color=c={pal['bg']}:s={width}x{height}:d=1",
            "-vf", ",".join(filters),
            "-frames:v", "1",
            "-pix_fmt", "rgb24",
            str(out),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            raise RuntimeError(f"card render failed: {res.stderr.strip()[-400:]}")
    return out


def make_section_cards(
    sections: list[dict],
    out_dir: str | Path,
    *,
    footer: str | None = None,
    width: int = 1280,
    height: int = 720,
    palette: dict | None = None,
) -> list[Path]:
    """One card per script section, in order. Returns the PNG paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, section in enumerate(sections, 1):
        title = str(section.get("title") or f"Part {i}")
        p = out / f"card_{i:02d}.png"
        make_card(
            p, number=f"{i:02d}", title=title,
            footer=footer or "OPENMONTAGE · SPECULATIVE EVOLUTION · AI ILLUSTRATIONS LABELLED",
            width=width, height=height, palette=palette,
        )
        paths.append(p)
    return paths
