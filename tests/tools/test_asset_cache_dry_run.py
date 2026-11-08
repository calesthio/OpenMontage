"""Documented preflight must not restore cached files or overwrite outputs."""

import shutil
import subprocess

import pytest

from lib.asset_cache import get_default_asset_cache, reset_default_asset_cache
from tools.video.video_stitch import VideoStitch


@pytest.fixture(autouse=True)
def clean_owned_cache():
    reset_default_asset_cache()
    yield
    reset_default_asset_cache()


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
@pytest.mark.parametrize("existing_output", [False, True])
def test_actual_stitch_dry_run_bypasses_cached_output(
    tmp_path, monkeypatch, existing_output
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    clips = []
    for color in ("red", "blue"):
        source = tmp_path / f"{color}.mp4"
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
                f"color=c={color}:s=64x48:r=2:d=1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(source),
            ],
            check=True,
            timeout=10,
        )
        clips.append(str(source))
    request = {"operation": "stitch", "clips": clips, "transition": "cut"}
    first_path = tmp_path / "rendered.mp4"
    first = VideoStitch().execute({**request, "output_path": str(first_path)})
    assert first.success, first.error
    cache = get_default_asset_cache()
    original_manifest = cache.manifest_path.read_bytes()
    original_hits = cache.stats()["hits_this_session"]
    dry_path = tmp_path / "preflight.mp4"
    original = None
    if existing_output:
        shutil.copy2(clips[1], dry_path)
        original = dry_path.read_bytes()
    result = VideoStitch().execute(
        {**request, "output_path": str(dry_path), "dry_run": True}
    )
    assert result.success, result.error
    assert not result.from_cache
    assert result.artifacts == []
    assert result.data["would_execute"] is True
    assert result.data["clip_count"] == 2
    if existing_output:
        assert dry_path.read_bytes() == original
    else:
        assert not dry_path.exists()
    assert cache.manifest_path.read_bytes() == original_manifest
    assert cache.stats()["hits_this_session"] == original_hits
    restored_path = tmp_path / "normal-restored.mp4"
    restored = VideoStitch().execute(
        {**request, "output_path": str(restored_path), "dry_run": False}
    )
    assert restored.success and restored.from_cache
    assert restored_path.read_bytes() == first_path.read_bytes()
