from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.base_tool import ToolResult

from backlot import jobs
from lib.checkpoint import init_project
from schemas.artifacts import validate_artifact


def _request(video_model: str = "grok-imagine-video") -> dict[str, Any]:
    model_variant = "grok-imagine-video"
    if video_model == "veo3.1":
        model_variant = "veo3.1"
    elif video_model == "kling-v3":
        model_variant = "v3/standard"
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
        "model_variant": model_variant,
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
    monkeypatch.setattr(
        jobs,
        "_qa_video_clip",
        lambda path, duration, **kwargs: {"warnings": [], "duration_ok": True, "dimensions_ok": True},
    )
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


def test_generate_assets_blocks_before_selector_when_budget_cap_exceeded(monkeypatch, tmp_path):
    _wire_fakes(monkeypatch, tmp_path)
    project_dir = init_project("p", title="P", pipeline_type="cinematic", pipeline_dir=tmp_path)

    class FakeCostTool:
        def estimate_cost(self, inputs: dict[str, Any]) -> float:
            return 0.12

    monkeypatch.setattr(jobs, "_video_tool", lambda model_config: FakeCostTool())
    request = _request()
    request["budget_cap_usd"] = 0.05

    with pytest.raises(jobs.JobError, match="Budget cap would be exceeded"):
        jobs._generate_assets("p", project_dir, request, _scene_plan(), sample_only=True)

    assert FakeVideoSelector.calls == []


def test_generate_assets_prepares_kling_reference_frame_to_plan_aspect(monkeypatch, tmp_path):
    _wire_fakes(monkeypatch, tmp_path)
    project_dir = init_project("p", title="P", pipeline_type="cinematic", pipeline_dir=tmp_path)

    def fake_prepare(project_dir: Path, scene_id: str, image_url: str, aspect_ratio: str) -> Path:
        prepared = project_dir / "assets" / "references" / f"{scene_id}_prepared.png"
        prepared.parent.mkdir(parents=True, exist_ok=True)
        prepared.write_bytes(b"prepared-reference")
        return prepared

    monkeypatch.setattr(jobs, "_prepare_kling_reference_frame", fake_prepare)

    manifest = jobs._generate_assets("p", project_dir, _request("kling-v3"), _scene_plan(), sample_only=True)

    validate_artifact("asset_manifest", manifest)
    assert len(FakeVideoSelector.calls) == 1
    call = FakeVideoSelector.calls[0]
    assert call["preferred_provider"] == "kling"
    assert call["operation"] == "image_to_video"
    assert call["aspect_ratio"] == "9:16"
    assert "image_url" not in call
    assert call["reference_image_path"].endswith("assets/references/sc1_prepared.png")
    assert call["reference_frame_preprocess"]["target_aspect_ratio"] == "9:16"
    assert call["reference_frame_preprocess"]["source_url"] == "https://cdn.example/ref1.png"
    assert call["cfg_scale"] == 0.75
    assert call["elements"][0]["frontal_image_url"] == "https://cdn.example/ref1.png"
    assert manifest["metadata"]["generation_runs"][0]["reference_frame_preprocess"]["version"] == "kling-start-frame-crop-fill-v2"
    assert manifest["metadata"]["generation_runs"][0]["reference_frame_preprocess"]["strategy"] == "crop-to-fill-reference"


def test_kling_reference_preprocess_compatibility_reuses_approved_padded_sample(tmp_path):
    video = tmp_path / "scene1.mp4"
    video.write_bytes(b"approved-sample")
    signature = {
        "video_model": "kling-v3",
        "reference_frame_preprocess_version": "kling-start-frame-crop-fill-v2",
    }
    video.with_suffix(".mp4.json").write_text(
        json.dumps({
            "video_model": "kling-v3",
            "reference_frame_preprocess_version": "kling-start-frame-aspect-pad-v1",
        }),
        encoding="utf-8",
    )

    assert jobs._clip_metadata_matches(video, signature) is True


def test_post_edit_plan_can_trim_padded_first_scene_start():
    assets = [
        {"id": "scene1", "type": "video", "duration_seconds": 6, "prompt": "macro textile"},
        {"id": "scene2", "type": "video", "duration_seconds": 6, "prompt": "motion"},
    ]

    edit_plan = jobs._post_edit_plan(
        assets,
        12,
        {"compose_requirements": {"trim_first_scene_start_seconds": 1.0}},
    )

    assert edit_plan["segments"][0]["source_start_seconds"] == 1.0
    assert edit_plan["segments"][0]["trim_seconds"] <= 5.0
    assert edit_plan["segments"][1]["source_start_seconds"] == 0.0


