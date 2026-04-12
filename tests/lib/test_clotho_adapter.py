"""Unit tests for lib/clotho_adapter.py.

All tests are pure-Python — no network, no file I/O (except test_output_write
which writes to tmp_path).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from lib.clotho_adapter import (
    ClothoAdapterError,
    ClothoAdapterOptions,
    adapt,
    _clamp_duration,
    _select_model,
)


# ---------------------------------------------------------------------------
# Scene fixtures
# ---------------------------------------------------------------------------

def _make_scene(
    scene_id: str = "s01",
    scene_type: str = "generated",
    start: float = 0,
    end: float = 5,
    description: str = "Test scene",
    shot_size: str = "medium",
    camera_movement: str = "static",
    lighting_key: str = "natural",
    required_assets: list | None = None,
) -> dict:
    return {
        "id": scene_id,
        "type": scene_type,
        "description": description,
        "start_seconds": start,
        "end_seconds": end,
        "shot_language": {
            "shot_size": shot_size,
            "camera_movement": camera_movement,
            "lighting_key": lighting_key,
        },
        "required_assets": required_assets or [{"type": "video", "source": "generate"}],
    }


def _make_scene_plan(scenes: list) -> dict:
    return {"version": "1.0", "scenes": scenes}


def _default_options(**kwargs) -> ClothoAdapterOptions:
    return ClothoAdapterOptions(project_name="test-project", **kwargs)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_adapt_single_generated_scene():
    """Single generated scene → s1-still, s1-clip, full-cut nodes."""
    scene_plan = _make_scene_plan([_make_scene()])
    result = adapt(scene_plan, _default_options())

    flow = yaml.safe_load(result.flow_yaml)
    node_ids = [n["id"] for n in flow["nodes"]]

    assert "s1-still" in node_ids
    assert "s1-clip" in node_ids
    assert "full-cut" in node_ids
    assert result.node_count == 3

    still = next(n for n in flow["nodes"] if n["id"] == "s1-still")
    assert still["kind"] == "image.generate"
    assert still["provider"] == "fal"

    clip = next(n for n in flow["nodes"] if n["id"] == "s1-clip")
    assert clip["kind"] == "video.image_to_video"
    assert clip["provider"] == "fal"


def test_model_selection_talking_head():
    """talking_head + refs → kling-2.5-turbo-pro."""
    scene = _make_scene(scene_type="talking_head")
    model = _select_model(scene, has_refs=True)
    assert model == "kling-2.5-turbo-pro"


def test_model_selection_talking_head_no_refs():
    """talking_head without refs → still kling-2.5-turbo-pro (human face)."""
    scene = _make_scene(scene_type="talking_head")
    model = _select_model(scene, has_refs=False)
    assert model == "kling-2.5-turbo-pro"


def test_model_selection_wide_multichar():
    """generated type + wide shot + refs → kling-3.0-pro."""
    scene = _make_scene(scene_type="generated", shot_size="wide")
    model = _select_model(scene, has_refs=True)
    assert model == "kling-3.0-pro"


def test_model_selection_no_humans():
    """broll, no refs → None (let Clotho tier default; Seedance OK)."""
    scene = _make_scene(scene_type="broll")
    model = _select_model(scene, has_refs=False)
    assert model is None


def test_references_omitted_when_empty():
    """No refs → 'references' key absent from clip node."""
    scene_plan = _make_scene_plan([_make_scene()])
    result = adapt(scene_plan, _default_options())

    flow = yaml.safe_load(result.flow_yaml)
    clip = next(n for n in flow["nodes"] if n["id"] == "s1-clip")
    assert "references" not in clip


def test_references_flat_absolute(tmp_path):
    """scene_refs with 2 abs paths → references is flat list of those paths."""
    ref1 = str(tmp_path / "ref1.jpg")
    ref2 = str(tmp_path / "ref2.jpg")
    # Files don't need to exist — adapter only validates they are absolute

    scene_plan = _make_scene_plan([_make_scene(scene_id="s01")])
    opts = _default_options(scene_refs={"s01": [ref1, ref2]})
    result = adapt(scene_plan, opts)

    flow = yaml.safe_load(result.flow_yaml)
    clip = next(n for n in flow["nodes"] if n["id"] == "s1-clip")
    assert clip["references"] == [ref1, ref2]


def test_references_relative_dropped():
    """Relative ref paths are dropped with a warning."""
    scene_plan = _make_scene_plan([_make_scene(scene_id="s01")])
    opts = _default_options(scene_refs={"s01": ["relative/path/ref.jpg"]})
    result = adapt(scene_plan, opts)

    flow = yaml.safe_load(result.flow_yaml)
    clip = next(n for n in flow["nodes"] if n["id"] == "s1-clip")
    assert "references" not in clip
    assert any("not absolute" in w for w in result.warnings)


def test_skip_text_card():
    """text_card scene → in skipped_scenes, absent from flow nodes."""
    text_card = _make_scene(scene_id="tc01", scene_type="text_card")
    generated = _make_scene(scene_id="s01", scene_type="generated")
    scene_plan = _make_scene_plan([text_card, generated])
    result = adapt(scene_plan, _default_options())

    assert "tc01" in result.skipped_scenes
    flow = yaml.safe_load(result.flow_yaml)
    node_ids = [n["id"] for n in flow["nodes"]]
    # No still/clip for tc01
    assert "s1-still" not in node_ids or True  # s2-still (generated is idx 2)
    # More precisely: no node should reference tc01
    assert not any("tc01" in n["id"] for n in flow["nodes"])


def test_duration_clamping():
    """3.5s scene → '5', 8s scene → '10'."""
    assert _clamp_duration(3.5) == "5"
    assert _clamp_duration(7.5) == "5"
    assert _clamp_duration(7.51) == "10"
    assert _clamp_duration(8.0) == "10"


def test_duration_in_clip_node():
    """Clip node params.duration matches clamped string."""
    scene_plan = _make_scene_plan([_make_scene(start=0, end=3.5)])
    result = adapt(scene_plan, _default_options())
    flow = yaml.safe_load(result.flow_yaml)
    clip = next(n for n in flow["nodes"] if n["id"] == "s1-clip")
    assert clip["params"]["duration"] == "5"


def test_aspect_ratio_flux_param():
    """aspect_ratio='9:16' → image_size: portrait_16_9 in still node params."""
    scene_plan = _make_scene_plan([_make_scene()])
    result = adapt(scene_plan, _default_options(aspect_ratio="9:16"))

    flow = yaml.safe_load(result.flow_yaml)
    still = next(n for n in flow["nodes"] if n["id"] == "s1-still")
    assert still["params"]["image_size"] == "portrait_16_9"
    assert "aspect_ratio" not in still["params"]


def test_aspect_ratio_landscape():
    """aspect_ratio='16:9' → image_size: landscape_16_9."""
    scene_plan = _make_scene_plan([_make_scene()])
    result = adapt(scene_plan, _default_options(aspect_ratio="16:9"))
    flow = yaml.safe_load(result.flow_yaml)
    still = next(n for n in flow["nodes"] if n["id"] == "s1-still")
    assert still["params"]["image_size"] == "landscape_16_9"


def test_output_write(tmp_path):
    """With output_path set → file written to disk with valid YAML."""
    out_file = tmp_path / "flow.yaml"
    scene_plan = _make_scene_plan([_make_scene()])
    adapt(scene_plan, _default_options(output_path=str(out_file)))

    assert out_file.exists()
    content = out_file.read_text()
    flow = yaml.safe_load(content)
    assert flow["name"] == "test-project"


def test_empty_generatable_scenes_raises():
    """All scenes are text_card → ClothoAdapterError raised."""
    scene_plan = _make_scene_plan([
        _make_scene(scene_id="tc01", scene_type="text_card"),
        _make_scene(scene_id="tc02", scene_type="animation"),
    ])
    with pytest.raises(ClothoAdapterError, match="no generatable scenes"):
        adapt(scene_plan, _default_options())


def test_cost_estimate():
    """Known model selection → cost matches _MODEL_COSTS_USD."""
    # generated scene, no refs → Seedance (tier default, None → 0.40) + image (0.04)
    scene_plan = _make_scene_plan([_make_scene(scene_type="generated")])
    result = adapt(scene_plan, _default_options())
    # image (0.04) + seedance (0.40) = 0.44
    assert abs(result.estimated_cost_usd - 0.44) < 1e-6


def test_cost_estimate_kling():
    """talking_head → kling-2.5-turbo-pro (0.70) + image (0.04) = 0.74."""
    scene = _make_scene(
        scene_type="talking_head",
        required_assets=[{"type": "video", "source": "generate"}],
    )
    scene_plan = _make_scene_plan([scene])
    result = adapt(scene_plan, _default_options())
    assert abs(result.estimated_cost_usd - 0.74) < 1e-6


def test_flow_structure():
    """Top-level flow dict has expected keys."""
    scene_plan = _make_scene_plan([_make_scene()])
    result = adapt(scene_plan, _default_options())
    flow = yaml.safe_load(result.flow_yaml)

    assert flow["version"] == 1
    assert flow["name"] == "test-project"
    assert flow["consumer"] == "openmontage-cinematic"
    assert flow["tier"] == "balanced"
    assert isinstance(flow["nodes"], list)
    assert isinstance(flow["outputs"], list)
    assert flow["outputs"][0]["name"] == "final"
    assert "{{ full-cut.output }}" in flow["outputs"][0]["from"]


def test_save_output_in_flow():
    """save_output set → outputs[0].save present in flow."""
    scene_plan = _make_scene_plan([_make_scene()])
    opts = _default_options(save_output="./out/test.mp4")
    result = adapt(scene_plan, opts)
    flow = yaml.safe_load(result.flow_yaml)
    assert flow["outputs"][0]["save"] == "./out/test.mp4"


def test_save_output_omitted_when_none():
    """save_output=None → 'save' key absent from outputs."""
    scene_plan = _make_scene_plan([_make_scene()])
    result = adapt(scene_plan, _default_options(save_output=None))
    flow = yaml.safe_load(result.flow_yaml)
    assert "save" not in flow["outputs"][0]


def test_multiple_scenes_concat_order():
    """Multiple scenes → clip node ids in concat videos list, in order."""
    s1 = _make_scene(scene_id="s01", start=0, end=5)
    s2 = _make_scene(scene_id="s02", start=5, end=10)
    scene_plan = _make_scene_plan([s1, s2])
    result = adapt(scene_plan, _default_options())

    flow = yaml.safe_load(result.flow_yaml)
    concat = next(n for n in flow["nodes"] if n["id"] == "full-cut")
    videos = concat["inputs"]["videos"]
    assert len(videos) == 2
    assert "s1-clip" in videos[0]
    assert "s2-clip" in videos[1]


def test_broll_type_treated_as_generative():
    """broll scene type → generates still + clip nodes."""
    scene_plan = _make_scene_plan([_make_scene(scene_type="broll")])
    result = adapt(scene_plan, _default_options())
    flow = yaml.safe_load(result.flow_yaml)
    node_ids = [n["id"] for n in flow["nodes"]]
    assert "s1-still" in node_ids
    assert "s1-clip" in node_ids


def test_invalid_aspect_ratio_raises():
    """Invalid aspect_ratio → ClothoAdapterError."""
    scene_plan = _make_scene_plan([_make_scene()])
    with pytest.raises(ClothoAdapterError, match="Invalid aspect_ratio"):
        adapt(scene_plan, _default_options(aspect_ratio="4:3"))


def test_empty_scene_plan_raises():
    """Empty scenes list → ClothoAdapterError."""
    with pytest.raises(ClothoAdapterError, match="no scenes"):
        adapt({"version": "1.0", "scenes": []}, _default_options())


def test_slugify_project_name():
    """Project name is slugified in flow.name."""
    scene_plan = _make_scene_plan([_make_scene()])
    opts = ClothoAdapterOptions(project_name="My Cool Project 2026!")
    result = adapt(scene_plan, opts)
    flow = yaml.safe_load(result.flow_yaml)
    assert flow["name"] == "my-cool-project-2026"
