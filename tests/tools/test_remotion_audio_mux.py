import shutil
import subprocess
from pathlib import Path

import pytest

from tools.video.video_compose import VideoCompose


pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required",
)


def _run(command: list[str]) -> None:
    subprocess.run(command, capture_output=True, check=True, timeout=30)


def test_external_audio_mux_adds_audible_stream_without_changing_video_length(tmp_path) -> None:
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.wav"
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "color=c=red:s=320x180:d=2:r=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
    ])
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=1", str(audio),
    ])

    result = VideoCompose()._mux_external_audio(video, audio)

    assert result.success, result.error
    streams = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type", "-of", "csv=p=0", str(video),
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout.splitlines()
    duration = float(subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(video),
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    ).stdout.strip())

    assert "video" in streams
    assert "audio" in streams
    assert duration == pytest.approx(2.0, abs=0.15)


# --- Termination and duration behaviour of the mux ---------------------------
#
# The mux used `-af apad` + `-shortest` with `-c:v copy`. apad emits audio
# forever and a stream-copied video never signals EOF to the filter graph, so
# `-shortest` had nothing to stop on: ffmpeg spun at 100% CPU and the output was
# never written. These tests pin the bounded behaviour. They run the real
# ffmpeg under a hard wall-clock limit so a regression fails instead of hanging
# the suite.


def _make_video(path: Path, seconds: int) -> None:
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"color=c=blue:s=320x180:d={seconds}:r=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ])


def _make_audio(path: Path, seconds: int) -> None:
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"sine=frequency=440:duration={seconds}", str(path),
    ])


def _probe(path: Path, entries: str) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0", str(path)],
        capture_output=True, check=True, text=True, timeout=30,
    ).stdout.strip()


def _record_commands(monkeypatch) -> list[tuple[list[str], dict]]:
    """Wrap run_command to record (cmd, kwargs) and enforce a hard 20 s limit."""
    calls: list[tuple[list[str], dict]] = []
    real = VideoCompose.run_command

    def spy(self, cmd, **kwargs):
        calls.append((list(cmd), dict(kwargs)))
        kwargs["timeout"] = min(kwargs.get("timeout") or 20, 20)
        return real(self, cmd, **kwargs)

    monkeypatch.setattr(VideoCompose, "run_command", spy)
    return calls


@pytest.mark.parametrize(
    "video_seconds, audio_seconds",
    [(2, 1), (2, 4)],
    ids=["audio-shorter-is-padded", "audio-longer-is-trimmed"],
)
def test_external_audio_mux_terminates_and_matches_video_duration(
    tmp_path, monkeypatch, video_seconds, audio_seconds
) -> None:
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.wav"
    _make_video(video, video_seconds)
    _make_audio(audio, audio_seconds)
    _record_commands(monkeypatch)

    result = VideoCompose()._mux_external_audio(video, audio)

    assert result.success, result.error
    assert "audio" in _probe(video, "stream=codec_type")
    assert float(_probe(video, "format=duration")) == pytest.approx(video_seconds, abs=0.2)
    leftovers = [p.name for p in tmp_path.iterdir() if ".audio-mux-" in p.name]
    assert not leftovers, f"temp mux output was not cleaned up: {leftovers}"


def test_external_audio_mux_never_uses_unbounded_apad_and_sets_a_timeout(
    tmp_path, monkeypatch
) -> None:
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.wav"
    _make_video(video, 2)
    _make_audio(audio, 1)
    calls = _record_commands(monkeypatch)

    assert VideoCompose()._mux_external_audio(video, audio).success

    cmd, kwargs = calls[-1]
    assert "-af" in cmd, "expected an explicit, bounded audio filter"
    audio_filter = cmd[cmd.index("-af") + 1]
    assert "apad" in audio_filter and "whole_dur=" in audio_filter, audio_filter
    assert "-shortest" not in cmd, "apad + -shortest + -c:v copy is the deadlocking pair"
    assert kwargs.get("timeout"), "the ffmpeg call must carry a wall-clock timeout"


def test_external_audio_mux_falls_back_to_shortest_without_apad_when_duration_unknown(
    tmp_path, monkeypatch
) -> None:
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.wav"
    _make_video(video, 2)
    _make_audio(audio, 1)
    calls = _record_commands(monkeypatch)
    monkeypatch.setattr(VideoCompose, "_probe_duration", staticmethod(lambda path: None))

    result = VideoCompose()._mux_external_audio(video, audio)

    assert result.success, result.error
    cmd, _ = calls[-1]
    assert "-shortest" in cmd
    assert "apad" not in " ".join(cmd), "unbounded apad must be dropped when duration is unknown"