def test_compose_uses_real_composer_music_and_end_card(monkeypatch, tmp_path):
    from tools.audio import audio_mixer, music_gen
    from tools.video import video_compose

    project_id = "compose-p"
    project_dir = tmp_path / project_id
    (project_dir / "assets" / "video").mkdir(parents=True)
    for idx in range(1, 4):
        (project_dir / "assets" / "video" / f"scene{idx}.mp4").write_bytes(b"video")

    music_calls: list[dict[str, Any]] = []
    mixer_calls: list[dict[str, Any]] = []
    composer_calls: list[dict[str, Any]] = []

    class FakeMusicGen:
        def estimate_cost(self, inputs: dict[str, Any]) -> float:
            return 0.05

        def execute(self, inputs: dict[str, Any]) -> ToolResult:
            music_calls.append(inputs)
            path = Path(inputs["output_path"])
            path.write_bytes(b"music")
            return ToolResult(success=True, data={"output": str(path)}, artifacts=[str(path)], cost_usd=0.05)

    class FakeAudioMixer:
        def execute(self, inputs: dict[str, Any]) -> ToolResult:
            mixer_calls.append(inputs)
            path = Path(inputs["output_path"])
            path.write_bytes(b"normalized")
            return ToolResult(success=True, data={"output": str(path)}, artifacts=[str(path)])

    class FakeVideoCompose:
        def execute(self, inputs: dict[str, Any]) -> ToolResult:
            composer_calls.append(inputs)
            path = Path(inputs["output_path"])
            path.write_bytes(b"rendered")
            return ToolResult(success=True, data={"operation": "remotion_render", "output": str(path)}, artifacts=[str(path)])

    monkeypatch.setattr(jobs, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(music_gen, "MusicGen", FakeMusicGen)
    monkeypatch.setattr(audio_mixer, "AudioMixer", FakeAudioMixer)
    monkeypatch.setattr(video_compose, "VideoCompose", FakeVideoCompose)
    monkeypatch.setattr(jobs, "_loudness_normalize_final", lambda src, dst: Path(dst).write_bytes(Path(src).read_bytes()))
    monkeypatch.setattr(
        jobs,
        "_render_qa",
        lambda final, planned: {
            "duration_seconds": float(planned),
            "planned_duration_seconds": float(planned),
            "audio": {"effectively_silent": False},
            "warnings": [],
        },
    )
    uploads: list[tuple[str, str]] = []
    monkeypatch.setattr(
        jobs.storage,
        "upload_file",
        lambda path, pid, rel: uploads.append((pid, rel)) or {
            "bucket": "ikawn-v1",
            "key": f"{pid}/{rel}",
            "url": f"https://cdn.example/{pid}/{rel}",
        },
    )

    request = _request("kling-v3")
    request.update({
        "project_id": project_id,
        "duration_seconds": 30,
        "budget_cap_usd": 5.0,
        "compose_requirements": {"trim_first_scene_start_seconds": 1.0},
    })
    manifest = {
        "version": "1.0",
        "total_cost_usd": 0.6,
        "assets": [
            {"id": f"vid_scene{idx}", "type": "video", "scene_id": f"scene{idx}", "path": f"assets/video/scene{idx}.mp4", "duration_seconds": 10.0}
            for idx in range(1, 4)
        ],
        "metadata": {
            "r2_assets": [
                {"path": f"assets/video/scene{idx}.mp4", "url": f"https://cdn.example/{project_id}/assets/video/scene{idx}.mp4"}
                for idx in range(1, 4)
            ]
        },
    }

    edit_decisions, render_report = jobs._compose(project_id, project_dir, manifest, request, _scene_plan())

    assert music_calls and music_calls[0]["duration_seconds"] >= 30
    assert mixer_calls and mixer_calls[0]["operation"] == "mix"
    assert composer_calls and composer_calls[0]["operation"] == "remotion_render"
    assert composer_calls[0]["profile"] == "youtube_shorts"
    props = composer_calls[0]["edit_decisions"]
    assert props["render_runtime"] == "remotion"
    assert props["composition_mode"] == "templated"
    assert props["music"]["src"] == f"https://cdn.example/{project_id}/renders/music_normalized.wav"
    assert props["scenes"][0]["src"] == f"https://cdn.example/{project_id}/assets/video/scene1.mp4"
    assert props["scenes"][0]["trimBeforeSeconds"] == 1.0
    assert props["scenes"][-1]["id"] == "end_card"
    assert props["scenes"][-1]["kind"] == "title"
    assert edit_decisions["render_runtime"] == "remotion"
    assert edit_decisions["composition_mode"] == "templated"
    assert edit_decisions["metadata"]["composer_tool"] == "video_compose"
    assert edit_decisions["metadata"]["renderer_component"] == "CinematicRenderer"
    assert edit_decisions["metadata"]["native_clip_audio"] == "replaced_by_continuous_music_bed"
    assert render_report["metadata"]["composer_tool"] == "video_compose"
    assert render_report["metadata"]["post_pipeline"]["loudness_target_lufs"] == -14
    assert (project_id, "renders/final.mp4") in uploads
    assert (project_id, "renders/music_normalized.wav") in uploads


def test_approve_asset_review_retries_compose_after_provider_failure(monkeypatch, tmp_path):
    project_id = "approved-compose-retry"
    project_dir = init_project(project_id, title="Retry", pipeline_type="cinematic", pipeline_dir=tmp_path)
    monkeypatch.setattr(jobs, "PROJECTS_DIR", tmp_path)

    request = _request("kling-v3")
    request["project_id"] = project_id
    scene_plan = _scene_plan()
    manifest = {
        "version": "1.0",
        "total_cost_usd": 0.24,
        "assets": [
            {"id": "vid_sc1", "type": "video", "scene_id": "sc1", "path": "assets/video/sc1.mp4", "duration_seconds": 6.0},
            {"id": "vid_sc2", "type": "video", "scene_id": "sc2", "path": "assets/video/sc2.mp4", "duration_seconds": 6.0},
        ],
        "metadata": {
            "reference_fidelity_review": {
                "status": "approved",
                "approved_at": "2026-07-10T00:00:00+00:00",
            },
        },
    }
    jobs._write_json(project_dir / "artifacts" / "job_request.json", request)
    jobs._write_json(project_dir / "artifacts" / "scene_plan.json", scene_plan)
    jobs._write_json(project_dir / "artifacts" / "asset_manifest.json", manifest)

    compose_calls: list[tuple[str, Path]] = []

    def fake_compose(pid: str, pdir: Path, asset_manifest: dict[str, Any], request_data: dict[str, Any], plan: dict[str, Any]):
        compose_calls.append((pid, pdir))
        return (
            {
                "version": "1.0",
                "render_runtime": "remotion",
                "cuts": [{"id": "cut_1", "source": "vid_sc1", "in_seconds": 0, "out_seconds": 6}],
            },
            {
                "version": "1.0",
                "outputs": [{
                    "path": "renders/final.mp4",
                    "format": "mp4",
                    "resolution": "1080x1920",
                    "duration_seconds": 12.0,
                }],
            },
        )

    monkeypatch.setattr(jobs, "_compose", fake_compose)

    result = jobs.approve_asset_review(project_id)

    assert result == {"ok": True, "project_id": project_id, "status": "completed"}
    assert compose_calls == [(project_id, project_dir)]
    assert (project_dir / "artifacts" / "render_report.json").is_file()


def test_generate_assets_blocks_dimension_mismatch_before_manifest_acceptance(monkeypatch, tmp_path):
    _wire_fakes(monkeypatch, tmp_path)
    project_dir = init_project("p", title="P", pipeline_type="cinematic", pipeline_dir=tmp_path)
    uploads: list[tuple[str, str]] = []

    monkeypatch.setattr(
        jobs.storage,
        "upload_file",
        lambda path, project_id, rel: uploads.append((project_id, rel)) or {
            "key": f"{project_id}/{rel}",
            "url": f"https://cdn.example/{project_id}/{rel}",
        },
    )
    monkeypatch.setattr(
        jobs,
        "_qa_video_clip",
        lambda path, duration, **kwargs: {
            "warnings": ["dimensions_vs_plan_mismatch"],
            "duration_ok": True,
            "dimensions_ok": False,
            "width": 856,
            "height": 1072,
            "expected_aspect_ratio": kwargs.get("expected_aspect_ratio"),
            "actual_aspect_ratio": 0.798507,
            "aspect_ratio_delta": 0.236007,
        },
    )

    with pytest.raises(jobs.JobAwaitingHuman, match="dimensions do not match"):
        jobs._generate_assets("p", project_dir, _request(), _scene_plan(), sample_only=True)

    manifest = jobs._read_json(project_dir / "artifacts" / "asset_manifest.json")
    assert manifest["metadata"]["blocked"] is True
    assert manifest["metadata"]["blocker"]["type"] == "asset_qa_dimension_mismatch"
    assert manifest["metadata"]["blocker"]["qa_checks"]["expected_aspect_ratio"] == "9:16"
    assert manifest["assets"] == []
    assert manifest["total_cost_usd"] == 0.12
    assert uploads == []
