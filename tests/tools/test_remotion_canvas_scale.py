"""Tests for the optional Remotion canvas size and render scale in video_compose.

The stock Explainer components use pixel sizes tuned for 1920x1080, so a
vertical render at a full 1080x1920 canvas draws text far too small. Rendering
a 720x1280 canvas with Remotion's `--scale=1.5` gives a 1080x1920 output with
everything 1.5x larger. These inputs map to `--width/--height` and `--scale`.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose  # noqa: E402


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/npx")
    return VideoCompose()


def _render_cmd(tool, tmp_path, monkeypatch, **extra) -> list[str]:
    seen = {}

    def fake_run_command(cmd, *a, **k):
        seen["cmd"] = cmd
        return None  # output file intentionally absent

    monkeypatch.setattr(tool, "run_command", fake_run_command)
    tool._remotion_render(
        {
            "composition_data": {"cuts": []},
            "output_path": str(tmp_path / "out.mp4"),
            **extra,
        }
    )
    return [str(c) for c in seen["cmd"]]


def _flag_values(cmd: list[str], flag: str) -> list[str]:
    return [cmd[i + 1] for i, c in enumerate(cmd) if c == flag]


def test_canvas_size_and_scale_are_passed_through(tool, tmp_path, monkeypatch):
    cmd = _render_cmd(
        tool, tmp_path, monkeypatch,
        composition_width=720, composition_height=1280, render_scale=1.5,
    )

    assert _flag_values(cmd, "--width") == ["720"]
    assert _flag_values(cmd, "--height") == ["1280"]
    assert "--scale=1.5" in cmd


def test_explicit_canvas_replaces_profile_dimensions(tool, tmp_path, monkeypatch):
    # Without this, Remotion would receive two --width/--height pairs.
    cmd = _render_cmd(
        tool, tmp_path, monkeypatch,
        profile="youtube_shorts", composition_width=720, composition_height=1280,
    )

    assert _flag_values(cmd, "--width") == ["720"]
    assert _flag_values(cmd, "--height") == ["1280"]


def test_profile_dimensions_unchanged_without_explicit_canvas(tool, tmp_path, monkeypatch):
    cmd = _render_cmd(tool, tmp_path, monkeypatch, profile="youtube_shorts")

    assert _flag_values(cmd, "--width") == ["1080"]
    assert _flag_values(cmd, "--height") == ["1920"]
    assert not any(c.startswith("--scale") for c in cmd)


def test_canvas_needs_both_dimensions(tool, tmp_path, monkeypatch):
    cmd = _render_cmd(tool, tmp_path, monkeypatch, composition_width=720)

    assert "--width" not in cmd
    assert "--height" not in cmd


def test_scale_alone_keeps_composition_size(tool, tmp_path, monkeypatch):
    cmd = _render_cmd(tool, tmp_path, monkeypatch, render_scale=2)

    assert "--scale=2.0" in cmd
    assert "--width" not in cmd


def test_high_level_render_forwards_canvas_and_scale(tool, tmp_path, monkeypatch):
    # execute(operation="render") -> _render() builds a fresh remotion_inputs
    # dict, so the options must be forwarded there too.
    captured = {}
    monkeypatch.setattr(tool, "_pre_compose_validation", lambda *a, **k: None)
    monkeypatch.setattr(tool, "_needs_remotion", lambda *a, **k: True)

    def fake_remotion_render(inputs):
        captured.update(inputs)
        from tools.base_tool import ToolResult

        return ToolResult(success=True, data={}, artifacts=[])

    monkeypatch.setattr(tool, "_remotion_render", fake_remotion_render)
    monkeypatch.setattr(tool, "_run_final_review", lambda *a, **k: {})

    tool._render(
        {
            "edit_decisions": {
                "render_runtime": "remotion",
                "renderer_family": "explainer-data",
                "cuts": [{"id": "c1", "source": "a1", "in_seconds": 0, "out_seconds": 2}],
            },
            "asset_manifest": {"assets": [{"id": "a1", "path": "/tmp/a1.mp4"}]},
            "output_path": str(tmp_path / "out.mp4"),
            "composition_width": 720,
            "composition_height": 1280,
            "render_scale": 1.5,
        }
    )

    assert captured.get("composition_width") == 720
    assert captured.get("composition_height") == 1280
    assert captured.get("render_scale") == 1.5


def test_inputs_are_declared_in_the_schema():
    props = VideoCompose.input_schema["properties"]

    assert props["composition_width"]["type"] == "integer"
    assert props["composition_height"]["type"] == "integer"
    assert props["render_scale"]["type"] == "number"
