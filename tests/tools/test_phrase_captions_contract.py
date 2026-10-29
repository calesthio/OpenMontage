import json
from pathlib import Path

import jsonschema
import pytest

from tools.video.video_compose import VideoCompose

REPO = Path(__file__).resolve().parents[2]

QWEN3_SEGMENTS = {
    "segments": [
        {
            "id": "s1",
            "text": "금리가 오르면 대출이 무거워집니다.",
            "start": 0.4,
            "end": 2.6,
            "words": [
                {"word": "금리가", "start": 0.4, "end": 0.9},
                {"word": "오르면", "start": 1.0, "end": 1.5},
                {"word": "대출이", "start": 1.7, "end": 2.1},
                {"word": "무거워집니다.", "start": 2.1, "end": 2.6},
            ],
        },
        {
            "id": "s2",
            "text": "그런데 왜일까요",
            "start": 3.0,
            "end": 3.9,
            "words": [
                {"word": "그런데", "start": 3.0, "end": 3.4},
                {"word": " ", "start": 3.4, "end": 3.4},
                {"word": "왜일까요", "start": 3.5, "end": 3.9},
            ],
        },
    ]
}


def test_qwen3_segments_become_global_ms_captions_with_segment_breaks() -> None:
    captions = VideoCompose._caption_words_from_timing(QWEN3_SEGMENTS)

    assert [c["word"] for c in captions] == ["금리가", "오르면", "대출이", "무거워집니다.", "그런데", "왜일까요"]
    assert captions[0] == {"word": "금리가", "startMs": 400, "endMs": 900}
    assert [i for i, c in enumerate(captions) if c.get("pageBreakAfter")] == [3, 5]


def test_flat_word_timestamps_and_timestamps_list_are_accepted() -> None:
    flat = {"word_timestamps": [{"word": "하나", "start": 0.0, "end": 0.3}, {"word": "둘", "start": 0.5, "end": 0.8}]}
    assert [c["startMs"] for c in VideoCompose._caption_words_from_timing(flat)] == [0, 500]
    assert len(VideoCompose._caption_words_from_timing(QWEN3_SEGMENTS["segments"])) == 6


def test_karaoke_style_loads_word_timings_from_subtitles_source(tmp_path: Path) -> None:
    source = tmp_path / "om_segments.json"
    source.write_text(json.dumps(QWEN3_SEGMENTS, ensure_ascii=False), encoding="utf-8")
    props = {"cuts": [], "subtitles": {"enabled": True, "style": "karaoke", "source": str(source)}}

    assert VideoCompose._attach_phrase_captions(props, "Explainer") is None
    assert len(props["captions"]) == 6


def test_karaoke_style_builds_cinematic_caption_config(tmp_path: Path) -> None:
    source = tmp_path / "om_segments.json"
    source.write_text(json.dumps(QWEN3_SEGMENTS, ensure_ascii=False), encoding="utf-8")
    props = {
        "subtitles": {"style": "Karaoke", "source": str(source), "dim_color": "#777777", "hold_seconds": 0.4}
    }

    assert VideoCompose._attach_phrase_captions(props, "CinematicRenderer") is None
    assert props["captions"]["style"] == "karaoke"
    assert props["captions"]["dimColor"] == "#777777"
    assert props["captions"]["holdSeconds"] == 0.4
    assert len(props["captions"]["words"]) == 6


def test_existing_captions_are_kept_and_other_styles_are_untouched() -> None:
    words = [{"word": "a", "startMs": 0, "endMs": 100}]
    props = {"captions": words, "subtitles": {"style": "karaoke"}}
    assert VideoCompose._attach_phrase_captions(props, "Explainer") is None
    assert props["captions"] is words

    legacy = {"subtitles": {"style": "word-by-word", "source": "captions.srt"}}
    assert VideoCompose._attach_phrase_captions(legacy, "Explainer") is None
    assert "captions" not in legacy


def test_karaoke_without_word_timings_fails_loudly() -> None:
    props = {"subtitles": {"enabled": True, "style": "karaoke", "source": "captions.srt"}}
    error = VideoCompose._attach_phrase_captions(props, "Explainer")
    assert error and "word timings" in error


def test_schema_accepts_phrase_caption_fields() -> None:
    schema = json.loads((REPO / "schemas/artifacts/edit_decisions.schema.json").read_text(encoding="utf-8"))
    doc = {
        "version": "1.0",
        "render_runtime": "remotion",
        "cuts": [{"id": "c1", "source": "", "in_seconds": 0, "out_seconds": 4}],
        "subtitles": {
            "enabled": True,
            "style": "karaoke",
            "source": "om_segments.json",
            "dim_color": "#8592A6",
            "max_chars_per_cue": 26,
            "hold_seconds": 0.6,
        },
    }
    jsonschema.validate(doc, schema)
    doc["subtitles"]["hold_seconds"] = -1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)
