"""Regression tests: CJK captions must not be joined, split, or transcribed by
Latin-script assumptions.

Three separate defects made Chinese captions unusable end to end:

1. `_build_cues` joined every token with a space, so ``人工智能`` rendered as
   ``人 工 智 能``. The Remotion `CaptionOverlay` exposes `wordSeparator` and
   documents `""` for CJK, but nothing in the Python layer ever set it.
2. Cue splitting counted tokens against `max_words_per_cue`. CJK recognisers
   emit per-character tokens with no word boundaries, so a length cut lands
   inside a word (``批`` | ``改作业``, ``接`` | ``过去``), and the default of 8
   tokens is far too small for a script where one token is one character.
3. Subtitles were built from speech-to-text of the narration audio rather than
   from the narration script itself, so ASR homophone errors were baked into
   the captions (``作用`` -> ``做用``, ``是把`` -> ``时把``) and all punctuation
   was lost -- and punctuation is the only clause signal available when the
   recogniser emits no word boundaries.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.subtitle.subtitle_gen import (  # noqa: E402
    SubtitleGen,
    _break_weight,
    _enforce_min_cue_duration,
    _join_tokens,
    align_script_to_words,
)
from tools.video.video_compose import VideoCompose  # noqa: E402

SCRIPT = (
    "人工智能不会取代老师。它真正的作用，是把批改作业、统计成绩、"
    "查找资料这些重复劳动接过去。这样一来，老师才能把宝贵的时间，"
    "还给每一个需要被看见的学生。"
)

# What faster-whisper produced for this narration *without* an initial prompt:
# homophone errors, no punctuation, one token per character.
DIRTY_ASR = (
    "人工智能不会取代老师他真正的做用时把批改作业统计成绩查找资料"
    "这些重复劳动接过去这样一来老师才能把宝贵的时间还给每一个需要被看见的学生"
)


def _one_char_segments(text: str, duration: float = 13.0):
    """Build the per-character word timings a CJK recogniser emits."""
    span = duration / len(text)
    words = [
        {"word": ch, "start": round(i * span, 3), "end": round((i + 1) * span, 3)}
        for i, ch in enumerate(text)
    ]
    return [{"text": text, "start": 0.0, "end": duration, "words": words}]


# --------------------------------------------------------------------------
# 1. joining
# --------------------------------------------------------------------------


def test_cjk_tokens_join_without_spaces():
    assert _join_tokens(["人", "工", "智", "能"]) == "人工智能"
    assert _join_tokens(["我们", "的", "工作", "方式。"]) == "我们的工作方式。"


def test_latin_tokens_keep_their_spaces():
    # Regression guard: the CJK fix must not collapse space-delimited scripts.
    assert _join_tokens(["Hello", "world"]) == "Hello world"
    assert _join_tokens(["one", "two", "three"]) == "one two three"


def test_mixed_script_does_not_pad_between_latin_and_cjk():
    assert _join_tokens(["AI", "正在", "改变"]) == "AI正在改变"


def test_join_ignores_markup_when_looking_for_cjk():
    # The karaoke SRT/VTT renderers wrap the active token in <b>…</b>.
    assert _join_tokens(["<b>人</b>", "工"]) == "<b>人</b>工"
    assert _join_tokens(["<b>Hello</b>", "world"]) == "<b>Hello</b> world"


def test_join_skips_empty_parts():
    assert _join_tokens(["人", "", "工"]) == "人工"
    assert _join_tokens(["", "Hello"]) == "Hello"


def test_join_keeps_hyphenated_latin_tokens_intact():
    # Chinese technical writing mixes in hyphenated Latin tokens ("GPT-4",
    # "skip-tts", "Wi-Fi"); a space around the hyphen would tear the word apart.
    assert _join_tokens(["skip", "-", "tts"]) == "skip-tts"
    assert _join_tokens(["Wi", "-", "Fi"]) == "Wi-Fi"
    assert _join_tokens(["GPT", "-", "4", "正在", "改变"]) == "GPT-4正在改变"
    assert _join_tokens(["l", "'", "heure"]) == "l'heure"


def test_join_still_pads_after_sentence_punctuation():
    # The intra-word suppression must not swallow ordinary sentence spacing.
    assert _join_tokens(["Hello.", "World"]) == "Hello. World"


# --------------------------------------------------------------------------
# 2. clause detection
# --------------------------------------------------------------------------


def test_break_weight_classifies_punctuation():
    assert _break_weight("老师。") == 2
    assert _break_weight("作用，") == 1
    assert _break_weight("作业、") == 1
    assert _break_weight("老师") == 0
    assert _break_weight("<b>方式。</b>") == 2


# --------------------------------------------------------------------------
# 3. script alignment
# --------------------------------------------------------------------------


def test_alignment_restores_script_characters_over_asr_errors():
    words = align_script_to_words(SCRIPT, _one_char_segments(DIRTY_ASR))
    rebuilt = "".join(w["word"] for w in words)

    assert "做用" not in rebuilt, "ASR homophone must not survive alignment"
    assert "时把" not in rebuilt
    assert rebuilt == SCRIPT, "aligned tokens must reproduce the script verbatim"


def test_alignment_restores_punctuation_that_asr_dropped():
    words = align_script_to_words(SCRIPT, _one_char_segments(DIRTY_ASR))
    rebuilt = "".join(w["word"] for w in words)

    for mark in "。，、":
        assert mark in rebuilt


def test_alignment_timings_are_monotonic_and_bounded():
    segments = _one_char_segments(DIRTY_ASR, duration=13.0)
    words = align_script_to_words(SCRIPT, segments)

    assert words[0]["start"] >= 0.0
    assert words[-1]["end"] <= 13.0
    previous_end = 0.0
    for w in words:
        assert w["start"] <= w["end"], f"{w['word']!r} has inverted timings"
        assert w["start"] >= previous_end - 0.05, f"{w['word']!r} goes backwards"
        previous_end = w["end"]


def test_alignment_without_word_timings_returns_nothing():
    # Segment-level transcripts have no words array; callers must fall back to
    # the legacy path rather than emit an empty caption track.
    assert align_script_to_words(SCRIPT, [{"text": SCRIPT, "start": 0, "end": 5}]) == []
    assert align_script_to_words("", _one_char_segments(DIRTY_ASR)) == []


def test_alignment_tolerates_a_script_longer_than_what_was_heard():
    # A dropped phrase in the transcript must not shift the remaining text.
    clipped = DIRTY_ASR.replace("统计成绩查找资料", "")
    words = align_script_to_words(SCRIPT, _one_char_segments(clipped))
    assert "".join(w["word"] for w in words) == SCRIPT


# --------------------------------------------------------------------------
# 4. end-to-end cue building
# --------------------------------------------------------------------------


def _cue_texts(segments, **inputs):
    tool = SubtitleGen()
    max_chars = inputs.pop("max_chars_per_line", 26)
    words = align_script_to_words(SCRIPT, segments, tokenize=inputs.pop("tokenize", True))
    return [c["text"] for c in tool._build_cues([{"words": words}], 99, max_chars)]


def test_cjk_cues_never_contain_spaces():
    for cue in _cue_texts(_one_char_segments(DIRTY_ASR)):
        assert " " not in cue, f"cue leaked a Latin space: {cue!r}"


def test_cjk_cues_break_on_punctuation():
    cues = _cue_texts(_one_char_segments(DIRTY_ASR))

    assert cues[0] == "人工智能不会取代老师。"
    assert cues[-1] == "还给每一个需要被看见的学生。"


def test_alignment_prevents_mid_word_cuts():
    # A long unpunctuated clause is where a length-based cut used to slice a
    # word in half. The default run is only asserted not to break inside a
    # segment produced by the aligner, which is the invariant that matters.
    clause = "统计成绩查找资料这些重复劳动接过去"
    segments = _one_char_segments(clause, duration=6.0)
    tool = SubtitleGen()

    for max_chars in (9, 12):
        words = align_script_to_words(clause, segments, tokenize=True)
        cues = [c["text"] for c in tool._build_cues([{"words": words}], 99, max_chars)]
        rejoined = "".join(cues)
        assert rejoined == clause, f"cues lost or reordered text at {max_chars}"
        # Every cue boundary must fall on a token boundary, never inside one.
        for cue in cues[:-1]:
            assert cue in [w["word"] for w in words] or any(
                cue == "".join(w["word"] for w in words[: i + 1])
                for i in range(len(words))
            ), f"cue {cue!r} ended mid-token"


def test_latin_transcript_path_is_unchanged():
    # A space-delimited transcript with no script_text must behave exactly as
    # before: tokens keep their spaces and no alignment is attempted.
    tool = SubtitleGen()
    segments = [{
        "text": "hello world again",
        "start": 0.0,
        "end": 3.0,
        "words": [
            {"word": "hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 1.0, "end": 2.0},
            {"word": "again", "start": 2.0, "end": 3.0},
        ],
    }]
    cues = [c["text"] for c in tool._build_cues(segments, 8, 42)]
    assert " ".join(cues) == "hello world again"


# --------------------------------------------------------------------------
# 5. minimum display time
# --------------------------------------------------------------------------


def test_short_cue_is_stretched_to_the_documented_minimum():
    # subtitle-sync.md specifies a 0.5s floor; ASR timing can hand a one-word
    # interjection a fraction of that, which is unreadable.
    cues = [
        {"index": 1, "start": 0.0, "end": 1.0, "text": "甲"},
        {"index": 2, "start": 1.0, "end": 1.24, "text": "不会。"},
        {"index": 3, "start": 3.0, "end": 4.0, "text": "丙"},
    ]
    out = _enforce_min_cue_duration(cues, 0.5)
    assert out[1]["end"] - out[1]["start"] == 0.5


def test_minimum_duration_never_overlaps_the_next_cue():
    cues = [
        {"index": 1, "start": 0.0, "end": 0.1, "text": "甲"},
        {"index": 2, "start": 0.2, "end": 1.0, "text": "乙"},
    ]
    out = _enforce_min_cue_duration(cues, 0.5)
    # Only 0.2s of room existed, so the cue borrows that and no more.
    assert out[0]["end"] <= 0.2
    assert out[0]["end"] <= out[1]["start"]


def test_minimum_duration_leaves_long_cues_alone():
    cues = [{"index": 1, "start": 0.0, "end": 2.0, "text": "甲"}]
    assert _enforce_min_cue_duration(cues, 0.5)[0]["end"] == 2.0
    # Disabled when the caller passes 0.
    assert _enforce_min_cue_duration(
        [{"index": 1, "start": 0.0, "end": 0.1, "text": "甲"}], 0.0
    )[0]["end"] == 0.1


# --------------------------------------------------------------------------
# 6. renderer defaults are chosen from the script, not left to the caller
# --------------------------------------------------------------------------


def test_renderer_defaults_are_set_for_cjk_captions():
    # compose-director.md never mentions these props, so an agent following the
    # documented path would otherwise render 人 工 智 能.
    props = {"captions": [{"word": w} for w in "人工智能不会取代老师"]}
    VideoCompose._apply_caption_script_defaults(VideoCompose, props)
    assert props["captionWordSeparator"] == ""
    assert props["captionWordsPerPage"] == 14


def test_renderer_defaults_leave_latin_captions_alone():
    props = {"captions": [{"word": w} for w in ["hello", "world", "again"]]}
    VideoCompose._apply_caption_script_defaults(VideoCompose, props)
    assert "captionWordSeparator" not in props
    assert "captionWordsPerPage" not in props


def test_renderer_defaults_respect_an_explicit_caller_choice():
    props = {
        "captions": [{"word": "人"}, {"word": "工"}],
        "captionWordSeparator": " ",
        "captionWordsPerPage": 6,
    }
    VideoCompose._apply_caption_script_defaults(VideoCompose, props)
    assert props["captionWordSeparator"] == " "
    assert props["captionWordsPerPage"] == 6


def test_renderer_defaults_no_op_without_captions():
    props = {"cuts": []}
    VideoCompose._apply_caption_script_defaults(VideoCompose, props)
    assert props == {"cuts": []}
