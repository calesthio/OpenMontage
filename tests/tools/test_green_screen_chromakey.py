"""Regression tests: chromakey compositing must not collapse frames to 1x1.

`_process_chromakey` built the background from a 1x1 lavfi color source and
tried to size it with `[0:v]scale=iw:ih` — a no-op, since iw/ih are the 1x1
source's own dimensions. FFmpeg's `overlay` takes the size of its first input
(the 1x1 background), so every processed frame was clipped to a single pixel.
`_reconstruct_video` then upscaled those 1x1 frames, yielding a solid-color
video with the keyed subject entirely gone. The fix uses `scale2ref` to resize
the background to the actual frame dimensions.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.green_screen_processor import GreenScreenProcessor  # noqa: E402


def test_chromakey_filter_scales_background_to_frame():
    """Offline: the built filtergraph must not leave a 1x1 background."""
    captured = []

    def fake_run(self, cmd, **kwargs):
        captured.append(list(cmd))

        class _R:
            returncode = 0
            stdout = ""
            stderr = ""

        return _R()

    tool = GreenScreenProcessor()
    orig = GreenScreenProcessor.run_command
    GreenScreenProcessor.run_command = fake_run
    try:
        frames_dir = Path(PROJECT_ROOT) / "tests" / "tools"  # any dir; glob may be empty
        # Drive the filter build directly with a temp frame present.
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            fd = Path(td) / "frames"
            pd = Path(td) / "processed"
            fd.mkdir()
            pd.mkdir()
            (fd / "frame_0000.png").write_bytes(b"stub")
            tool._process_chromakey(fd, pd, "#0E172A", 1, 320, 240)
    finally:
        GreenScreenProcessor.run_command = orig

    ffmpeg_cmds = [c for c in captured if c and c[0] == "ffmpeg"]
    assert ffmpeg_cmds, "no ffmpeg command built"
    cmd = ffmpeg_cmds[0]
    fc = cmd[cmd.index("-filter_complex") + 1]
    # Background must be sized to the frame, not the old 1x1 no-op.
    assert "size=320x240" in " ".join(cmd), "background not sized to frame"
    assert "size=1x1" not in " ".join(cmd), "still using the 1x1 background"
    assert "[0:v]scale=iw:ih[bg]" not in fc, "still using the 1x1 no-op scale"
    # Alpha must be forced so keyed transparency survives on every FFmpeg build.
    assert "format=yuva420p" in fc, f"keyed alpha not forced: {fc}"


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
                    reason="ffmpeg/ffprobe required")
def test_chromakey_preserves_frame_size_and_keys(tmp_path):
    """End-to-end: output keeps the source size and keys green -> background."""
    frames_dir = tmp_path / "frames"
    processed_dir = tmp_path / "processed"
    frames_dir.mkdir()
    processed_dir.mkdir()

    frame = frames_dir / "frame_0000.png"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         "color=c=0x00FF00:size=320x240,drawbox=x=100:y=80:w=120:h=80:color=red:t=fill",
         "-frames:v", "1", str(frame)],
        capture_output=True, check=True, timeout=60,
    )

    ok = GreenScreenProcessor()._process_chromakey(
        frames_dir, processed_dir, "#0E172A", 1, 320, 240
    )
    assert ok

    out = processed_dir / "frame_0000.png"
    assert out.exists()

    def _size(p):
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "stream=width,height",
             "-of", "csv=p=0", str(p)],
            capture_output=True, text=True, timeout=30,
        )
        w, h = r.stdout.strip().split(",")
        return int(w), int(h)

    assert _size(out) == (320, 240), "frame collapsed instead of keeping source size"

    def _pixel(p, x, y):
        r = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-i", str(p), "-vf", f"crop=1:1:{x}:{y}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, timeout=30,
        )
        return r.stdout[:3]

    center = _pixel(out, 160, 120)   # red box -> stays red
    corner = _pixel(out, 10, 10)     # was green -> keyed to dark background
    assert center[0] > 150 and center[1] < 80, f"subject lost, center={center!r}"
    assert corner[0] < 60 and corner[1] < 60, f"green not keyed, corner={corner!r}"
