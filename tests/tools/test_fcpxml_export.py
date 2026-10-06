"""Tests for the fcpxml_export publisher tool.

Covers the tool contract, the FCPXML timeline structure for solo and grid
scenes, and the error paths.

The grid numbers asserted here (positions, crop percentages, the always-"1 1"
scale) were reverse-engineered from a timeline positioned by hand in DaVinci
Resolve and exported back out — Resolve's internal position unit space is not
the 1920x1080 canvas and its conversion isn't publicly documented. They cannot
be re-derived analytically, so these tests exist to pin them: if someone
"simplifies" the transform recipe, grid scenes silently stop compositing in
Resolve and only a manual import would reveal it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

from tools.base_tool import ToolStatus, ToolTier
from tools.publishers.fcpxml_export import build_fcpxml, export_project_to_fcpxml

pytestmark = pytest.mark.skipif(
    shutil.which("ffprobe") is None or shutil.which("ffmpeg") is None,
    reason="ffmpeg/ffprobe not available",
)


def _make_clip(path: Path, seconds: int = 2, with_audio: bool = False) -> None:
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
           f"color=c=teal:s=320x240:d={seconds}:r=30"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={seconds}",
                "-shortest", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-crf", "40", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, capture_output=True, check=True)


@pytest.fixture(scope="module")
def clips(tmp_path_factory) -> dict[str, str]:
    """Three real 2-second clips, keyed by the bare filename scene_plan uses."""
    d = tmp_path_factory.mktemp("clips")
    paths = {}
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        p = d / name
        _make_clip(p, with_audio=(name == "a.mp4"))
        paths[name] = str(p)
    return paths


def _scene(scene_id: str, start: float, end: float, *filenames: str) -> dict:
    return {
        "id": scene_id,
        "start_seconds": start,
        "end_seconds": end,
        "required_assets": [{"path": f} for f in filenames],
    }


def _make_project(
    root: Path, fps: int = 30, w: int = 320, h: int = 240, seconds: int = 2
) -> Path:
    """A minimal project workspace: one source clip + the two artifacts."""
    proj = root / "projects" / "demo"
    (proj / "artifacts").mkdir(parents=True)
    src = root / "footage" / "shot.mp4"
    src.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"color=c=teal:s={w}x{h}:d={seconds}:r={fps}",
         "-c:v", "libx264", "-crf", "40", "-pix_fmt", "yuv420p", str(src)],
        capture_output=True, check=True,
    )
    (proj / "artifacts" / "scene_plan.json").write_text(json.dumps({
        "scenes": [_scene("cut-1", 0.0, float(seconds), "shot.mp4")]
    }))
    (proj / "artifacts" / "asset_manifest.json").write_text(json.dumps({
        "assets": [{"type": "video", "path": str(src)}]
    }))
    return proj


def test_contract_metadata():
    from tools.publishers.fcpxml_export import FcpxmlExport

    tool = FcpxmlExport()
    info = tool.get_info()
    assert info["name"] == "fcpxml_export"
    assert info["capability"] == "publish"
    assert info["tier"] == ToolTier.PUBLISH.value
    assert info["provider"] == "fcpxml"
    assert info["resource_profile"]["network_required"] is False
    assert tool.get_status() == ToolStatus.AVAILABLE
    assert tool.estimate_cost({}) == 0.0


def test_registry_discovers_the_tool():
    from tools.tool_registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()
    names = {t.name for t in registry.get_by_capability("publish")}
    assert "fcpxml_export" in names


def test_cinematic_publish_stage_offers_the_tool():
    """An agent only uses what the stage's tools_available declares, so a tool
    absent from every manifest is unreachable through the documented path no
    matter that the registry can see it."""
    import yaml

    manifest = yaml.safe_load(
        (PROJECT_ROOT / "pipeline_defs" / "cinematic.yaml").read_text()
    )
    publish = next(s for s in manifest["stages"] if s["name"] == "publish")
    assert "fcpxml_export" in publish["tools_available"]


def test_solo_scene_becomes_a_spine_clip(clips):
    xml = build_fcpxml(
        [_scene("cut-1", 0.0, 2.0, "a.mp4")], clips, None, None, "demo"
    )
    assert '<format id="r1" name="FFVideoFormat1080p30"' in xml
    assert 'frameDuration="1/30s" width="1920" height="1080"' in xml
    # 2 seconds at 30fps == 60 frames
    assert 'offset="0/30s" duration="60/30s"' in xml
    assert 'lane=' not in xml


def test_fps_and_resolution_are_configurable(clips):
    """A 25fps vertical project must not be described as 1920x1080@30.

    Every timeline time in FCPXML is a rational over the frame rate, so a
    hardcoded 30 silently retimes 24/25/50/60fps footage on import.
    """
    xml = build_fcpxml(
        [_scene("cut-1", 0.0, 2.0, "a.mp4")], clips, None, None, "demo",
        fps=25, width=1080, height=1920,
    )
    assert 'frameDuration="1/25s" width="1080" height="1920"' in xml
    # 2 seconds at 25fps == 50 frames, not 60
    assert 'duration="50/25s"' in xml
    assert "/30s" not in xml


def test_export_detects_fps_and_resolution_from_the_source(tmp_path):
    """The sequence format should follow the footage, not a hardcoded default.

    Handing 25fps footage to Resolve inside a 30fps sequence conforms every
    clip on import, which shifts every downstream cut.
    """
    proj = _make_project(tmp_path, fps=25, w=640, h=480)
    out_path, _, _ = export_project_to_fcpxml(proj)
    xml = Path(out_path).read_text()
    assert 'frameDuration="1/25s" width="640" height="480"' in xml


def test_execute_accepts_an_explicit_format_override(tmp_path):
    """Source-derived format is a default, not a mandate — a 4K source may
    still be finished in a 1080p sequence."""
    from tools.publishers.fcpxml_export import FcpxmlExport

    proj = _make_project(tmp_path, fps=30, w=640, h=480)
    result = FcpxmlExport().execute(
        {"project_dir": str(proj), "fps": 24, "width": 1920, "height": 1080}
    )
    assert result.success is True
    xml = Path(result.data["fcpxml_path"]).read_text()
    assert 'frameDuration="1/24s" width="1920" height="1080"' in xml


def test_missing_ffprobe_returns_a_tool_error(tmp_path, monkeypatch):
    """The tool declares dependencies=['cmd:ffprobe'], but declaring it doesn't
    stop the call — a missing binary raised FileNotFoundError straight out of
    execute() instead of the contract's ToolResult(success=False)."""
    from tools.publishers.fcpxml_export import FcpxmlExport

    proj = _make_project(tmp_path)
    monkeypatch.setenv("PATH", "")  # ffprobe is now unresolvable
    result = FcpxmlExport().execute({"project_dir": str(proj)})
    assert result.success is False
    assert "ffprobe" in (result.error or "").lower()


