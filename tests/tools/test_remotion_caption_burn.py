"""Regression tests for Remotion talking-head caption prop generation."""

from __future__ import annotations

import json
import subprocess

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
