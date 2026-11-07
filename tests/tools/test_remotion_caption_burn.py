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
