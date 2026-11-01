"""Contracts for semantic Three.js world generation and atelier rendering."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from tools.base_tool import ToolResult
from tools.graphics.threejs_world import ThreeJSWorld
from tools.tool_registry import ToolRegistry
from tools.video.hyperframes_compose import HyperFramesCompose
from tools.video.video_compose import VideoCompose


def _world_spec(duration: float = 12.0) -> dict:
    return {
        "version": "1.0",
        "title": "The Luminous Divide",
        "seed": 260805248,
        "explicit_constraints": ["one continuous explorable world"],
        "inferred_details": ["cyan emissive accents provide visual continuity"],
        "world": {
            "size": 96,
            "resolution": 72,
            "elevation_scale": 12,
            "water_level": -1.5,
        },
        "regions": [
            {
                "id": "wetlands",
                "center": [-0.45, 0.15],
                "radius": 0.9,
                "landform": "basin",
                "color": "#204a43",
                "accent_color": "#71f7c4",
                "scatter": {"tree": 18, "rock": 8, "crystal": 6},
            },
            {
                "id": "rift",
                "center": [0.5, -0.1],
                "radius": 0.9,
                "landform": "canyon",
                "color": "#503040",
                "accent_color": "#ff765f",
                "scatter": {"tree": 0, "rock": 18, "crystal": 9},
            },
        ],
        "landmarks": [
            {
                "id": "threshold-ring",
                "type": "ring",
                "region_id": "wetlands",
                "position": [-22, 0, 8],
                "scale": 3.5,
            }
        ],
        "camera_path": [
            {"time": 0, "position": [-42, 23, 38], "target": [-18, 0, 4]},
            {"time": duration / 2, "position": [0, 16, 24], "target": [10, 0, -4]},
            {"time": duration, "position": [42, 25, -34], "target": [20, 0, -5]},
        ],
    }


def test_threejs_world_contract_and_registry_discovery():
    tool = ThreeJSWorld()
    assert tool.capability == "3d_world_generation"
    assert tool.provider == "threejs"
    assert "threejs-world-generation" in tool.agent_skills
    assert {"cinematic", "semantic", "wireframe"} == set(
        tool.input_schema["properties"]["render_mode"]["enum"]
    )

    registry = ToolRegistry()
    registry.discover("tools")
    assert "threejs_world" in {
        discovered.name
        for discovered in registry.get_by_capability("3d_world_generation")
    }


def test_threejs_world_validate_emits_worldclaw_diagnostics():
    result = ThreeJSWorld().execute(
        {"operation": "validate", "world_spec": _world_spec(), "duration_seconds": 12}
    )
    assert result.success, result.error
    report = result.data["report"]
    assert report["valid"] is True
    assert report["stats"]["region_count"] == 2
    assert report["stats"]["terrain_triangles"] > 0
    assert set(report["diagnostic_passes"]) == {"cinematic", "semantic", "wireframe"}
    assert report["review_views"] == [
        "global",
        "regional",
        "walk",
        "semantic",
        "wireframe",
    ]


def test_threejs_world_build_is_deterministic_and_editable(tmp_path):
    workspaces = [tmp_path / "first", tmp_path / "second"]
    hashes = []
    for workspace in workspaces:
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
        for filename in (
            "index.html",
            "world.css",
            "world-runtime.js",
            "world.json",
            "world-spec.js",
            "world-report.json",
            "hyperframes.json",
        ):
            assert (workspace / filename).is_file()
        index = (workspace / "index.html").read_text(encoding="utf-8")
        assert "--world-width: 1280px" in index
        assert 'data-render-mode="semantic"' in index
        hashes.append(
            hashlib.sha256((workspace / "world-spec.js").read_bytes()).hexdigest()
        )
    assert hashes[0] == hashes[1]
    assert json.loads((workspaces[0] / "world.json").read_text(encoding="utf-8"))[
        "seed"
    ] == 260805248


def test_threejs_world_rejects_incomplete_camera_path():
    spec = _world_spec()
    spec["camera_path"][-1]["time"] = 11
    result = ThreeJSWorld().execute(
        {"operation": "validate", "world_spec": spec, "duration_seconds": 12}
    )
    assert not result.success
    assert "Last camera key" in (result.error or "")


def test_production_tier_rejects_primitive_only_spec():
    result = ThreeJSWorld().execute({
        "operation": "validate",
        "world_spec": _world_spec(),
        "duration_seconds": 12,
        "quality_tier": "production",
        "asset_catalog_paths": [],
    })
    assert not result.success
    assert "asset catalog" in (result.error or "").lower()
    assert "asset-palette" in (result.error or "").lower()
    assert "terrain material" in (result.error or "").lower()


def test_blockout_tier_is_labeled_as_nonproduction():
    result = ThreeJSWorld().execute({
        "operation": "validate",
        "world_spec": _world_spec(),
        "duration_seconds": 12,
        "quality_tier": "blockout",
    })
    assert result.success
    assert result.data["report"]["quality_tier"] == "blockout"
    assert any("do not present" in warning.lower() for warning in result.data["report"]["warnings"])


def test_hyperframes_render_existing_preserves_authored_entry(tmp_path, monkeypatch):
    workspace = tmp_path / "world"
    workspace.mkdir()
    entry = workspace / "index.html"
    entry.write_text("<main data-composition-id='world'></main>", encoding="utf-8")
    tool = HyperFramesCompose()
    monkeypatch.setattr(tool, "_runtime_check", lambda: {"runtime_available": True})
    monkeypatch.setattr(tool, "_check", lambda inputs: ToolResult(success=True, data={"ok": True}))

    def fake_run(args, *, cwd, timeout, check):
        output = Path(args[args.index("--output") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"rendered")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(tool, "_run_hf", fake_run)
    output = tmp_path / "renders" / "final.mp4"
    result = tool.execute(
        {
            "operation": "render_existing",
            "workspace_path": str(workspace),
            "output_path": str(output),
            "quality": "draft",
        }
    )
    assert result.success, result.error
    assert result.data["authored_entry_preserved"] is True
    assert entry.read_text(encoding="utf-8") == "<main data-composition-id='world'></main>"
    assert output.is_file()


def test_video_compose_routes_empty_cut_atelier_to_existing_workspace(tmp_path, monkeypatch):
    captured = {}
    output = tmp_path / "final.mp4"

    def fake_hyperframes_execute(self, inputs):
        captured.update(inputs)
        Path(inputs["output_path"]).write_bytes(b"fake mp4")
        return ToolResult(success=True, data={"output": inputs["output_path"]})

    monkeypatch.setattr(VideoCompose, "_hyperframes_available", lambda self: True)
    monkeypatch.setattr(HyperFramesCompose, "execute", fake_hyperframes_execute)
    monkeypatch.setattr(
        VideoCompose,
        "_run_final_review",
        lambda self, *args, **kwargs: {"status": "pass", "issues_found": []},
    )

    result = VideoCompose().execute(
        {
            "operation": "render",
            "workspace_path": str(tmp_path / "world"),
            "output_path": str(output),
            "edit_decisions": {
                "version": "1.0",
                "cuts": [],
                "render_runtime": "hyperframes",
                "renderer_family": "bespoke",
                "composition_mode": "atelier",
                "bespoke": {"entry": "index.html"},
            },
        }
    )
    assert result.success, result.error
    assert captured["operation"] == "render_existing"
    assert captured["asset_manifest"] == {"version": "1.0", "assets": []}
    assert captured["edit_decisions"]["cuts"] == []
