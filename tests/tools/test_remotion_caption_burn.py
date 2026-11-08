"""Regression tests for Remotion talking-head caption prop generation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools.video.remotion_caption_burn import RemotionCaptionBurn


def test_remotion_video_src_is_relative_to_public_dir(tmp_path, monkeypatch):
    """Remotion's staticFile() requires paths relative to ``public/``.

    This exercises the prop-writing path without running ffprobe or npx.
    """
    composer_root = tmp_path / "remotion-composer"
    (composer_root / "node_modules").mkdir(parents=True)
    (composer_root / "package.json").write_text("{}", encoding="utf-8")

    source = tmp_path / "talking-head-input.mp4"
    source.write_bytes(b"fake video")
    output = tmp_path / "rendered.mp4"
    commands: list[list[str]] = []

    tool = RemotionCaptionBurn()
    monkeypatch.setattr(tool, "_find_remotion_root", lambda: composer_root)

    def fake_run_command(cmd, *args, **kwargs):
        commands.append(list(cmd))
        if cmd[:2] == ["ffprobe", "-v"] and "format=duration" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="1.25\n")
        if cmd[:2] == ["ffprobe", "-v"] and "stream=width,height" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="1280x720\n")
        if "remotion" in cmd and "render" in cmd:
            output.write_bytes(b"rendered video")
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr(tool, "run_command", fake_run_command)

    result = tool._render_remotion(
        input_path=str(source),
        output_path=str(output),
        captions=[{"word": "hello", "startMs": 0, "endMs": 500}],
        words_per_page=4,
        font_size=52,
        highlight_color="#22D3EE",
    )

    assert result.success, result.error
    props_path = composer_root / "public" / "demo-props" / "caption-burn-talking-head-input.json"
    props = json.loads(props_path.read_text(encoding="utf-8"))
    assert props["videoSrc"] == "talking-head/talking-head-input.mp4"
    assert not props["videoSrc"].startswith("public/")
    assert commands[0][0] == "ffprobe"
    assert commands[-1][0] in {"npx", "npx.cmd"}


# ---------------------------------------------------------------------- #
#  Thai captions: Whisper returns byte-level fragments, not words
# ---------------------------------------------------------------------- #

# Real faster-whisper (large-v3-turbo, language="th") output for
# "แมวตกจากที่สูงแล้ว ลงด้วยเท้า" — tone marks arrive as separate "words".
_THAI_FRAGMENTS = [
    ("แ", 0.0, 0.1), ("ม", 0.1, 0.2), ("ว", 0.2, 0.3), ("ต", 0.3, 0.4),
    ("ก", 0.4, 0.5), ("จ", 0.5, 0.6), ("าก", 0.6, 0.7), ("ท", 0.7, 0.8),
    ("ี่", 0.8, 0.9), ("ส", 0.9, 1.0), ("ู", 1.0, 1.1), ("ง", 1.1, 1.2),
    ("แล", 1.2, 1.3), ("้", 1.3, 1.4), ("ว", 1.4, 1.5), (" ล", 1.5, 1.6),
    ("ง", 1.6, 1.7), ("ด", 1.7, 1.8), ("้", 1.8, 1.9), ("วย", 1.9, 2.0),
    ("เท", 2.0, 2.1), ("้", 2.1, 2.2), ("า", 2.2, 2.3),
]


def _thai_segments():
    return [{
        "start": 0.0, "end": 2.3, "text": "แมวตกจากที่สูงแล้ว ลงด้วยเท้า",
        "words": [{"word": w, "start": s, "end": e} for w, s, e in _THAI_FRAGMENTS],
    }]


def test_thai_fragments_are_merged_into_words():
    captions = RemotionCaptionBurn()._segments_to_word_captions(_thai_segments())
    words = [c["word"] for c in captions]

    # No caption is a detached mark or a lone fragment, and the text is intact.
    assert "".join(words).replace(" ", " ") == "แมวตกจากที่สูงแล้ว ลงด้วยเท้า"
    assert "แมว" in words and "ด้วย" in words and "เท้า" in words
    assert not any(w in {"้", "ี่", "ู"} for w in words)
    # Timing comes from the fragments each word covers.
    mae = captions[words.index("แมว")]
    assert (mae["startMs"], mae["endMs"]) == (0, 300)
    # The real space after แล้ว survives as a non-breaking space.
    assert any(w.endswith(" ") for w in words)
    # Each segment ends a caption page.
    assert captions[-1]["pageBreakAfter"] is True


def test_thai_corrections_may_change_length_and_keep_timing():
    segs = _thai_segments()
    captions = RemotionCaptionBurn()._segments_to_word_captions(segs, {"เท้า": "อุ้งเท้า"})
    joined = "".join(c["word"] for c in captions)
    assert joined.endswith("อุ้งเท้า")
    assert captions[-1]["endMs"] == 2300


def test_thai_render_props_disable_word_separator(tmp_path, monkeypatch):
    composer_root = tmp_path / "remotion-composer"
    (composer_root / "node_modules").mkdir(parents=True)
    source = tmp_path / "thai.mp4"
    source.write_bytes(b"fake video")
    output = tmp_path / "out.mp4"

    tool = RemotionCaptionBurn()
    monkeypatch.setattr(tool, "_find_remotion_root", lambda: composer_root)
    monkeypatch.setattr(tool, "_remotion_available", lambda: True)

    def fake_run_command(cmd, *args, **kwargs):
        if "format=duration" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="2.3\n")
        if "stream=width,height" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="1080x1920\n")
        if "render" in cmd:
            output.write_bytes(b"rendered")
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    result = tool.execute({
        "input_path": str(source), "output_path": str(output), "segments": _thai_segments(),
    })

    assert result.success, result.error
    props = json.loads((composer_root / "public" / "demo-props" / "caption-burn-thai.json").read_text(encoding="utf-8"))
    assert props["captionWordSeparator"] == ""
    assert props["wordsPerPage"] == 6


def test_english_captions_unchanged():
    segs = [{"start": 0, "end": 1, "text": "Cats land", "words": [
        {"word": " Cats", "start": 0.0, "end": 0.5}, {"word": " land", "start": 0.5, "end": 1.0}]}]
    tool = RemotionCaptionBurn()
    captions = tool._segments_to_word_captions(segs)
    assert [c["word"] for c in captions] == ["Cats", "land"]
    assert "pageBreakAfter" not in captions[-1]
    assert tool._caption_word_separator(tool._segments_are_thai(segs)) is None


def test_thai_srt_is_segmented(tmp_path):
    srt = tmp_path / "th.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nแมวตกจากที่สูง\n", encoding="utf-8")
    captions = RemotionCaptionBurn()._srt_to_word_captions(str(srt))
    assert "".join(c["word"] for c in captions) == "แมวตกจากที่สูง"
    assert len(captions) > 1
    assert captions[0]["startMs"] == 0 and captions[-1]["endMs"] == 1000


# ---------------------------------------------------------------------- #
#  PR #879 review: case-insensitive corrections, stable Thai mode
# ---------------------------------------------------------------------- #


def _even_thai_segment(text, start=0.0, end=2.0):
    return [{"start": start, "end": end, "text": text}]


def test_thai_corrections_are_case_insensitive():
    tool = RemotionCaptionBurn()
    captions = tool._segments_to_word_captions(
        _even_thai_segment("ลองใช้ Cloud เพื่อทำงาน"), {"cloud": "Claude"})
    joined = "".join(c["word"] for c in captions)
    assert "Claude" in joined and "Cloud" not in joined


def test_thai_srt_corrections_are_case_insensitive(tmp_path):
    srt = tmp_path / "th.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nลองใช้ CLOUD เพื่อทำงาน\n", encoding="utf-8")
    captions = RemotionCaptionBurn()._srt_to_word_captions(str(srt), {"Cloud": "Claude"})
    joined = "".join(c["word"] for c in captions)
    assert "Claude" in joined and "CLOUD" not in joined


def _run_execute(tmp_path, monkeypatch, inputs, *, remotion=True):
    composer_root = tmp_path / "remotion-composer"
    (composer_root / "node_modules").mkdir(parents=True, exist_ok=True)
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake video")
    output = tmp_path / "out.mp4"
    srt_texts: list[str] = []

    tool = RemotionCaptionBurn()
    monkeypatch.setattr(tool, "_find_remotion_root", lambda: composer_root)
    monkeypatch.setattr(tool, "_remotion_available", lambda: remotion)

    def fake_run_command(cmd, *args, **kwargs):
        if "format=duration" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="2.0\n")
        if "stream=width,height" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="1080x1920\n")
        if cmd[0] == "ffmpeg":
            vf = cmd[cmd.index("-vf") + 1]
            path = vf.split("subtitles='", 1)[1].split("'", 1)[0].replace("\\:", ":")
            srt_texts.append(open(path, encoding="utf-8").read())
        output.write_bytes(b"rendered")
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    result = tool.execute({"input_path": str(source), "output_path": str(output), **inputs})
    assert result.success, result.error
    props_file = composer_root / "public" / "demo-props" / "caption-burn-clip.json"
    props = json.loads(props_file.read_text(encoding="utf-8")) if remotion else None
    return props, srt_texts


def test_latin_heavy_correction_keeps_thai_mode(tmp_path, monkeypatch):
    props, _ = _run_execute(tmp_path, monkeypatch, {
        "segments": _even_thai_segment("แมวใช้ openai"),
        "corrections": {"openai": "OpenMontage"},
    })
    assert props["captionWordSeparator"] == ""
    assert props["wordsPerPage"] == 6


def test_latin_heavy_correction_keeps_thai_mode_in_ffmpeg(tmp_path, monkeypatch):
    _, srt_texts = _run_execute(tmp_path, monkeypatch, {
        "segments": _even_thai_segment("แมวใช้ openai"),
        "corrections": {"openai": "OpenMontage"},
    }, remotion=False)
    text = srt_texts[0].split("\n")[2]
    assert text == "แมวใช้ OpenMontage"


def test_thai_correction_keeps_english_spacing(tmp_path, monkeypatch):
    segs = [{"start": 0, "end": 1, "text": "hi cat", "words": [
        {"word": " hi", "start": 0.0, "end": 0.5}, {"word": " cat", "start": 0.5, "end": 1.0}]}]
    props, _ = _run_execute(tmp_path, monkeypatch, {
        "segments": segs, "corrections": {"cat": "แมวน้อยน่ารักมาก"},
    })
    assert "captionWordSeparator" not in props
    assert props["wordsPerPage"] == 4


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
