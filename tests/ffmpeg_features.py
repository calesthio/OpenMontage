"""Skip conditions for tests that need a full FFmpeg build.

The stock Homebrew `ffmpeg` (and other minimal builds) has no `drawtext`, no
`subtitles` (libass) and no `libvorbis`. Tests that render with those features
used to FAIL there, on the base branch as much as on any change, so every local
run ended "10 failed" and a real regression among them was easy to miss.

They now skip with the reason — unless ``OPENMONTAGE_REQUIRE_FULL_FFMPEG=1`` is
set (CI sets it), in which case a build that lacks a feature fails the test
instead of hiding it.
"""

from __future__ import annotations

import os

import pytest

from tools.ffmpeg_capabilities import has_encoder, has_filter

STRICT = os.environ.get("OPENMONTAGE_REQUIRE_FULL_FFMPEG", "").strip() == "1"


def _needs(available: bool, what: str) -> pytest.MarkDecorator:
    return pytest.mark.skipif(
        not available and not STRICT,
        reason=f"this ffmpeg build has no {what} (set OPENMONTAGE_REQUIRE_FULL_FFMPEG=1 to fail instead)",
    )


requires_drawtext = _needs(has_filter("drawtext"), "drawtext filter (freetype)")
requires_subtitles_filter = _needs(has_filter("subtitles"), "subtitles filter (libass)")
requires_libvorbis = _needs(has_encoder("libvorbis"), "libvorbis encoder")
