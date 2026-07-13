"""Regression tests: SRT/VTT timestamp formatting must not overflow milliseconds.

`_ts_srt` / `_ts_vtt` computed the seconds and millisecond fields independently:
`ms = int(round((seconds % 1) * 1000))`. When the fractional part is >= 0.9995,
that rounds to 1000, emitting a malformed 4-digit `…,1000` with no carry into
the seconds (and, at boundaries, minutes/hours) field — e.g. 0.9999s ->
`00:00:00,1000` instead of `00:00:01,000`. Such timestamps are rejected by
strict SRT/VTT parsers (ffmpeg subtitles filter, VLC, browser WebVTT).
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.subtitle.subtitle_gen import SubtitleGen  # noqa: E402

_SRT_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}$")
_VTT_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}$")


def test_millisecond_carry_does_not_overflow():
    # Every fractional part >= 0.9995 must carry into the next second, never
    # emit a 4-digit millisecond field.
    assert SubtitleGen._ts_srt(0.9999) == "00:00:01,000"
    assert SubtitleGen._ts_vtt(0.9999) == "00:00:01.000"
    assert SubtitleGen._ts_srt(1.9996) == "00:00:02,000"


def test_carry_propagates_across_minute_and_hour_boundaries():
    assert SubtitleGen._ts_srt(59.9999) == "00:01:00,000"
    assert SubtitleGen._ts_srt(3599.9999) == "01:00:00,000"
    assert SubtitleGen._ts_srt(7261.9999) == "02:01:02,000"


def test_normal_values_unchanged():
    assert SubtitleGen._ts_srt(0.0) == "00:00:00,000"
    assert SubtitleGen._ts_srt(1.5) == "00:00:01,500"
    assert SubtitleGen._ts_srt(0.4994) == "00:00:00,499"
    assert SubtitleGen._ts_vtt(83.25) == "00:01:23.250"


def test_all_outputs_are_well_formed():
    # Sweep values that land on and around the dangerous boundary.
    for t in (0.0, 0.4995, 0.9995, 0.9999, 1.0, 59.9995, 3599.9999, 12345.9999):
        assert _SRT_RE.match(SubtitleGen._ts_srt(t)), SubtitleGen._ts_srt(t)
        assert _VTT_RE.match(SubtitleGen._ts_vtt(t)), SubtitleGen._ts_vtt(t)
