"""Correction values are literal text, not regular-expression replacements."""

import pytest

from tools.subtitle.subtitle_gen import SubtitleGen


@pytest.mark.parametrize("replacement", [r"C:\Users\speaker", r"\1", r"line\ntext"])
def test_segment_corrections_preserve_backslashes(tmp_path, replacement):
    segments = [{"text": "Use folder.", "start": 0, "end": 1}]
    output = tmp_path / "captions.srt"
    result = SubtitleGen().execute({
        "segments": segments,
        "corrections": {"folder": replacement},
        "output_path": str(output),
    })
    assert result.success, result.error
    assert f"Use {replacement}." in output.read_text()
    assert segments[0]["text"] == "Use folder."


def test_segment_and_word_corrections_agree():
    replacement = r"C:\Users\speaker"
    segments = [
        {"text": "FOLDER", "start": 0, "end": 1},
        {"words": [{"word": "FOLDER", "start": 1, "end": 2}]},
    ]
    corrected = SubtitleGen._apply_corrections(segments, {"folder": replacement})
    assert corrected[0]["text"] == corrected[1]["words"][0]["word"] == replacement
