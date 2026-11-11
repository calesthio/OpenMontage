"""A cache hit must report the materialized output, not an earlier destination."""

import shutil
import subprocess
from pathlib import Path

import pytest

from lib.asset_cache import reset_default_asset_cache
from tools.base_tool import _result_from_cache
from tools.video.green_screen_processor import GreenScreenProcessor


@pytest.fixture(autouse=True)
def reset_owned_cache():
    reset_default_asset_cache()
    yield
    reset_default_asset_cache()


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
def test_actual_chromakey_cache_hit_reports_restored_video(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=64x48:r=2:d=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        timeout=10,
    )
    request = {
        "input_path": str(source),
        "method": "chromakey",
        "fps": 2,
        "bg_color": "#0E172A",
    }
    first_path, restored_path = tmp_path / "first.mp4", tmp_path / "restored.mp4"
    first = GreenScreenProcessor().execute({**request, "output_path": str(first_path)})
    assert first.success, first.error
    original = first_path.read_bytes()
    first_path.unlink()
    restored = GreenScreenProcessor().execute(
        {**request, "output_path": str(restored_path)}
    )
    assert restored.success, restored.error
    assert restored.from_cache
    assert restored_path.read_bytes() == original
    assert restored.artifacts == [str(restored_path)]
    assert Path(restored.data["output_path"]) == restored_path
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            restored.data["output_path"],
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert probe.stdout.strip() == "64,48"


@pytest.mark.parametrize(
    "alias", ["outputs", "video_paths", "image_paths", "audio_paths"]
)
def test_single_output_aliases_rebind_without_rewriting_provenance(alias, tmp_path):
    old, new = str(tmp_path / "old.bin"), tmp_path / "new.bin"
    data = {
        "output": old,
        "output_path": old,
        alias: [old],
        "remote_outputs": ["https://example.invalid/media"],
        "source_url": "https://example.invalid/source",
        "input_path": "input.bin",
        "caption": old,
    }
    restored = {"data": data, "seed": 123, "model": "fixture"}
    result = _result_from_cache(restored, new)
    assert result.data["output"] == str(new)
    assert result.data["output_path"] == str(new)
    assert result.data[alias] == [str(new)]
    assert result.data["remote_outputs"] == data["remote_outputs"]
    assert result.data["source_url"] == data["source_url"]
    assert result.data["input_path"] == data["input_path"]
    assert result.data["caption"] == old
    assert data[alias] == [old]
    assert data["output"] == old
    assert result.seed == 123 and result.model == "fixture"


def test_nonmatching_or_multiple_output_entries_are_preserved(tmp_path):
    data = {
        "output": "old.mp4",
        "outputs": ["https://example.invalid/remote"],
        "video_paths": ["old.mp4", "another.mp4"],
    }
    result = _result_from_cache({"data": data}, tmp_path / "new.mp4")
    assert result.data["outputs"] == data["outputs"]
    assert result.data["video_paths"] == data["video_paths"]
