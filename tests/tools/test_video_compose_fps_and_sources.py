"""Frame rate and asset-path resolution for video_compose's FFmpeg compose.

Two regressions of the same shape as the vertical-resolution bug covered in
`test_video_compose_vertical.py` -- the tool documented a contract and then
ignored it:

1. The per-segment filter chain hardcoded `fps=30` (and `-r 30`), so a caller
   composing 64fps interpolated footage got it silently decimated to 30, and
   16fps generative footage got uneven frame duplication that reads as judder.

2. `asset_manifest.schema.json` defines an asset `path` as a "relative path
   within the pipeline project directory", but cut sources were opened relative
   to the process CWD -- so a manifest that followed the schema only worked if
   the caller happened to run from inside the project directory.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tools.video.video_compose import VideoCompose

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not available",
)


def _make_clip(path: Path, fps: int = 30, d: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"color=c=teal:s=320x240:d={d}:r={fps}",
         "-c:v", "libx264", "-crf", "28", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, check=True,
    )


def _fps(path: Path) -> str:
    return subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(path)]
    ).decode().strip()


def _edit_decisions(src: Path, metadata: dict | None = None) -> dict:
    ed = {
        "version": "1.0",
        "render_runtime": "ffmpeg",
        "cuts": [{"id": "c1", "source": str(src), "in_seconds": 0, "out_seconds": 2}],
    }
    if metadata:
        ed["metadata"] = metadata
    return ed


# ---------------------------------------------------------------------------
# Frame rate
# ---------------------------------------------------------------------------

def test_compose_default_fps_is_30(tmp_path):
    """No fps requested → 30, exactly as before (backward compatible)."""
    src = tmp_path / "in.mp4"
    _make_clip(src, fps=24)
    out = tmp_path / "out.mp4"

    result = VideoCompose().execute({
        "operation": "compose",
        "edit_decisions": _edit_decisions(src),
        "output_path": str(out),
    })

    assert result.success, result.error
    assert _fps(out) == "30/1"


def test_compose_target_fps_is_honored(tmp_path):
    """A 64fps interpolated source stays 64fps when asked for."""
    src = tmp_path / "in64.mp4"
    _make_clip(src, fps=64)
    out = tmp_path / "out64.mp4"

    result = VideoCompose().execute({
        "operation": "compose",
        "edit_decisions": _edit_decisions(
            src, {"compose_target": {"width": 320, "height": 240, "fps": 64}}
        ),
        "output_path": str(out),
    })

    assert result.success, result.error
    assert _fps(out) == "64/1", "compose_target.fps was ignored — output decimated"


def test_inputs_fps_overrides_compose_target(tmp_path):
    """An explicit `fps` input wins over the artifact's compose_target."""
    src = tmp_path / "in.mp4"
    _make_clip(src, fps=30)
    out = tmp_path / "out.mp4"

    result = VideoCompose().execute({
        "operation": "compose",
        "edit_decisions": _edit_decisions(
            src, {"compose_target": {"width": 320, "height": 240, "fps": 24}}
        ),
        "fps": 50,
        "output_path": str(out),
    })

    assert result.success, result.error
    assert _fps(out) == "50/1"


@pytest.mark.parametrize("bad", [0, -5, "sixty", None])
def test_invalid_fps_falls_back_to_default(tmp_path, bad):
    """Garbage in compose_target.fps must not produce a broken ffmpeg command."""
    src = tmp_path / "in.mp4"
    _make_clip(src)
    out = tmp_path / f"out_{bad}.mp4"

    result = VideoCompose().execute({
        "operation": "compose",
        "edit_decisions": _edit_decisions(
            src, {"compose_target": {"width": 320, "height": 240, "fps": bad}}
        ),
        "output_path": str(out),
    })

    assert result.success, result.error
    assert _fps(out) == "30/1"


# ---------------------------------------------------------------------------
# Asset path resolution
# ---------------------------------------------------------------------------

def test_source_relative_to_project_dir_resolves(tmp_path):
    """The path layout the asset_manifest schema prescribes must work.

    `projects/<id>/assets/video/shot.mp4` referenced as `assets/video/shot.mp4`,
    with the output going to `projects/<id>/renders/`, and the process running
    from somewhere else entirely.
    """
    project = tmp_path / "projects" / "demo"
    clip = project / "assets" / "video" / "shot1.mp4"
    _make_clip(clip)
    out = project / "renders" / "final.mp4"

    resolved, tried = VideoCompose._resolve_source("assets/video/shot1.mp4", out)

    assert resolved == clip.resolve(), f"unresolved; tried {tried}"


def test_source_relative_to_cwd_still_resolves(tmp_path, monkeypatch):
    """Existing callers that pass CWD-relative paths keep working."""
    clip = tmp_path / "shots" / "shot1.mp4"
    _make_clip(clip)
    monkeypatch.chdir(tmp_path)

    resolved, _ = VideoCompose._resolve_source("shots/shot1.mp4", tmp_path / "out.mp4")

    assert resolved is not None and resolved.exists()


def test_absolute_source_is_used_as_given(tmp_path):
    clip = tmp_path / "abs.mp4"
    _make_clip(clip)

    resolved, _ = VideoCompose._resolve_source(str(clip), tmp_path / "out.mp4")

    assert resolved == clip


def test_missing_source_reports_every_base_tried(tmp_path):
    """The error must say where it looked, not just that a path is missing."""
    out = tmp_path / "projects" / "demo" / "renders" / "final.mp4"
    out.parent.mkdir(parents=True)

    resolved, tried = VideoCompose._resolve_source("assets/video/nope.mp4", out)

    assert resolved is None
    assert len(tried) == 2, tried
    assert any("projects/demo" in str(t) for t in tried)


def test_project_dir_inference():
    """`renders/` is the marker for a project workspace; anything else is not."""
    assert VideoCompose._project_dir_for(
        Path("/w/projects/demo/renders/final.mp4")
    ) == Path("/w/projects/demo")
    assert VideoCompose._project_dir_for(Path("/w/out/final.mp4")) == Path("/w/out")


def test_render_resolves_manifest_asset_by_id(tmp_path, monkeypatch):
    """End to end through the render op: id → schema-relative path → output."""
    project = tmp_path / "projects" / "demo"
    clip = project / "assets" / "video" / "shot1.mp4"
    _make_clip(clip)
    out = project / "renders" / "final.mp4"
    monkeypatch.chdir(tmp_path)  # not inside the project dir

    result = VideoCompose().execute({
        "operation": "render",
        "edit_decisions": {
            "version": "1.0",
            "render_runtime": "ffmpeg",
            "renderer_family": "cinematic-trailer",
            "cuts": [{"id": "c1", "source": "shot1", "in_seconds": 0, "out_seconds": 1}],
        },
        "asset_manifest": {
            "version": "1.0",
            "assets": [{
                "id": "shot1",
                "type": "video",
                "path": "assets/video/shot1.mp4",
                "source_tool": "test",
                "scene_id": "s1",
            }],
            "total_cost_usd": 0,
        },
        "output_path": str(out),
    })

    assert result.success, result.error
    assert out.exists()
