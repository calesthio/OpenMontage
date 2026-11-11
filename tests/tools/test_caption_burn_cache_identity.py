"""remotion_caption_burn must not serve a cached burn made from different captions.

The tool is deterministic, so with OPENMONTAGE_ASSET_CACHE=1 every call goes
through the asset cache. Its key covered only input_path, segments and
srt_path, so a rerun with corrections (or a new caption style) restored the
first, uncorrected video.
"""

import shutil
import subprocess

import pytest

from lib.asset_cache import reset_default_asset_cache
from tools.video.remotion_caption_burn import RemotionCaptionBurn


def _has_subtitles_filter() -> bool:
    if not shutil.which("ffmpeg"):
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                         capture_output=True, text=True, timeout=10).stdout
    return " subtitles " in out


_FIELDS = sorted(set(RemotionCaptionBurn.input_schema["properties"]) - {"output_path"})


def test_field_list_is_not_empty():
    assert "corrections" in _FIELDS


@pytest.mark.parametrize("field", _FIELDS)
def test_every_caption_input_changes_the_cache_key(field):
    tool = RemotionCaptionBurn()
    base = {"input_path": "in.mp4", "output_path": "out.mp4"}
    assert tool.cache_key(base) != tool.cache_key({**base, field: "changed"})


@pytest.mark.skipif(not _has_subtitles_filter(), reason="ffmpeg without libass")
def test_corrected_captions_are_burned_not_restored(tmp_path, monkeypatch):
    src = tmp_path / "in.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=duration=1:size=160x120:rate=12",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
        check=True, timeout=30,
    )
    segments = [{
        "start": 0.0, "end": 1.0, "text": "teh fox",
        "words": [{"word": "teh", "start": 0.0, "end": 0.5},
                  {"word": "fox", "start": 0.5, "end": 1.0}],
    }]

    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    reset_default_asset_cache()
    tool = RemotionCaptionBurn()
    try:
        results = [
            tool.execute({"input_path": str(src), "output_path": str(tmp_path / out),
                          "segments": segments, "force_ffmpeg": True, **extra})
            for out, extra in [("raw.mp4", {}),
                               ("fixed.mp4", {"corrections": {"teh": "the"}})]
        ]
    finally:
        reset_default_asset_cache()

    assert all(r.success for r in results), [r.error for r in results]
    assert results[1].from_cache is False
    assert (tmp_path / "raw.mp4").read_bytes() != (tmp_path / "fixed.mp4").read_bytes()
