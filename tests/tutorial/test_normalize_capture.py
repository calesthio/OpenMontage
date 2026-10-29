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


def test_extend_capture_holds_the_last_frame(tmp_path):
    # Cypress's screencast stops at the last screen change, so a static final
    # step is recorded shorter than its narration; the body is padded to fit.
    cap = tmp_path / "cap.mp4"
    _make_capture(cap, (), dur=3)
    got = bridge.extend_capture(str(cap), 5.5)
    assert abs(got - 5.5) < 0.1
    assert abs(bridge.probe(str(cap))["duration"] - 5.5) < 0.1
    assert _probe_wh(cap) == (1280, 720)


def test_extend_capture_leaves_a_long_enough_clip_alone(tmp_path):
    cap = tmp_path / "cap.mp4"
    _make_capture(cap, (), dur=3)
    before = cap.stat().st_mtime_ns
    assert abs(bridge.extend_capture(str(cap), 2.0) - 3.0) < 0.1
    assert cap.stat().st_mtime_ns == before


def test_align_marker_times_fills_a_missed_flash():
    # Steps at wall clock 0, 2, 3, 4 s; the video starts 1 s earlier and the
    # flash of the third step was not captured.
    got = bridge.align_marker_times([1.0, 3.02, 5.0], [0.0, 2.0, 3.0, 4.0])
    assert [round(t, 1) for t in got] == [1.0, 3.0, 4.0, 5.0]
    assert got[1] == 3.02  # a detected marker wins over the estimate


def test_align_marker_times_needs_two_agreeing_markers():
    assert bridge.align_marker_times([7.0], [0.0, 2.0]) == []


def test_normalize_capture_recovers_from_a_missed_marker(tmp_path):
    raw = tmp_path / "raw.mp4"
    _make_capture(raw, (1, 5))
    manifest = {
        "steps": [
            {"index": i, "narration": "x", "t_ms": t, "marker": {"heightPx": 6}}
            for i, t in enumerate((0, 2000, 4000))
        ]
    }
    norm = bridge.normalize_capture(str(raw), manifest, str(tmp_path / "cap.mp4"))
    assert [round(t) for t in norm["marker_times_s"]] == [1, 3, 5]


def test_marker_detected_below_a_runner_header(tmp_path):
    # The Cypress runner's header sits above the app, so the strip is not at y=0.
    raw = tmp_path / "raw.mp4"
    marks = (1, 3, 5)
    enable = "+".join(f"between(t,{t},{t + 0.15})" for t in marks)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x224466:s=1280x720:d=7:r=30",
         "-vf", f"drawbox=x=40:y=64:w=1200:h=6:color=magenta@1.0:t=fill:enable='{enable}'",
         "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", str(raw)], check=True)
    cfr = tmp_path / "cfr.mp4"
    bridge._to_cfr(str(raw), str(cfr))
    got = bridge.detect_marker_times(str(cfr), 6)
    assert len(got) == 3
    for g, exp in zip(got, marks):
        assert abs(g - exp) < 0.3
