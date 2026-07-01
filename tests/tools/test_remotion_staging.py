"""Tests for Remotion local-asset staging in video_compose (issue #237, PR #238).

Remotion's renderer only serves http(s) URLs or files under the composer's
public/ directory — file:// is rejected at render time. `_remotion_render` must
therefore stage local assets into public/_om_assets and rewrite the props to
staticFile-relative paths, for BOTH the Explainer shape (cuts[].source,
audio.narration/music.src) and the Cinematic shape (scenes[].src, top-level
soundtrack.src / music.src). It must also refresh a staged copy when the source
bytes change, so a regenerated asset written to the same path is not served stale.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose  # noqa: E402


def _capture_props(tool):
    """Patch run_command so a render 'succeeds' and the staged props are captured.

    Returns a dict that the caller reads after execute(): {"props": <staged props>}.
    """
    captured = {}

    def fake_run_command(cmd, *a, **k):
        # cmd = ["npx","remotion","render", index, comp_id, out_path, "--props", props_path]
        props_path = Path(cmd[cmd.index("--props") + 1])
        captured["props"] = json.loads(props_path.read_text())
        Path(cmd[5]).write_bytes(b"\x00")  # create output so exists() -> True
        return None

    tool.run_command = fake_run_command  # type: ignore[assignment]
    return captured


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/npx")
    return VideoCompose()


def test_cinematic_audio_and_scenes_are_staged(tool, tmp_path):
    soundtrack = tmp_path / "narration.wav"
    soundtrack.write_bytes(b"narration-bytes")
    music = tmp_path / "bed.mp3"
    music.write_bytes(b"music-bytes")
    scene_clip = tmp_path / "broll.mp4"
    scene_clip.write_bytes(b"broll-bytes")

    captured = _capture_props(tool)
    out = tmp_path / "renders" / "out.mp4"
    result = tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "scenes": [{"src": str(scene_clip)}],
                "soundtrack": {"src": str(soundtrack)},
                "music": {"src": f"file://{music}"},
            },
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    props = captured["props"]
    assert props["soundtrack"]["src"].startswith("_om_assets/")
    assert props["music"]["src"].startswith("_om_assets/")
    assert props["scenes"][0]["src"].startswith("_om_assets/")

    staged = PROJECT_ROOT / "remotion-composer" / "public" / "_om_assets"
    for key, original in (
        (props["soundtrack"]["src"], b"narration-bytes"),
        (props["music"]["src"], b"music-bytes"),
        (props["scenes"][0]["src"], b"broll-bytes"),
    ):
        assert (staged / Path(key).name).read_bytes() == original


def test_staged_copy_is_refreshed_when_source_changes(tool, tmp_path):
    src = tmp_path / "narration.wav"
    src.write_bytes(b"first-render")

    captured = _capture_props(tool)
    comp = {
        "renderer_family": "cinematic-trailer",
        "scenes": [],
        "soundtrack": {"src": str(src)},
    }
    out = tmp_path / "renders" / "out.mp4"

    r1 = tool._remotion_render({"composition_data": dict(comp), "output_path": str(out)})
    assert r1.success is True, r1.error
    staged_rel = captured["props"]["soundtrack"]["src"]
    staged_file = PROJECT_ROOT / "remotion-composer" / "public" / staged_rel
    assert staged_file.read_bytes() == b"first-render"

    # Regenerate the asset at the same path with new bytes.
    src.write_bytes(b"second-render-longer-bytes")
    r2 = tool._remotion_render({"composition_data": dict(comp), "output_path": str(out)})
    assert r2.success is True, r2.error
    assert staged_file.read_bytes() == b"second-render-longer-bytes"
