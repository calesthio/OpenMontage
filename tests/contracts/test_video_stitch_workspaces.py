"""Stitch jobs sharing an output folder must not share intermediate files."""

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from tools.video.video_stitch import VideoStitch


def prepare_job(tmp_path, name, operation):
    clips = []
    for index in range(2):
        clip = tmp_path / f"{name}-{index}.mp4"
        clip.write_bytes(f"{name}-{index}".encode())
        clips.append(str(clip))
    return {
        "operation": operation,
        "clips": clips,
        "output_path": str(tmp_path / f"{name}.mp4"),
        "auto_normalize": True,
        "layout": "side_by_side",
    }


def stub_probe(monkeypatch):
    monkeypatch.setattr(VideoStitch, "_probe_clip", lambda *_: {
        "width": 160, "height": 90, "fps": 10, "duration": 1,
        "video_codec": "h264", "pixel_format": "yuv420p",
    })
    monkeypatch.setattr(VideoStitch, "_clip_has_audio", lambda *_: False)


@pytest.mark.parametrize("operation", ["stitch", "spatial"])
def test_overlapping_jobs_keep_their_own_intermediates(tmp_path, monkeypatch, operation):
    stub_probe(monkeypatch)
    outer_inputs = prepare_job(tmp_path, "outer", operation)
    inner_inputs = prepare_job(tmp_path, "inner", operation)
    inner_finished = False

    def run_command(self, cmd, **kwargs):
        nonlocal inner_finished
        output = Path(cmd[-1])
        if output == Path(outer_inputs["output_path"]) and not inner_finished:
            inner_finished = True
            # Finish another job while this job's final FFmpeg call is pending.
            inner_result = VideoStitch().execute(inner_inputs)
            assert inner_result.success, inner_result.error
        if "concat" in cmd:
            listing = Path(cmd[cmd.index("-i") + 1]).read_text(encoding="utf-8")
            sources = [Path(line[6:-1]) for line in listing.splitlines()]
        else:
            sources = [Path(cmd[index + 1]) for index, arg in enumerate(cmd) if arg == "-i"]
            # Silent audio augmentation also has a lavfi input.
            sources = [path for path in sources if not str(path).startswith("anullsrc=")]
        output.write_bytes(b"|".join(path.read_bytes() for path in sources))
        return CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(VideoStitch, "run_command", run_command)
    result = VideoStitch().execute(outer_inputs)
    assert result.success, result.error
    assert Path(outer_inputs["output_path"]).read_bytes() == b"outer-0|outer-1"
    assert Path(inner_inputs["output_path"]).read_bytes() == b"inner-0|inner-1"
    assert not list(tmp_path.glob(".*_tmp*"))
    for inputs in (outer_inputs, inner_inputs):
        assert all(Path(path).exists() for path in inputs["clips"])


@pytest.mark.parametrize("operation", ["stitch", "spatial"])
def test_failed_encoding_removes_partial_intermediates(tmp_path, monkeypatch, operation):
    stub_probe(monkeypatch)
    inputs = prepare_job(tmp_path, "failed", operation)

    def fail_encoding(self, cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"partial output")
        raise RuntimeError("encoding failed")

    monkeypatch.setattr(VideoStitch, "run_command", fail_encoding)
    result = VideoStitch().execute(inputs)
    assert not result.success
    assert "encoding failed" in result.error
    assert not list(tmp_path.glob(".*_tmp*"))
    assert all(Path(path).exists() for path in inputs["clips"])
