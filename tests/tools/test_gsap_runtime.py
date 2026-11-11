"""GSAP is served from a local npm install so HTML renders work offline.

`make setup` installs the pinned `gsap` package in remotion-composer/; the
HyperFrames scaffold, the character preview and the Three.js world copy that
build next to their HTML. Without the install they fall back to the pinned
CDN URL.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import tools.gsap_runtime as gsap_runtime
from tools.base_tool import ToolResult
from tools.gsap_runtime import GSAP_CDN_URL, GSAP_FILENAME, GSAP_VERSION, stage_gsap

REPO_ROOT = Path(__file__).resolve().parents[2]
FAKE_GSAP = "/*! GSAP test build */ window.gsap = {};\n"


@pytest.fixture
def local_gsap(tmp_path, monkeypatch) -> Path:
    source = tmp_path / "node_modules" / "gsap" / "dist" / GSAP_FILENAME
    source.parent.mkdir(parents=True)
    source.write_text(FAKE_GSAP, encoding="utf-8")
    monkeypatch.setattr(gsap_runtime, "LOCAL_GSAP_PATH", source)
    return source


@pytest.fixture
def no_local_gsap(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(gsap_runtime, "LOCAL_GSAP_PATH", tmp_path / "missing" / GSAP_FILENAME)


def test_stage_gsap_copies_local_build(tmp_path, local_gsap):
    target = tmp_path / "workspace"
    target.mkdir()
    assert stage_gsap(target) == GSAP_FILENAME
    assert (target / GSAP_FILENAME).read_text(encoding="utf-8") == FAKE_GSAP


def test_stage_gsap_falls_back_to_pinned_cdn(tmp_path, no_local_gsap):
    target = tmp_path / "workspace"
    target.mkdir()
    assert stage_gsap(target) == GSAP_CDN_URL
    assert f"gsap@{GSAP_VERSION}/" in GSAP_CDN_URL
    assert not (target / GSAP_FILENAME).exists()


def test_npm_manifest_pins_the_runtime_version():
    package = json.loads((REPO_ROOT / "remotion-composer" / "package.json").read_text(encoding="utf-8"))
    assert package["dependencies"]["gsap"] == GSAP_VERSION
    lock = json.loads((REPO_ROOT / "remotion-composer" / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"]["node_modules/gsap"]["version"] == GSAP_VERSION


def test_local_path_points_at_the_npm_install():
    expected = REPO_ROOT / "remotion-composer" / "node_modules" / "gsap" / "dist" / GSAP_FILENAME
    assert gsap_runtime.LOCAL_GSAP_PATH == expected


def test_tools_do_not_hard_code_a_gsap_cdn_url():
    """Every tool takes its GSAP src from tools/gsap_runtime.py."""
    offenders = []
    for path in (REPO_ROOT / "tools").rglob("*"):
        if path.suffix not in {".py", ".html", ".js"} or "__pycache__" in path.parts:
            continue
        if path.name == "gsap_runtime.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"gsap@\d|ajax/libs/gsap", text):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def _scaffold(tmp_path: Path) -> tuple[Path, ToolResult]:
    from tools.video.hyperframes_compose import HyperFramesCompose

    workspace = tmp_path / "hf"
    result = HyperFramesCompose().execute(
        {
            "operation": "scaffold_workspace",
            "workspace_path": str(workspace),
            "edit_decisions": {
                "version": "1.0",
                "render_runtime": "hyperframes",
                "cuts": [{"id": "c1", "type": "text_card", "text": "Hello", "in_seconds": 0, "out_seconds": 2}],
            },
            "asset_manifest": {"assets": []},
        }
    )
    assert result.success, result.error
    return workspace, result


def test_hyperframes_scaffold_uses_local_gsap(tmp_path, local_gsap):
    workspace, result = _scaffold(tmp_path)
    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert f'<script src="{GSAP_FILENAME}"></script>' in html
    assert "cdn.jsdelivr.net" not in html
    assert (workspace / GSAP_FILENAME).read_text(encoding="utf-8") == FAKE_GSAP
    assert result.data["gsap_src"] == GSAP_FILENAME


def test_hyperframes_scaffold_falls_back_to_cdn(tmp_path, no_local_gsap):
    workspace, result = _scaffold(tmp_path)
    html = (workspace / "index.html").read_text(encoding="utf-8")
    assert f'<script src="{GSAP_CDN_URL}"></script>' in html
    assert result.data["gsap_src"] == GSAP_CDN_URL


def _character_render(tmp_path: Path):
    from tools.character.character_animation import (
        ActionTimelineCompiler,
        CharacterRigRenderer,
        CharacterSpecGenerator,
        PoseLibraryBuilder,
        SvgRigBuilder,
    )

    design = CharacterSpecGenerator().execute(
        {"characters": [{"id": "lead", "role": "lead", "body_type": "round"}]}
    ).data["character_design"]
    rig_plan = SvgRigBuilder().execute({"character_design": design}).data["rig_plan"]
    pose_library = PoseLibraryBuilder().execute({"rig_plan": rig_plan}).data["pose_library"]
    scene_plan = {
        "version": "1.0",
        "scenes": [
            {
                "id": "scene-1",
                "type": "character_scene",
                "description": "Lead waves.",
                "start_seconds": 0,
                "end_seconds": 1,
                "character_actions": [
                    {"character_id": "lead", "emotion": "happy", "action_sequence": ["perform"]}
                ],
            }
        ],
    }
    timeline = ActionTimelineCompiler().execute(
        {"scene_plan": scene_plan, "character_ids": ["lead"]}
    ).data["action_timeline"]
    result = CharacterRigRenderer().execute(
        {
            "rig_plan": rig_plan,
            "pose_library": pose_library,
            "action_timeline": timeline,
            "output_path": str(tmp_path / "preview" / "preview.html"),
        }
    )
    assert result.success, result.error
    return result


def test_character_preview_uses_local_gsap(tmp_path, local_gsap):
    result = _character_render(tmp_path)
    preview = Path(result.data["preview_path"])
    html = preview.read_text(encoding="utf-8")
    assert f'<script src="{GSAP_FILENAME}"></script>' in html
    assert (preview.parent / GSAP_FILENAME).read_text(encoding="utf-8") == FAKE_GSAP
    assert result.data["gsap_src"] == GSAP_FILENAME


def test_character_sub_composition_relies_on_host_gsap(tmp_path, local_gsap):
    """The runtime clones the <template> into a host that already loads GSAP."""
    result = _character_render(tmp_path)
    composition = Path(result.data["composition_path"]).read_text(encoding="utf-8")
    assert "<script src=" not in composition
    assert "gsap.timeline(" in composition


def test_threejs_world_uses_local_gsap(tmp_path, local_gsap):
    from tools.graphics.threejs_world import ThreeJSWorld
    from tests.tools.test_threejs_world import _world_spec

    workspace = tmp_path / "world"
    result = ThreeJSWorld().execute(
        {
            "operation": "build",
            "world_spec": _world_spec(),
            "output_path": str(workspace),
            "duration_seconds": 12,
            "width": 1280,
            "height": 720,
            "render_mode": "semantic",
        }
    )
    assert result.success, result.error
    index = (workspace / "index.html").read_text(encoding="utf-8")
    assert f'<script src="{GSAP_FILENAME}"></script>' in index
    assert "__GSAP_SRC__" not in index
    assert (workspace / GSAP_FILENAME).read_text(encoding="utf-8") == FAKE_GSAP
