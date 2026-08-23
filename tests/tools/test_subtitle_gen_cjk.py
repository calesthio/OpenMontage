"""Regression tests: CJK captions must not get a space between every token.

The transcriber emits one token per word, and `subtitle_gen` joined them with
`" "`. That is right for space-delimited languages and wrong for Chinese,
Japanese and Korean, which are written without inter-word spaces — a
Traditional Chinese cue came out as "阿公 的 助聽器 已經 戴 了 十五 年"
instead of "阿公的助聽器已經戴了十五年".

`CaptionOverlay` gained a `wordSeparator` prop for the Remotion side
(PR #507), but the SRT/VTT path that ffmpeg burns in was untouched.

The space survives at a script boundary, so mixed text keeps reading
correctly, and output for space-delimited languages is byte-identical.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.subtitle.subtitle_gen import (  # noqa: E402
    SubtitleGen,
    join_caption_tokens,
)


def _cue_texts(tokens: list[str], **inputs) -> list[str]:
    words = [
        {"word": w, "start": i * 0.4, "end": (i + 1) * 0.4}
        for i, w in enumerate(tokens)
    ]
    segments = [
        {
            "start": 0.0,
            "end": len(tokens) * 0.4,
            "text": "".join(tokens),
            "words": words,
        }
    ]
    cues = SubtitleGen()._build_cues(segments, inputs.get("max_words", 8), 42)
    return [c["text"] for c in cues]


# --- join_caption_tokens ----------------------------------------------------


def test_two_cjk_tokens_are_glued():
    assert join_caption_tokens(["阿公", "的", "助聽器"]) == "阿公的助聽器"


def test_space_survives_at_a_script_boundary():
    assert join_caption_tokens(["使用", "OpenMontage", "製作"]) == "使用 OpenMontage 製作"


def test_latin_tokens_keep_their_spaces():
    assert join_caption_tokens(["the", "quick", "fox"]) == "the quick fox"


def test_fullwidth_punctuation_stays_glued():
    # A stranded "。" at the start of a line is a Chinese typography error.
    assert join_caption_tokens(["難熬", "。"]) == "難熬。"
    assert join_caption_tokens(["真的", "嗎", "？"]) == "真的嗎？"


def test_kana_and_hangul_are_treated_as_cjk():
    assert join_caption_tokens(["日本語", "の", "字幕"]) == "日本語の字幕"
    assert join_caption_tokens(["한국어", "자막"]) == "한국어자막"


def test_extension_b_ideographs_are_treated_as_cjk():
    # U+20000 onwards carries rarer Traditional forms; a range check that
    # stopped at U+9FFF would put a space beside them.
    rare = "\U00020000"
    assert join_caption_tokens([rare, "字"]) == f"{rare}字"


def test_rendered_forms_do_not_decide_spacing():
    # Karaoke markup must not make a CJK neighbour look like Latin.
    assert (
        join_caption_tokens(["阿公", "的"], ["<b>阿公</b>", "的"]) == "<b>阿公</b>的"
    )


def test_empty_input_is_empty():
    assert join_caption_tokens([]) == ""


# --- end to end through the tool -------------------------------------------


def test_chinese_cues_have_no_inter_token_spaces():
    texts = _cue_texts("阿公 的 助聽器 已經 戴 了 十五 年".split())
    assert texts == ["阿公的助聽器已經戴了十五年"]


def test_english_cues_are_unchanged():
    texts = _cue_texts("the quick brown fox jumps".split())
    assert texts == ["the quick brown fox jumps"]


def test_mixed_script_cue_keeps_the_boundary_space():
    texts = _cue_texts("使用 OpenMontage 製作 的 影片".split())
    assert texts == ["使用 OpenMontage 製作的影片"]


def test_karaoke_srt_does_not_reintroduce_spaces():
    words = [
        {"word": w, "start": i * 0.4, "end": (i + 1) * 0.4}
        for i, w in enumerate(["阿公", "的", "助聽器"])
    ]
    cues = [{"index": 1, "start": 0.0, "end": 1.2, "text": "阿公的助聽器", "words": words}]

    srt = SubtitleGen()._render_srt(cues, "karaoke")

    assert "<b>阿公</b>的助聽器" in srt
    assert "阿公 的" not in srt


def test_corrections_rebuild_segment_text_without_spaces():
    segments = [
        {
            "start": 0.0,
            "end": 1.2,
            "text": "阿公的助聽氣",
            "words": [
                {"word": "阿公", "start": 0.0, "end": 0.4},
                {"word": "的", "start": 0.4, "end": 0.8},
                {"word": "助聽氣", "start": 0.8, "end": 1.2},
            ],
        }
    ]

    fixed = SubtitleGen()._apply_corrections(segments, {"助聽氣": "助聽器"})

    assert fixed[0]["text"] == "阿公的助聽器"
