"""Concat calls must own their temporary files, including failed partial cuts."""
from pathlib import Path
from unittest.mock import patch

from tools.video.video_trimmer import VideoTrimmer


def test_nested_concat_keeps_outer_file_list(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    lists = []
    tool = VideoTrimmer()

    def run(cmd):
        file_list = Path(cmd[cmd.index("-i") + 1])
        lists.append(file_list)
        if len(lists) == 1:
            inner = tool.execute({"operation": "concat", "segments": [{"input_path": str(source)}],
                                  "output_path": str(tmp_path / "inner.mp4")})
            assert inner.success, inner.error
        assert file_list.exists()
        assert source.resolve().as_posix() in file_list.read_text()

    with patch.object(tool, "run_command", side_effect=run):
        result = tool.execute({"operation": "concat", "segments": [{"input_path": str(source)}],
                               "output_path": str(tmp_path / "outer.mp4")})
    assert result.success, result.error
    assert lists[0].parent != lists[1].parent
    assert all(not path.parent.exists() for path in lists)
    assert source.read_bytes() == b"source"


def test_partial_cut_is_removed_without_masking_error(tmp_path):
    source = tmp_path / "source.mp4"
    source.touch()
    partials = []

    def fail(cmd):
        partial = Path(cmd[-1])
        partial.write_bytes(b"partial")
        partials.append(partial)
        raise RuntimeError("cut failed")

    tool = VideoTrimmer()
    with patch.object(tool, "run_command", side_effect=fail):
        result = tool.execute({"operation": "concat", "segments": [{"input_path": str(source), "start_seconds": 1}],
                               "output_path": str(tmp_path / "output.mp4")})
    assert not result.success
    assert result.error == "cut failed"
    assert not partials[0].parent.exists()


def test_existing_concat_directory_is_not_owned_by_call(tmp_path):
    directory = tmp_path / ".concat_tmp"
    directory.mkdir()
    source = directory / "original.mp4"
    source.write_bytes(b"original")
    tool = VideoTrimmer()
    with patch.object(tool, "run_command"):
        result = tool.execute({"operation": "concat", "segments": [{"input_path": str(source)}],
                               "output_path": str(tmp_path / "output.mp4")})
    assert result.success, result.error
    assert source.read_bytes() == b"original"
