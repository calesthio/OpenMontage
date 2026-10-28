"""Scene-guided samples must belong to the scene they describe."""
import shutil
import subprocess

import pytest

from tools.analysis.frame_sampler import FrameSampler


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize("start,end,channel", [(0, .08, 0), (.08, .48, 1), (.48, .56, 2)])
def test_scene_sample_stays_inside_its_shot(tmp_path, start, end, channel):
    video = tmp_path / "shots.mkv"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=red:s=16x16:r=50:d=0.08",
        "-f", "lavfi", "-i", "color=lime:s=16x16:r=50:d=0.4",
        "-f", "lavfi", "-i", "color=blue:s=16x16:r=50:d=0.08",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map", "[v]", "-c:v", "ffv1", str(video),
    ], check=True, timeout=30)
    result = FrameSampler().execute({
        "input_path": str(video), "strategy": "scene_guided", "format": "png",
        "output_dir": str(tmp_path / "frames"),
        "scene_boundaries": [{"start_seconds": start, "end_seconds": end}],
    })
    assert result.success, result.error
    frames = result.data["frames"]
    assert len(frames) == 1
    raw = subprocess.run([
        "ffmpeg", "-v", "error", "-i", frames[0]["path"],
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ], check=True, capture_output=True, timeout=30).stdout
    # The extracted pixel color is an oracle independent of timestamp metadata.
    assert raw[channel] > 200
    assert all(raw[i] < 20 for i in range(3) if i != channel)
    assert start <= frames[0]["timestamp_seconds"] < end
