"""SRT cue boundaries used by both caption rendering paths."""

from pathlib import Path

import pytest

from tools.video.remotion_caption_burn import RemotionCaptionBurn


@pytest.mark.parametrize("separator", ["\n\n", "\n \n", "\n\t\n", "\n \t \n", "\n \n\t\n\n"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_whitespace_only_lines_separate_srt_cues(
    tmp_path: Path, separator: str, newline: str
) -> None:
    content = (
        "1\n00:00:00,000 --> 00:00:01,000\nHello"
        f"{separator}"
        "2\n00:00:02,000 --> 00:00:03,000\nWorld"
    )
    srt = tmp_path / "captions.srt"
    srt.write_bytes(content.replace("\n", newline).encode("utf-8"))

    assert RemotionCaptionBurn()._srt_to_word_captions(str(srt)) == [
        {"word": "Hello", "startMs": 0, "endMs": 1000},
        {"word": "World", "startMs": 2000, "endMs": 3000},
    ]


def test_multiline_cues_keep_word_timing_and_corrections(tmp_path: Path) -> None:
    srt = tmp_path / "captions.srt"
    srt.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nHello,\nworld!\n \n"
        "2\n00:00:04,000 --> 00:00:05,000\nGoodbye.\n",
        encoding="utf-8",
    )

    assert RemotionCaptionBurn()._srt_to_word_captions(
        str(srt), corrections={"HELLO": "Hi"}
    ) == [
        {"word": "Hi", "startMs": 1000, "endMs": 2000},
        {"word": "world!", "startMs": 2000, "endMs": 3000},
        {"word": "Goodbye.", "startMs": 4000, "endMs": 5000},
    ]


def test_empty_srt_has_no_captions(tmp_path: Path) -> None:
    srt = tmp_path / "captions.srt"
    srt.write_text(" \n\t\n", encoding="utf-8")

    assert RemotionCaptionBurn()._srt_to_word_captions(str(srt)) == []
