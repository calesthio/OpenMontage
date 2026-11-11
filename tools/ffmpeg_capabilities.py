"""What the installed FFmpeg build can actually do.

`cmd:ffmpeg` on PATH says nothing about how it was built. A minimal build (the
default Homebrew formula since 2025, many container images) has no `drawtext`
filter (needs freetype), no `subtitles`/`ass` filter (needs libass) and no
`libvorbis` encoder. Tools that need one of those reported AVAILABLE and then
failed at render time with "Filter not found" — the silent-availability bug the
preflight contract exists to prevent.

A tool states the need as a dependency — ``"ffmpeg_filter:drawtext"`` or
``"ffmpeg_encoder:libvorbis"`` — and `BaseTool.check_dependencies` asks here.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from functools import lru_cache

_NAME = re.compile(r"^[a-z0-9_]+$")
_FLAGS = re.compile(r"^[A-Z.|]+$")

# (kind, name, what stops working without it) — surfaced at preflight.
NOTABLE_FEATURES: tuple[tuple[str, str, str], ...] = (
    ("filter", "drawtext",
     "FFmpeg-drawn text fails (showcase_card titles and watermarks)"),
    ("filter", "subtitles",
     "FFmpeg subtitle burn-in fails (video_compose native captions) -- burn "
     "captions with Remotion (remotion_caption_burn) instead"),
    ("encoder", "libvorbis",
     "Ogg Vorbis audio output fails -- use libopus or AAC"),
)

FULL_BUILD_HINT = (
    "Install an FFmpeg build with freetype, libass and libvorbis "
    "(macOS: `brew install ffmpeg-full`; Debian/Ubuntu: the distro `ffmpeg` "
    "package already has them)."
)


@lru_cache(maxsize=4)
def _listing(kind: str) -> frozenset[str]:
    """Names `ffmpeg -filters` / `-encoders` prints. Empty when ffmpeg is absent."""
    exe = shutil.which("ffmpeg")
    if not exe:
        return frozenset()
    try:
        out = subprocess.run(
            [exe, "-hide_banner", f"-{kind}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    names = set()
    for line in out.splitlines():
        parts = line.split()
        # " T.. drawtext   V->V  Draw text"  /  " A....D libvorbis  libvorbis"
        if len(parts) >= 2 and _FLAGS.match(parts[0]) and _NAME.match(parts[1]):
            names.add(parts[1])
    return frozenset(names)


def has_filter(name: str) -> bool:
    return name in _listing("filters")


def has_encoder(name: str) -> bool:
    return name in _listing("encoders")


def has_feature(kind: str, name: str) -> bool:
    return has_filter(name) if kind == "filter" else has_encoder(name)


def capability_warnings() -> list[str]:
    """One line per notable feature this FFmpeg build lacks (none if no ffmpeg:
    a missing binary is reported by the tools that depend on it)."""
    if not shutil.which("ffmpeg") or not _listing("filters"):
        return []
    missing = [
        f"ffmpeg: this build has no `{name}` {kind} -- {consequence}"
        for kind, name, consequence in NOTABLE_FEATURES
        if not has_feature(kind, name)
    ]
    if missing:
        missing.append(f"ffmpeg: {FULL_BUILD_HINT}")
    return missing
