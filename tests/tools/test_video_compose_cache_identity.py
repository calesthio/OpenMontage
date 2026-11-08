"""video_compose must not serve a cached render made from different inputs.

video_compose is deterministic, so with OPENMONTAGE_ASSET_CACHE=1 every call
with an output_path goes through the asset cache. Its key used to cover only
operation, input_path and edit_decisions, so a second burn_subtitles call with
a different subtitle file, or an encode at a different crf, restored the first
call's video.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lib.asset_cache import reset_default_asset_cache
from tools.video.video_compose import VideoCompose

# Derived from the source, not from the key list: every top-level input that
# execute() reads, declared in input_schema or not. Neither field below
# changes the result.
_SOURCE = Path(VideoCompose.__module__.replace(".", "/") + ".py")
_READ = set(re.findall(
    r"""\binputs(?:\.get\(|\[)\s*["']([a-z_]+)["']""",
    (Path(__file__).resolve().parents[2] / _SOURCE).read_text(encoding="utf-8"),
))
_FIELDS = sorted(
    (_READ | set(VideoCompose.input_schema["properties"]))
    - {"output_path", "remotion_timeout_ms"}
)


def _has_subtitles_filter() -> bool:
    if not shutil.which("ffmpeg"):
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                         capture_output=True, text=True, timeout=10).stdout
    return " subtitles " in out


def test_field_list_is_not_empty():
    assert {"subtitle_path", "crf", "playbook"} <= set(_FIELDS)


@pytest.mark.parametrize("field", _FIELDS)
def test_every_rendering_input_changes_the_cache_key(field):
    tool = VideoCompose()
    base = {"operation": "render", "output_path": "out.mp4"}
    assert tool.cache_key(base) != tool.cache_key({**base, field: "changed"})


@pytest.mark.skipif(not _has_subtitles_filter(), reason="ffmpeg without libass")
@pytest.mark.parametrize(
    "operation,first,second",
    [
        ("burn_subtitles", {"subtitle_path": "a.srt"}, {"subtitle_path": "b.srt"}),
        ("encode", {"crf": 18}, {"crf": 40}),
    ],
)
def test_changed_input_is_rendered_not_restored(
    tmp_path, monkeypatch, operation, first, second
):
    src = tmp_path / "in.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=duration=1:size=160x120:rate=12",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
        check=True, timeout=30,
    )
    for name, text in [("a.srt", "FIRST"), ("b.srt", "SECOND")]:
        (tmp_path / name).write_text(f"1\n00:00:00,000 --> 00:00:01,000\n{text}\n")
    resolve = lambda d: {
        k: str(tmp_path / v) if k == "subtitle_path" else v for k, v in d.items()
    }

    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
    monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
    reset_default_asset_cache()
    tool = VideoCompose()
    try:
        results = [
            tool.execute({"operation": operation, "input_path": str(src),
                          "output_path": str(tmp_path / out), **resolve(extra)})
            for out, extra in [("first.mp4", first), ("second.mp4", second)]
        ]
    finally:
        reset_default_asset_cache()

    assert all(r.success for r in results), [r.error for r in results]
    assert results[1].from_cache is False
    assert (tmp_path / "first.mp4").read_bytes() != (tmp_path / "second.mp4").read_bytes()
