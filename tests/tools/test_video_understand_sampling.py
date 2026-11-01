"""Frame sampling in video_understand.

No network and no ffmpeg: subprocess.run is faked, so these assert the commands
the tool builds rather than what a particular ffmpeg build happens to return.
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest

from tools.analysis.video_understand import VideoUnderstand


class FakePIL:
    """Stand-in for PIL.Image.open(...).convert('RGB')."""

    def __init__(self, path):
        self.path = path

    def convert(self, _mode):
        return self


@pytest.fixture()
def fake_ffmpeg(monkeypatch):
    """Record every ffmpeg invocation and materialise the files it promises."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if cmd and cmd[0] == "ffmpeg":
            target = Path(cmd[-4])
            if "%04d" in target.name:
                for index in range(3):
                    target.with_name(target.name.replace("%04d", f"{index:04d}")).write_bytes(b"x")
            else:
                target.write_bytes(b"x")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("tools.analysis.video_understand.subprocess.run", fake_run)

    fake_image_module = types.SimpleNamespace(open=FakePIL)
    monkeypatch.setitem(
        __import__("sys").modules, "PIL",
        types.SimpleNamespace(Image=fake_image_module),
    )
    return calls


def _seek_positions(calls: list[list[str]]) -> list[float]:
    return [float(cmd[cmd.index("-ss") + 1]) for cmd in calls if "-ss" in cmd]


def test_samples_span_the_whole_clip(monkeypatch, fake_ffmpeg, tmp_path):
    """The regression this file exists for.

    `-vf thumbnail=N -frames:v N` reads as even sampling and is not: thumbnail=N
    picks the most representative frame out of each consecutive N-frame batch,
    so it never looks past the opening seconds. A four-second clip that is
    solid red for 2s then solid blue for 2s came back as four red frames, and
    the caption pass called it a video in which nothing changes.
    """
    monkeypatch.setattr(
        VideoUnderstand, "_video_duration_seconds", staticmethod(lambda _p: 100.0)
    )

    frames = VideoUnderstand()._extract_video_frames(tmp_path / "clip.mp4", None, 4)

    assert len(frames) == 4
    assert _seek_positions(fake_ffmpeg) == [12.5, 37.5, 62.5, 87.5]
    # The property the batching bug violated: the last sample is near the end.
    assert _seek_positions(fake_ffmpeg)[-1] > 75.0
    assert not any("thumbnail=" in " ".join(cmd) for cmd in fake_ffmpeg)


def test_explicit_frame_indices_still_use_the_select_filter(fake_ffmpeg, tmp_path):
    """That branch was already correct and must not change."""
    VideoUnderstand()._extract_video_frames(tmp_path / "clip.mp4", [3, 9, 27], 3)

    joined = " ".join(fake_ffmpeg[0])
    assert "select=" in joined
    assert "eq(n\\,3)" in joined and "eq(n\\,27)" in joined
    assert "-ss" not in fake_ffmpeg[0]


def test_falls_back_when_duration_is_unknown(monkeypatch, fake_ffmpeg, tmp_path):
    """A stream, or no ffprobe on PATH, must still yield frames."""
    monkeypatch.setattr(
        VideoUnderstand, "_video_duration_seconds", staticmethod(lambda _p: None)
    )

    frames = VideoUnderstand()._extract_video_frames(tmp_path / "stream.mp4", None, 3)

    assert frames, "the fallback must produce frames, not an empty list"
    assert not _seek_positions(fake_ffmpeg), "no duration means no seek positions"


@pytest.mark.parametrize("probe_output, expected", [
    ("12.5\n", 12.5),
    ("N/A\n", None),
    ("", None),
    ("0\n", None),        # a zero duration would divide the sampler by zero
    ("-3\n", None),
])
def test_duration_probe_rejects_unusable_values(monkeypatch, tmp_path, probe_output, expected):
    monkeypatch.setattr(
        "tools.analysis.video_understand.subprocess.run",
        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout=probe_output, stderr=""),
    )
    assert VideoUnderstand._video_duration_seconds(tmp_path / "c.mp4") == expected


def test_duration_probe_survives_a_missing_ffprobe(monkeypatch, tmp_path):
    def boom(*_a, **_k):
        raise FileNotFoundError("ffprobe")

    monkeypatch.setattr("tools.analysis.video_understand.subprocess.run", boom)
    assert VideoUnderstand._video_duration_seconds(tmp_path / "c.mp4") is None
