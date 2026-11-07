"""Doubao timing compatibility and Chinese/Latin caption spacing."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.subtitle.subtitle_gen import SubtitleGen


@pytest.mark.parametrize("fmt", ["srt", "vtt", "json"])
def test_doubao_words_preserve_seconds_and_input(tmp_path, fmt):
    segments = [{"startTime": 0.045, "endTime": 1.615, "text": "中国DeepSeek模型",
                 "words": [
                     {"word": "中", "startTime": 0.045, "endTime": 0.135},
                     {"word": "国", "startTime": 0.135, "endTime": 0.265},
                     {"word": "DeepSeek", "startTime": 0.265, "endTime": 1.0},
                     {"word": "模型", "startTime": 1.0, "endTime": 1.615}]}]
    original = copy.deepcopy(segments)
    output = tmp_path / f"captions.{fmt}"
    result = SubtitleGen().execute({"segments": segments, "format": fmt,
                                    "output_path": str(output)})
    assert result.success
    assert segments == original
    content = output.read_text()
    if fmt == "json":
        cue = json.loads(content)["cues"][0]
        assert (cue["start"], cue["end"], cue["text"]) == (0.045, 1.615, "中国DeepSeek模型")
    else:
        assert "中国DeepSeek模型" in content
        assert ("00:00:00,045 --> 00:00:01,615" if fmt == "srt"
                else "00:00:00.045 --> 00:00:01.615") in content


def test_canonical_english_output_unchanged(tmp_path):
    output = tmp_path / "english.srt"
    result = SubtitleGen().execute({"segments": [{"words": [
        {"word": "Hello", "start": 0, "end": 0.5},
        {"word": "world.", "start": 0.5, "end": 1}]}], "output_path": str(output)})
    assert result.success
    assert output.read_text() == "1\n00:00:00,000 --> 00:00:01,000\nHello world.\n"


def test_sentence_only_doubao_input(tmp_path):
    output = tmp_path / "sentence.srt"
    result = SubtitleGen().execute({"segments": [{"text": "你好。", "startTime": 1.2,
                                                  "endTime": 2.3}], "output_path": str(output)})
    assert result.success
    assert "00:00:01,200 --> 00:00:02,300\n你好。" in output.read_text()


@pytest.mark.parametrize("timing", [{}, {"start": 0}, {"startTime": 0},
                                   {"start": -1, "end": 1}, {"start": 2, "end": 1},
                                   {"start": float("nan"), "end": 1},
                                   {"start": 0, "end": "1"}])
def test_invalid_timing_fails_without_writing(tmp_path, timing):
    output = tmp_path / "invalid.srt"
    result = SubtitleGen().execute({"segments": [{"words": [{"word": "词", **timing}]}],
                                    "output_path": str(output)})
    assert not result.success
    assert "timestamp" in result.error.lower()
    assert not output.exists()


def test_canonical_timing_takes_precedence():
    normalized = SubtitleGen._normalize_timestamps([{"words": [
        {"word": "x", "start": 0, "end": 1, "startTime": 5, "endTime": 6}]}])
    assert normalized[0]["words"][0]["start"] == 0
    assert normalized[0]["words"][0]["end"] == 1


@pytest.mark.parametrize("fmt", ["srt", "vtt"])
def test_karaoke_spacing_and_word_timing(tmp_path, fmt):
    output = tmp_path / f"karaoke.{fmt}"
    result = SubtitleGen().execute({"segments": [{"words": [
        {"word": "中", "startTime": 0, "endTime": 0.5},
        {"word": "国", "startTime": 0.5, "endTime": 1}]}], "format": fmt,
        "highlight_style": "karaoke", "output_path": str(output)})
    assert result.success
    assert "<b>中</b>国" in output.read_text()
    assert "中<b>国</b>" in output.read_text()


def test_mixed_text_preserves_english_word_spaces():
    assert SubtitleGen._join_tokens(["中国", "open", "source", "模型", "R", "一。"]) == "中国open source模型R一。"


def test_chinese_cue_length_uses_actual_text(tmp_path):
    output = tmp_path / "split.json"
    words = [{"word": ch, "startTime": i, "endTime": i + 1}
             for i, ch in enumerate("中国团队发布模型")]
    result = SubtitleGen().execute({"segments": [{"words": words}], "format": "json",
        "max_chars_per_line": 4, "max_words_per_cue": 8, "output_path": str(output)})
    assert result.success
    cues = json.loads(output.read_text())["cues"]
    assert [c["text"] for c in cues] == ["中国团队", "发布模型"]
    assert [(c["start"], c["end"]) for c in cues] == [(0, 4), (4, 8)]
