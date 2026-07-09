from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.base_tool import ToolResult

from backlot import jobs
from lib.checkpoint import init_project
from schemas.artifacts import validate_artifact


def _request(video_model: str = "grok-imagine-video") -> dict[str, Any]:
    return {
        "version": "1.0",
        "project_id": "p",
        "title": "Saree",
        "prompt": "Create a premium saree ad faithful to attached references.",
        "aspect_ratio": "9:16",
        "duration_seconds": 12,
        "scene_count": 2,
        "video_model": video_model,
        "video_model_label": video_model,
        "video_provider": video_model,
        "model_variant": "grok-imagine-video" if video_model == "grok-imagine-video" else "veo3.1",
        "reference_assets": [
            {"asset_id": "r1", "url": "https://cdn.example/ref1.png", "content_type": "image/png", "path": "ref1.png"},
            {"asset_id": "r2", "url": "https://cdn.example/ref2.png", "content_type": "image/png", "path": "ref2.png"},
        ],
    }


def _scene_plan() -> dict[str, Any]:
    return {
        "version": "1.0",
        "scenes": [
            {
                "id": "sc1",
                "description": "Macro textile detail",
                "shot_intent": "Open on the Warli motif",
                "start_seconds": 0,
                "end_seconds": 6,
            },
            {
                "id": "sc2",
                "description": "Pallu movement",
                "shot_intent": "Continue the same saree in motion",
                "start_seconds": 6,
                "end_seconds": 12,
            },
        ],
    }


class FakeVideoSelector:
    calls: list[dict[str, Any]] = []

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        self.calls.append(dict(inputs))
        output = Path(str(inputs["output_path"]))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake-video")
        return ToolResult(
            success=True,
            data={
                "selected_tool": "fake_provider_tool",
                "selected_provider": str(inputs.get("preferred_provider") or "fake"),
                "duration_seconds": 6,
                "resolution": inputs.get("resolution", "720p"),
            },
            artifacts=[str(output)],
            cost_usd=0.12,
            model="fake-model",
        )


def _wire_fakes(monkeypatch, tmp_path):
    from tools.video import video_selector

    FakeVideoSelector.calls = []
    monkeypatch.setattr(jobs, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(video_selector, "VideoSelector", FakeVideoSelector)
    monkeypatch.setattr(jobs, "_qa_video_clip", lambda path, duration: {"warnings": [], "duration_ok": True})
    monkeypatch.setattr(
        jobs.storage,
        "upload_file",
        lambda path, project_id, rel: {"key": f"{project_id}/{rel}", "url": f"https://cdn.example/{project_id}/{rel}"},
    )

    def fake_extract(video_path: Path, output_path: Path) -> bool:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(f"last-frame:{video_path.name}".encode("utf-8"))
        return True

    monkeypatch.setattr(jobs, "_extract_last_frame", fake_extract)


def test_generate_assets_routes_through_video_selector_and_chains_last_frame(monkeypatch, tmp_path):
    _wire_fakes(monkeypatch, tmp_path)
    project_dir = init_project("p", title="P", pipeline_type="cinematic", pipeline_dir=tmp_path)

    manifest = jobs._generate_assets("p", project_dir, _request(), _scene_plan(), sample_only=False)

    validate_artifact("asset_manifest", manifest)
    assert len(FakeVideoSelector.calls) == 2
    assert FakeVideoSelector.calls[0]["operation"] == "reference_to_video"
    assert FakeVideoSelector.calls[0]["preferred_provider"] == "grok"
    assert FakeVideoSelector.calls[0]["reference_image_urls"] == [
        "https://cdn.example/ref1.png",
        "https://cdn.example/ref2.png",
    ]
    assert FakeVideoSelector.calls[1]["operation"] == "image_to_video"
    assert FakeVideoSelector.calls[1]["reference_image_path"].endswith("assets/chaining/sc1_last.jpg")
    assert manifest["metadata"]["generation_adapter"] == "hosted_pipeline.video_selector_sequence"
    assert manifest["metadata"]["generation_runs"][1]["chain_source_used"] is True
    assert manifest["metadata"]["generation_runs"][1]["chaining_mode"] == "image_to_video_from_previous_last_frame"
    assert manifest["total_cost_usd"] == 0.24


def test_generate_assets_uses_sample_first_before_batch(monkeypatch, tmp_path):
    _wire_fakes(monkeypatch, tmp_path)
    project_dir = init_project("p", title="P", pipeline_type="cinematic", pipeline_dir=tmp_path)

    manifest = jobs._generate_assets("p", project_dir, _request(), _scene_plan(), sample_only=True)

    validate_artifact("asset_manifest", manifest)
    assert len(FakeVideoSelector.calls) == 1
    assert manifest["metadata"]["sample_only"] is True
    assert manifest["metadata"]["generated_scene_count"] == 1
    assert manifest["metadata"]["total_scene_count"] == 2


def test_generate_assets_uses_veo_first_last_frame_chaining(monkeypatch, tmp_path):
    _wire_fakes(monkeypatch, tmp_path)
    project_dir = init_project("p", title="P", pipeline_type="cinematic", pipeline_dir=tmp_path)

    manifest = jobs._generate_assets("p", project_dir, _request("veo3.1"), _scene_plan(), sample_only=False)

    validate_artifact("asset_manifest", manifest)
    assert len(FakeVideoSelector.calls) == 2
    assert FakeVideoSelector.calls[0]["operation"] == "reference_to_video"
    assert FakeVideoSelector.calls[0]["preferred_provider"] == "veo"
    assert FakeVideoSelector.calls[1]["operation"] == "first_last_frame_to_video"
    assert FakeVideoSelector.calls[1]["first_frame_path"].endswith("assets/chaining/sc1_last.jpg")
    assert FakeVideoSelector.calls[1]["last_frame_url"] == "https://cdn.example/ref2.png"
    assert manifest["metadata"]["generation_runs"][1]["chaining_mode"] == "first_last_frame_to_video"
