"""Silence detection must distinguish failed decoding from a clean recording."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tools.video.silence_cutter import SilenceCutter


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="native FFmpeg required")
@pytest.mark.parametrize("mode", ["remove", "speed_up", "mark"])
def test_invalid_media_reports_detection_failure(tmp_path: Path, mode: str) -> None:
    source = tmp_path / "invalid.mp4"
    source.write_bytes(b"not a media file")
    output = tmp_path / "result.mp4"

    result = SilenceCutter().execute({
        "input_path": str(source), "output_path": str(output), "mode": mode,
    })

    assert not result.success
    assert "silence detection failed" in result.error.lower()
    assert not output.exists()
    assert source.read_bytes() == b"not a media file"


def test_detection_timeout_is_not_reported_as_no_silence(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"placeholder")
    cutter = SilenceCutter()

    def fail(*_args, **_kwargs):
        raise TimeoutError("detection timed out")

    monkeypatch.setattr(cutter, "run_command", fail)
    result = cutter.execute({"input_path": str(source)})

    assert not result.success
    assert "detection timed out" in result.error
