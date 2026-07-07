"""Marker-detection + normalize_capture tests (require ffmpeg)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.capture import cypress_bridge as bridge  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg required"
)


def _probe_wh(p):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(p)],
        text=True,
    )
    st = json.loads(out)["streams"][0]
    return int(st["width"]), int(st["height"])


def _make_capture(path, marks, w=1280, h=720, dur=7):
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", f"color=c=0x224466:s={w}x{h}:d={dur}:r=30"]
    if marks:
        enable = "+".join(f"between(t,{t},{t + 0.15})" for t in marks)
        cmd += ["-vf", f"drawbox=x=0:y=0:w=iw:h=6:color=magenta@1.0:t=fill:enable='{enable}'"]
    cmd += ["-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, check=True)


def test_marker_detection_and_letterbox(tmp_path):
    raw = tmp_path / "raw.mp4"
    marks = (1, 3, 5)
    _make_capture(raw, marks)
    manifest = {
        "steps": [
            {"index": i, "narration": "x", "t_ms": t * 1000, "marker": {"heightPx": 6}}
            for i, t in enumerate(marks)
        ]
    }
    norm = bridge.normalize_capture(str(raw), manifest, str(tmp_path / "cap.mp4"))
    assert len(norm["marker_times_s"]) == 3
    for got, exp in zip(norm["marker_times_s"], marks):
        assert abs(got - exp) < 0.3, (got, exp)
    assert _probe_wh(tmp_path / "cap.mp4") == (1920, 1080)


def test_no_markers_falls_back_gracefully(tmp_path):
    raw = tmp_path / "raw.mp4"
    _make_capture(raw, ())  # no flashes
    manifest = {"steps": [{"index": 0, "narration": "x", "t_ms": 500}]}  # no marker key
    norm = bridge.normalize_capture(str(raw), manifest, str(tmp_path / "cap.mp4"))
    assert norm["marker_times_s"] == []
    assert _probe_wh(tmp_path / "cap.mp4") == (1920, 1080)
