"""Native encoders must not restore a different container from the asset cache."""

import json
import shutil
import subprocess

import pytest

from lib.asset_cache import reset_default_asset_cache
from tools.audio.audio_mixer import AudioMixer
from tools.video.video_stitch import VideoStitch


@pytest.fixture
def enabled_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_MAX_GB", "0.01")
    reset_default_asset_cache()
    yield
    reset_default_asset_cache()


def _ffmpeg(args):
    subprocess.run(["ffmpeg", "-v", "error", *args], capture_output=True, check=True, timeout=15)


def _format(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=format_name", "-of", "json", str(path)],
        capture_output=True, text=True, check=True, timeout=10,
    )
    return json.loads(result.stdout)["format"]["format_name"]


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
@pytest.mark.parametrize("kind", ["audio", "video"])
def test_changed_container_renders_but_same_format_renames_hit(tmp_path, monkeypatch, enabled_cache, kind):
    if kind == "audio":
        source = tmp_path / "source.wav"
        _ffmpeg(["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000:duration=0.4", str(source)])
        tool = AudioMixer()
        inputs = {"operation": "mix", "tracks": [{"path": str(source)}], "normalize": False}
        first_suffix, next_suffix, expected = "wav", "mp3", "mp3"
    else:
        clips = []
        for index in range(2):
            source = tmp_path / f"clip{index}.mp4"
            _ffmpeg(["-f", "lavfi", "-i", "color=size=32x32:rate=10:duration=0.4", "-c:v", "libx264", str(source)])
            clips.append(str(source))
        tool = VideoStitch()
        inputs = {"operation": "stitch", "clips": clips}
        first_suffix, next_suffix, expected = "mp4", "mkv", "matroska"

    def execute(name, suffix):
        output = tmp_path / f"{name}.{suffix}"
        result = tool.execute({**inputs, "output_path": str(output)})
        assert result.success, result.error
        return output, result

    cold_path, cold = execute("cold", first_suffix)
    renamed_path, renamed = execute("renamed", first_suffix.upper())
    assert not cold.from_cache
    assert renamed.from_cache
    assert renamed_path.read_bytes() == cold_path.read_bytes()

    changed_path, changed = execute("changed", next_suffix)
    # Native uncached execution is an independent container oracle; ffprobe
    # reads headers instead of trusting the destination's filename extension.
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "0")
    oracle_path, oracle = execute("oracle", next_suffix)
    assert not oracle.from_cache
    assert expected in _format(oracle_path)
    assert _format(changed_path) == _format(oracle_path)
    assert not changed.from_cache
    assert _format(changed_path) != _format(cold_path)


@pytest.mark.parametrize("output", [None, ""])
def test_key_api_accepts_absent_or_empty_destination(output):
    tool = AudioMixer()
    assert tool.cache_key({}) == tool.cache_key({"output_path": output})
