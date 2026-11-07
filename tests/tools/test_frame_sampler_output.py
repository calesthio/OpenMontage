from pathlib import Path

import pytest

from tools.analysis.frame_sampler import FrameSampler


@pytest.mark.parametrize("strategy", ["interval", "count", "timestamps", "scene_guided"])
def test_frame_sampler_does_not_report_frames_from_a_previous_run(tmp_path, monkeypatch, strategy):
    source = tmp_path / "input.mp4"
    source.touch()
    output = tmp_path / "frames"
    output.mkdir()
    stale = output / ("frame_0002.jpg" if strategy in ("interval", "count") else "frame_0001.jpg")
    stale.write_bytes(b"previous frame")
    sampler = FrameSampler()

    def write_frames(command):
        if "%04d" in command[-1]:
            Path(command[-1] % 1).write_bytes(b"new frame")
        elif float(command[command.index("-ss") + 1]) < 1:
            Path(command[-1]).write_bytes(b"new frame")

    monkeypatch.setattr(sampler, "run_command", write_frames)
    monkeypatch.setattr(sampler, "_get_duration", lambda _: 1.0)
    result = sampler.execute(
        {
            "input_path": str(source),
            "output_dir": str(output),
            "strategy": strategy,
            "timestamps": [0, 30],
            "scene_boundaries": [
                {"start_seconds": 0, "end_seconds": 1},
                {"start_seconds": 30, "end_seconds": 31},
            ],
        }
    )

    assert result.success
    assert result.data["frame_count"] == 1
    [frame] = result.data["frames"]
    frame_path = Path(frame["path"])
    assert frame_path.parent == output
    assert frame_path.read_bytes() == b"new frame"
    assert stale.read_bytes() == b"previous frame"
    assert sorted(output.iterdir()) == sorted([frame_path, stale])
