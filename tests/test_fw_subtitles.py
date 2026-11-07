"""Subtitle cue building: <=2 lines, <=6 s per cue, breaks on pauses."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.fw_subtitles import (  # noqa: E402
    cues_from_words,
    hmsms,
    srt_text,
    wrap_two_lines,
)


def _w(word, start, end):
    return {"word": word, "start": start, "end": end}


def test_hmsms_formats_like_srt():
    assert hmsms(0.0) == "00:00:00,000"
    assert hmsms(3661.5) == "01:01:01,500"


def test_short_pauses_do_not_split_a_cue():
    words = [_w("beneath", 0.0, 0.4), _w("the", 0.45, 0.6),
             _w("ice,", 0.65, 1.1)]
    cues = cues_from_words(words)
    assert len(cues) == 1
    assert cues[0][2] == "beneath the ice,"


def test_long_pause_splits_and_punctuation_splits():
    words = [_w("First.", 0.0, 0.4), _w("Second", 1.6, 2.0)]
    cues = cues_from_words(words)
    assert [c[2] for c in cues] == ["First.", "Second"]


def test_no_cue_exceeds_the_duration_cap():
    words = [_w("word", i * 0.5, i * 0.5 + 0.45) for i in range(40)]
    cues = cues_from_words(words)
    assert len(cues) > 1
    assert all(end - start <= 6.0 + 0.5 for start, end, _ in cues)
    assert all(len(text) <= 84 for _s, _e, text in cues)


def test_wrap_two_lines_stays_within_two_lines():
    text = "a rather long subtitle line that definitely needs wrapping"
    wrapped = wrap_two_lines(text)
    assert len(wrapped.splitlines()) == 2
    assert all(len(line) <= 42 for line in wrapped.splitlines())


def test_srt_text_indexes_cues_from_one():
    cues = [(0.0, 1.0, "one"), (1.2, 2.0, "two")]
    out = srt_text(cues)
    assert out.startswith("1\n00:00:00,000 --> 00:00:01,000\none")
    assert "\n\n2\n00:00:01,200 --> 00:00:02,000\ntwo" in out


def test_decode_16k_mono_uses_ffmpeg_and_returns_float32(tmp_path):
    import subprocess

    import numpy as np

    from scripts.fw_subtitles import decode_16k_mono

    wav = tmp_path / "a.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=0.5:sample_rate=44100",
                    "-ac", "2", str(wav)], check=True)
    samples = decode_16k_mono(str(wav))
    assert samples.dtype == np.float32
    assert samples.ndim == 1
    assert 0.4 * 16000 <= samples.size <= 0.6 * 16000
    assert float(np.abs(samples).max()) > 0.01
