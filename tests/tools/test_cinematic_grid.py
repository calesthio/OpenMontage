"""Grid scenes: 2-3 clips side by side in one CinematicRenderer time slot."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from tools.video.video_compose import VideoCompose

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA = json.loads(
    (PROJECT_ROOT / "schemas" / "artifacts" / "edit_decisions.schema.json").read_text()
)


def _cut(**overrides) -> dict:
    cut = {"id": "cut-1", "source": "a.mp4", "in_seconds": 1.0, "out_seconds": 3.0}
    cut.update(overrides)
    return cut


def test_grid_sources_become_a_grid_scene():
    scenes = VideoCompose._cuts_to_cinematic_scenes(
        [_cut(grid_sources=["a.mp4", "b.mp4", "c.mp4"])]
    )
    assert len(scenes) == 1
    scene = scenes[0]
    assert scene["kind"] == "grid"
    assert scene["durationSeconds"] == 2.0
    assert [c["src"] for c in scene["cells"]] == ["a.mp4", "b.mp4", "c.mp4"]
    # Every cell plays the cut's in/out window, not the whole clip from zero.
    for cell in scene["cells"]:
        assert cell["trimBeforeSeconds"] == 1.0
        assert cell["trimAfterSeconds"] == 3.0


def test_grid_scene_honours_hard_cut_transitions():
    [scene] = VideoCompose._cuts_to_cinematic_scenes(
        [_cut(grid_sources=["a.mp4", "b.mp4"], transition_in="cut", transition_out="cut")]
    )
    assert scene["fadeInFrames"] == 0
    assert scene["fadeOutFrames"] == 0


def test_single_grid_source_falls_back_to_a_plain_video_scene():
    [scene] = VideoCompose._cuts_to_cinematic_scenes([_cut(grid_sources=["a.mp4"])])
    assert scene["kind"] == "video"
    assert scene["src"] == "a.mp4"


def test_grid_scene_sits_on_the_sequential_timeline():
    scenes = VideoCompose._cuts_to_cinematic_scenes([
        _cut(id="cut-1"),
        _cut(id="cut-2", grid_sources=["b.mp4", "c.mp4"]),
        _cut(id="cut-3"),
    ])
    assert [s["kind"] for s in scenes] == ["video", "grid", "video"]
    assert [s["startSeconds"] for s in scenes] == [0.0, 2.0, 4.0]


def test_grid_cells_are_staged_into_the_public_dir(tmp_path):
    """Remotion can't read file:// or absolute paths during a render, so every
    cell must be copied into the --public-dir like a plain video src."""
    clips = []
    for name in ("left.mp4", "right.mp4"):
        p = tmp_path / "footage" / name
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(b"not really video")
        clips.append(str(p))

    props = {"scenes": VideoCompose._cuts_to_cinematic_scenes(
        [_cut(source=clips[0], grid_sources=clips)]
    )}
    public_dir = tmp_path / "public"
    assert VideoCompose._stage_remotion_media(props, public_dir) == 2
    for cell in props["scenes"][0]["cells"]:
        assert (public_dir / cell["src"]).is_file()


@pytest.mark.parametrize("grid_sources, valid", [
    (["a.mp4", "b.mp4"], True),
    (["a.mp4", "b.mp4", "c.mp4"], True),
    (["a.mp4"], False),
    (["a.mp4", "b.mp4", "c.mp4", "d.mp4"], False),
])
def test_schema_bounds_grid_sources(grid_sources, valid):
    doc = {
        "version": "1.0",
        "render_runtime": "remotion",
        "cuts": [_cut(grid_sources=grid_sources)],
    }
    if valid:
        jsonschema.validate(doc, SCHEMA)
    else:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, SCHEMA)
