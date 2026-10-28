"""Exercise recorded crop updates through the actual local FFmpeg renderer."""

import json
import shutil
import subprocess

import pytest

from lib.asset_cache import reset_default_asset_cache
from tools.video.auto_reframe import AutoReframe

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="Native FFmpeg required"
)


def _bands(path):
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:size=96x64:rate=20:duration=1",
            "-vf",
            "drawbox=x=48:y=0:w=48:h=64:color=blue:t=fill",
            "-c:v",
            "libx264",
            str(path),
        ],
        capture_output=True,
        check=True,
        timeout=15,
    )


def _centre(path, timestamp):
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            str(timestamp),
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ],
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert len(result.stdout) == 36 * 64 * 3
    offset = (32 * 36 + 18) * 3
    return tuple(result.stdout[offset : offset + 3])


def _request(tmp_path, points):
    source, tracking, output = (
        tmp_path / "bands.mp4",
        tmp_path / "tracking.json",
        tmp_path / "crop.mp4",
    )
    _bands(source)
    tracking.write_text(
        json.dumps(
            {
                "faces": [
                    {
                        "timestamp_seconds": time,
                        "bbox": {"x": x, "y": 0.4, "width": 0.1, "height": 0.2},
                    }
                    for time, x in points
                ]
            }
        ),
        encoding="utf-8",
    )
    inputs = {
        "input_path": str(source),
        "face_tracking_json": str(tracking),
        "target_aspect": "portrait",
        "target_width": 36,
        "target_height": 64,
        "smoothing_window": 1,
        "output_path": str(output),
    }
    result = AutoReframe().execute(inputs)
    assert result.success, result.error
    return output, inputs


@pytest.mark.parametrize(
    "points,times",
    [
        ([(0, 0.05), (0.2, 0.85), (0.4, 0.05)], [0.05, 0.25, 0.65]),
        ([(0, 0.05), (0.5, 0.85), (0.8, 0.05)], [0.05, 0.65, 0.9]),
    ],
)
def test_three_recorded_poses_update_the_actual_crop(
    tmp_path, monkeypatch, points, times
):
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "0")
    output, _ = _request(tmp_path, points)
    colours = [_centre(output, time) for time in times]
    # Independently selected left/right/left regions of the real source frame.
    assert colours[0][0] > 200
    assert colours[1][2] > 200
    assert colours[2][0] > 200


@pytest.mark.parametrize(
    "points,channel",
    [
        ([(0, 0.05), (0.2, 0.05), (0.4, 0.05)], 0),
        ([(0, 0.05), (0.5, 0.85)], 2),
    ],
)
def test_stable_and_short_tracking_preserve_existing_static_controls(
    tmp_path, monkeypatch, points, channel
):
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "0")
    output, _ = _request(tmp_path, points)
    colours = [_centre(output, time) for time in [0.05, 0.5, 0.9]]
    assert all(colour[channel] > 200 for colour in colours)
    assert len(set(colours)) == 1


def test_repeated_dynamic_render_restores_identical_updated_video(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    reset_default_asset_cache()
    try:
        output, inputs = _request(tmp_path, [(0, 0.05), (0.5, 0.85), (0.8, 0.05)])
        assert _centre(output, 0.65)[2] > 200
        repeated_path = tmp_path / "repeat.mp4"
        repeated = AutoReframe().execute({**inputs, "output_path": str(repeated_path)})
        assert repeated.success and repeated.from_cache
        assert repeated_path.read_bytes() == output.read_bytes()
    finally:
        reset_default_asset_cache()
