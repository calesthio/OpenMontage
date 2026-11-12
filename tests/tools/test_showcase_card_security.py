"""Security regression tests for showcase_card (GHSA-cg89-3297-mwhg).

Covers two issues raised on review of the initial subtitle-style fix:

1. [P1] title_color (and background_color) were still interpolated directly
   into the FFmpeg filtergraph, letting a crafted color literal append a
   second drawtext filter that reads an arbitrary local file into the
   output frame. _validate_color() must reject anything that isn't a bare
   named color or 0x/#-hex literal.
2. [P2] _drawtext_safe used to destroy literal punctuation in user text
   (stripped "%", "\\", turned ":" into " —"). The textfile+expansion=none
   approach must preserve the original text byte-for-byte.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from tools.video.showcase_card import (
    ShowcaseCard,
    _validate_color,
    _validate_font_file,
    _validate_int_range,
    _write_drawtext_textfile,
    _safe_filter_path,
)

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not available",
)


def _make_clip(path, w: int = 320, h: int = 240, d: int = 1) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"color=c=teal:s={w}x{h}:d={d}:r=10",
         "-c:v", "libx264", "-crf", "30", "-pix_fmt", "yuv420p",
         "-g", "10", "-keyint_min", "10", str(path)],
        capture_output=True, check=True,
    )


# --- Unit tests: pure validation logic, no FFmpeg needed ------------------


@pytest.mark.parametrize(
    "value",
    [
        "white",
        "0x0A0F1A",
        "0x0A0F1AFF",
        "#112233",
        "white@0.3",
        "red@1.0",
    ],
)
def test_validate_color_accepts_legitimate_literals(value):
    assert _validate_color("title_color", value) == value


@pytest.mark.parametrize(
    "payload",
    [
        # Reviewer-demonstrated attack: close the fontcolor value's filter
        # option list and append a second drawtext that reads a local file.
        "white':fontfile='/etc/hostname':x=0:y=0,drawtext=textfile='/etc/hostname",
        "white:drawtext=textfile=/etc/passwd",
        "white,drawtext=text=injected",
        "white'; rm -rf /",
        "",
    ],
)
def test_validate_color_rejects_filtergraph_breakout(payload):
    with pytest.raises(ValueError):
        _validate_color("title_color", payload)


def test_validate_font_file_rejects_path_and_quote_characters():
    assert _validate_font_file("title_font", "segoeuib.ttf") == "segoeuib.ttf"
    for payload in ("../../etc/passwd", "a.ttf':fontfile='b", "C:/evil.ttf", "no_extension"):
        with pytest.raises(ValueError):
            _validate_font_file("title_font", payload)


def test_validate_int_range_rejects_out_of_range_and_non_int():
    assert _validate_int_range("output_width", 1080, 16, 7680) == 1080
    for payload in (0, 100000, "1080", 10.5, True):
        with pytest.raises(ValueError):
            _validate_int_range("output_width", payload, 16, 7680)


def test_write_drawtext_textfile_preserves_literal_punctuation(tmp_path):
    for payload in ("Save 50%", "Time: 12:30", r"back\slash", "it's, a test"):
        path = _write_drawtext_textfile(tmp_path, payload)
        assert path.read_text(encoding="utf-8") == payload


# --- Integration tests: real FFmpeg, run through ShowcaseCard.execute() ---


@requires_ffmpeg
def test_title_color_injection_is_rejected_not_executed(tmp_path):
    """Reproduces the reviewer's title_color filtergraph-breakout and the
    canary-file-read it enabled; must now fail validation instead of
    reading the canary into the rendered output."""
    src = tmp_path / "in.mp4"
    _make_clip(src)
    canary = tmp_path / "canary.txt"
    canary.write_text("TOP-SECRET-CANARY", encoding="utf-8")

    tool = ShowcaseCard()
    result = tool.execute({
        "input_path": str(src),
        "output_path": str(tmp_path / "out.mp4"),
        "title": "Showcase",
        "title_color": f"white':fontfile='{canary}':x=0:y=0,drawtext=textfile='{canary}",
    })

    assert result.success is False
    assert not (tmp_path / "out.mp4").exists()


@requires_ffmpeg
def test_legitimate_render_with_tricky_punctuation_succeeds(tmp_path):
    src = tmp_path / "in.mp4"
    _make_clip(src)
    out = tmp_path / "out.mp4"

    tool = ShowcaseCard()
    result = tool.execute({
        "input_path": str(src),
        "output_path": str(out),
        "title": "Save 50% off!",
        "subtitle": "Ends: 12:30, don't miss it",
        "watermark": r"a\b",
    })

    assert result.success is True, result.error
    assert out.exists()


@requires_ffmpeg
def test_background_color_injection_is_rejected(tmp_path):
    src = tmp_path / "in.mp4"
    _make_clip(src)

    tool = ShowcaseCard()
    result = tool.execute({
        "input_path": str(src),
        "output_path": str(tmp_path / "out.mp4"),
        "title": "Showcase",
        "background_color": "black,drawtext=text=injected",
    })

    assert result.success is False


def test_filter_path_encodes_windows_drive_and_preserves_posix_paths():
    assert _safe_filter_path(PureWindowsPath(r"C:\Users\Jane Doe\text.txt")) == r"C\:/Users/Jane Doe/text.txt"
    assert _safe_filter_path(PurePosixPath("/tmp/Jane Doe/text.txt")) == "/tmp/Jane Doe/text.txt"
    assert _safe_filter_path(PurePosixPath("/tmp/time:12.txt")) == r"/tmp/time\:12.txt"
    with pytest.raises(ValueError, match="NUL"):
        _safe_filter_path(PurePosixPath("/tmp/bad\x00.txt"))


@requires_ffmpeg
@pytest.mark.parametrize("directory", ["spaces in path", "O'Brien", "comma,semi;[brackets]=value"])
def test_textfile_path_punctuation_preserves_rendered_frame(tmp_path, directory):
    """Compare real frames, so a parsed-but-truncated filename cannot pass."""
    text = "Save 50%: it's ready, a\\b %{n}"
    plain = _write_drawtext_textfile(tmp_path / "plain", text)
    special = _write_drawtext_textfile(tmp_path / directory, text)

    def frame(path):
        vf = f"drawtext=textfile='{_safe_filter_path(path)}':expansion=none:fontcolor=white:fontsize=24"
        return subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=640x160:d=0.1",
             "-vf", vf, "-frames:v", "1", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
            capture_output=True, check=True, timeout=20,
        ).stdout

    reference = frame(plain)
    assert frame(special) == reference
    assert any(pixel > 100 for pixel in reference)
    special.write_text("", encoding="utf-8")
    assert frame(special) != reference


@requires_ffmpeg
def test_showcase_render_in_quoted_temp_directory_and_cleanup(tmp_path, monkeypatch):
    src = tmp_path / "in.mp4"
    _make_clip(src)
    temp_root = tmp_path / "O'Brien, [temp]; files"
    temp_root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp_root))
    result = ShowcaseCard().execute({
        "input_path": str(src), "output_path": str(tmp_path / "out.mp4"),
        "title": "Save 50%", "subtitle": "Time: 12:30, don't miss it", "watermark": r"a\b",
        "output_width": 320, "output_height": 480,
    })
    assert result.success, result.error
    assert not list(temp_root.iterdir())


def test_subtitle_style_neutralises_force_style_payload():
    """The reviewer's force_style breakout must collapse into one inert value.

    ``_build_subtitle_style`` embeds every value inside
    ``-vf "subtitles=...:force_style='...'"``, so a value that keeps a quote,
    a comma, a colon or an ``=`` can close the quoted literal and append a
    second filter (the demonstrated attack appended a ``drawtext`` reading a
    local file into the frame). Assert structurally that nothing survives
    which could start a new filter, option or style entry.
    """
    from tools.video.video_compose import VideoCompose

    payload = ("Arial',drawtext=fontsize=30:fontcolor=white:textfile=canary.txt"
               ",drawtext=fontsize=10:text='")
    style = VideoCompose._build_subtitle_style({"font": payload})
    benign = VideoCompose._build_subtitle_style({"font": "Arial"})

    # No extra style entries were smuggled in alongside the legitimate ones.
    assert len(style.split(",")) == len(benign.split(","))

    for entry in style.split(","):
        key, sep, value = entry.partition("=")
        assert sep == "=", entry
        assert key.isalpha(), entry
        # A value holding any of these could terminate the quoted literal or
        # open a new filter / option / style entry.
        assert not set(value) & set(r"'\:,;[]="), entry


@requires_ffmpeg
def test_subtitle_style_payload_does_not_read_local_file(tmp_path):
    """Render real frames and assert the output cannot depend on a local file.

    The security property is that a crafted style value cannot make FFmpeg
    read a file off the machine into the frame -- so the frame must be
    identical whether or not the file the payload names exists. (An earlier
    version of this test compared the payload's frame against a frame
    rendered with ``FontName=Arial``; those differ for a benign reason --
    fontconfig resolves "Arial" to an installed face and falls back to its
    default family for the sanitised payload, so that comparison measured
    typeface selection rather than injection.)
    """
    from tools.video.video_compose import VideoCompose

    (tmp_path / "subs.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nNormal caption\n", encoding="utf-8")
    canary = tmp_path / "canary.txt"
    canary.write_text("REVIEW CANARY " * 8, encoding="utf-8")

    def frame(font):
        style = VideoCompose._build_subtitle_style({"font": font})
        return subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=640x360:d=0.1",
             "-vf", f"subtitles='subs.srt':force_style='{style}'", "-frames:v", "1",
             "-pix_fmt", "gray", "-f", "rawvideo", "-"],
            cwd=tmp_path, capture_output=True, check=True, timeout=20,
        ).stdout

    payload = ("Arial',drawtext=fontsize=30:fontcolor=white:textfile=canary.txt"
               ",drawtext=fontsize=10:text='")

    with_canary = frame(payload)
    # The caption itself must have rendered, so this is not two blank frames.
    assert any(pixel > 100 for pixel in with_canary)

    canary.unlink()
    # If the payload had injected a filter reading the canary, removing the
    # file would change the frame (or make FFmpeg fail outright).
    assert frame(payload) == with_canary

    # A payload naming a file that never existed is inert for the same reason.
    missing = ("Arial',drawtext=fontsize=30:fontcolor=white:textfile=missing.txt"
               ",drawtext=fontsize=10:text='")
    assert frame(missing) == with_canary