def test_unreadable_media_returns_a_tool_error(tmp_path):
    """A file ffprobe can't parse should name the file, not surface a raw
    JSON decode error from the probe's empty stdout."""
    from tools.publishers.fcpxml_export import FcpxmlExport

    proj = _make_project(tmp_path)
    bogus = proj / "artifacts" / "broken.mp4"
    bogus.write_text("this is not a video")
    (proj / "artifacts" / "asset_manifest.json").write_text(json.dumps({
        "assets": [{"type": "video", "path": str(bogus)}]
    }))
    (proj / "artifacts" / "scene_plan.json").write_text(json.dumps({
        "scenes": [_scene("cut-1", 0.0, 2.0, "broken.mp4")]
    }))

    result = FcpxmlExport().execute({"project_dir": str(proj)})
    assert result.success is False
    assert "broken.mp4" in (result.error or "")


def test_sdr_substitutions_are_reported_not_silent(tmp_path):
    """The Dolby Vision workaround swaps sources behind the user's back.

    If assets/transcoded_sdr/<stem>.mp4 exists the timeline quietly points at
    it instead of the original. That's the right behaviour — HDR clips don't
    decode in Resolve on some machines — but an editor comparing the FCPXML
    against their asset_manifest has no way to know it happened, so the tool
    has to say so.
    """
    from tools.publishers.fcpxml_export import FcpxmlExport

    proj = _make_project(tmp_path)
    sdr_dir = proj / "assets" / "transcoded_sdr"
    sdr_dir.mkdir(parents=True)
    _make_clip(sdr_dir / "shot.mp4")

    result = FcpxmlExport().execute({"project_dir": str(proj)})
    assert result.success is True
    assert result.data["sdr_substitutions"] == ["shot.mp4"]
    # ...and the timeline really does point at the SDR copy.
    assert "transcoded_sdr" in Path(result.data["fcpxml_path"]).read_text()


def test_two_up_grid_uses_verified_resolve_transform(clips):
    xml = build_fcpxml(
        [_scene("cut-1", 0.0, 2.0, "a.mp4", "b.mp4")], clips, None, None, "demo"
    )
    # Second cell is a connected clip on lane 1, not a second spine item.
    assert 'lane="1"' in xml
    # The verified 2-up recipe: no crop, conform-to-fit, scale always 1 1.
    assert '<adjust-conform type="fit"/>' in xml
    assert '<adjust-transform position="-99.63 0" anchor="0 0" scale="1 1"/>' in xml
    assert '<adjust-transform position="99.63 0" anchor="0 0" scale="1 1"/>' in xml
    assert "adjust-crop" not in xml


def test_three_up_grid_crops_and_positions_each_cell(clips):
    xml = build_fcpxml(
        [_scene("cut-1", 0.0, 2.0, "a.mp4", "b.mp4", "c.mp4")],
        clips, None, None, "demo",
    )
    assert '<trim-rect right="16.5" left="16.5"/>' in xml
    for pos in ("-145.6 0", "0.0 0", "145.6 0"):
        assert f'<adjust-transform position="{pos}" anchor="0 0" scale="1 1"/>' in xml
    assert 'lane="1"' in xml and 'lane="2"' in xml


def test_unsupported_grid_width_is_rejected_not_silently_stacked(clips):
    """Only 2-up and 3-up have verified Resolve transforms.

    Without a template every cell got no adjustments at all, so all four
    rendered full-frame stacked on each other and only the top one was
    visible — a timeline that imports cleanly and is silently wrong. Failing
    loudly is the only honest option until a 4-up template is measured.
    """
    with pytest.raises(ValueError, match="4"):
        build_fcpxml(
            [_scene("cut-1", 0.0, 2.0, "a.mp4", "b.mp4", "c.mp4", "a.mp4")],
            clips, None, None, "demo",
        )


def test_connected_clips_are_relative_to_their_anchor(clips):
    """Regression: connected-clip offset is relative to the anchor, not the
    timeline. Using the scene's absolute offset double-counted it and made
    lanes lag further behind the later a grid fell in the timeline."""
    xml = build_fcpxml(
        [
            _scene("cut-1", 0.0, 2.0, "a.mp4"),
            _scene("cut-2", 2.0, 4.0, "b.mp4", "c.mp4"),
        ],
        clips, None, None, "demo",
    )
    # The anchor sits at the absolute timeline position...
    assert 'offset="60/30s" duration="60/30s"' in xml
    # ...but its connected cell restarts from zero.
    assert 'lane="1" offset="0s"' in xml


def test_music_lands_on_a_negative_lane(clips, tmp_path):
    music = tmp_path / "bed.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:d=4",
         "-c:a", "libmp3lame", str(music)],
        capture_output=True, check=True,
    )
    xml = build_fcpxml(
        [_scene("cut-1", 0.0, 2.0, "a.mp4")], clips, str(music), 4.0, "demo"
    )
    assert 'lane="-1"' in xml
    assert 'hasAudio="1" audioSources="1" audioChannels="2" hasVideo="0"' in xml
