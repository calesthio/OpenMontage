from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backlot import jobs
from hosted_pipeline.executor import StageRunResult
from lib.checkpoint import init_project, write_checkpoint


PROJECT_ID = "stage-executor-cutover"
REPO_SHA = "test-stage-executor-sha"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _research_brief() -> dict[str, Any]:
    sources = [
        {"url": f"https://example.com/source-{idx}", "title": f"Source {idx}", "used_for": "fixture", "reliability": "secondary"}
        for idx in range(1, 6)
    ]
    return {
        "version": "1.0",
        "topic": "Warli heritage saree",
        "research_date": "2026-07-10",
        "landscape": {
            "existing_content": [
                {"title": f"Reference {idx}", "source": "fixture", "angle": "product fidelity", "what_it_covers": "Warli motif detail"}
                for idx in range(1, 4)
            ],
            "saturated_angles": ["generic fashion reel"],
            "underserved_gaps": ["reference-faithful motif detail"],
        },
        "data_points": [
            {"claim": f"Fixture claim {idx}", "source_url": sources[idx - 1]["url"], "credibility": "secondary_source"}
            for idx in range(1, 4)
        ],
        "audience_insights": {
            "common_questions": ["What is the motif?", "How does the pallu move?", "Can I see the real product?"],
            "misconceptions": [{"myth": "Any ethnic pattern is close enough.", "reality": "Warli figures must stay legible."}],
            "knowledge_level": "Style-aware social buyers.",
        },
        "angles_discovered": [
            {"name": f"Angle {idx}", "hook": "Open on the Warli print.", "type": "narrative", "why_now": "Reference-led product video.", "grounded_in": ["fixture"]}
            for idx in range(1, 4)
        ],
        "sources": sources,
        "metadata": {"executor": "hosted_stage_executor", "repo_sha": REPO_SHA},
    }


def _proposal_packet() -> dict[str, Any]:
    concepts = []
    for idx in range(1, 4):
        concepts.append({
            "id": f"c{idx}",
            "title": f"Warli saree concept {idx}",
            "hook": "Start on the real Warli motif.",
            "narrative_structure": "story",
            "visual_approach": "Reference-faithful product film with stable fabric and model continuity.",
            "suggested_playbook": "clean-professional",
            "target_audience": "Premium saree buyers",
            "target_platform": "instagram",
            "target_duration_seconds": 30,
            "key_points": ["Use uploaded references.", "Keep motifs legible."],
            "core_message": "The saree is handcrafted and product-faithful.",
            "cta": "Enquire now",
            "tone": "premium, cinematic",
            "grounded_in": ["research_brief"],
            "why_this_works": "It prioritizes the real product over invented patterns.",
        })
    return {
        "version": "1.0",
        "concept_options": concepts,
        "selected_concept": {"concept_id": "c1", "rationale": "Best reference-fidelity route."},
        "production_plan": {
            "pipeline": "cinematic",
            "playbook": "clean-professional",
            "stages": [
                {"stage": "proposal", "tools": [], "approach": "Review the plan before paid media generation."},
                {"stage": "assets", "tools": [{"tool_name": "video_selector", "role": "Choose video provider", "available": True}], "approach": "Generate only after approval."},
            ],
            "render_runtime": "remotion",
            "renderer_family": "cinematic-trailer",
            "delivery_promise": {
                "promise_type": "motion_led",
                "motion_required": True,
                "source_required": True,
                "tone_mode": "cinematic",
                "quality_floor": "presentable",
                "approved_fallback": None,
            },
            "quality_tradeoffs": [{"tradeoff": "Sample-first limits spend.", "recommendation": "Approve the sample before batch."}],
            "alternative_paths": [{"description": "Plan only", "total_cost_usd": 0, "quality_level": "free"}],
            "music_source": {"source_type": "ai_generated", "provider": "music_gen", "estimated_cost_usd": 0, "mood_direction": "quiet premium textile ad"},
        },
        "cost_estimate": {"total_estimated_usd": 0.0, "line_items": [], "budget_verdict": "within_budget"},
        "approval": {"status": "pending"},
        "metadata": {"executor": "hosted_stage_executor", "repo_sha": REPO_SHA},
    }


def _script() -> dict[str, Any]:
    return {
        "version": "1.0",
        "title": "Warli Heritage Saree",
        "total_duration_seconds": 30,
        "sections": [
            {"id": "s1", "text": "A story woven in ivory and ochre.", "start_seconds": 0, "end_seconds": 10},
            {"id": "s2", "text": "Every motif carries a handmade rhythm.", "start_seconds": 10, "end_seconds": 20},
            {"id": "s3", "text": "Handcrafted. Heirloom. Yours.", "start_seconds": 20, "end_seconds": 30},
        ],
        "metadata": {"executor": "hosted_stage_executor", "repo_sha": REPO_SHA},
    }


def _scene_plan() -> dict[str, Any]:
    return {
        "version": "1.0",
        "style_playbook": "clean-professional",
        "scenes": [
            {
                "id": f"scene{idx}",
                "type": "generated",
                "description": f"Reference-faithful Warli saree scene {idx}",
                "start_seconds": (idx - 1) * 10,
                "end_seconds": idx * 10,
                "script_section_id": f"s{idx}",
                "required_assets": [{"type": "video", "description": "Use the uploaded saree references.", "source": "generate"}],
                "shot_intent": "Keep the real motif and pallu detail visible.",
                "narrative_role": "deliver_payload",
                "sequence_index": idx,
                "hero_moment": idx == 2,
            }
            for idx in range(1, 4)
        ],
        "metadata": {"executor": "hosted_stage_executor", "repo_sha": REPO_SHA},
    }


class FakeStageExecutor:
    calls: list[Any] = []

    def __init__(self, *, projects_dir: Path, model_client: Any) -> None:
        self.projects_dir = projects_dir
        self.model_client = model_client

    def run_stage(self, request: Any) -> StageRunResult:
        self.calls.append(request)
        artifacts = {
            "research": ("research_brief", _research_brief(), "completed", False),
            "proposal": ("proposal_packet", _proposal_packet(), "awaiting_human", False),
            "script": ("script", _script(), "completed", True),
            "scene_plan": ("scene_plan", _scene_plan(), "completed", True),
        }
        artifact_name, artifact, status, approved = artifacts[request.stage]
        project_dir = self.projects_dir / request.project_id
        _write_json(project_dir / "artifacts" / f"{artifact_name}.json", artifact)
        if request.stage == "proposal":
            _write_json(project_dir / "artifacts" / "decision_log.json", {
                "version": "1.0",
                "project_id": request.project_id,
                "decisions": [{
                    "decision_id": "d-provider",
                    "stage": "proposal",
                    "category": "provider_selection",
                    "subject": "Video provider",
                    "options_considered": [{"option_id": "kling-v3", "label": "Kling 3", "score": 1, "reason": "Fixture."}],
                    "selected": "kling-v3",
                    "reason": "Fixture selection.",
                    "user_visible": True,
                    "user_approved": False,
                    "confidence": 0.8,
                }],
            })
        _write_json(project_dir / "artifacts" / "cost_log.json", {
            "version": "1.0",
            "budget_total_usd": 5.0,
            "budget_spent_usd": 0.012,
            "budget_reserved_usd": 0.0,
            "entries": [{
                "id": f"cost-{request.stage}",
                "tool": "director_llm",
                "operation": request.stage,
                "status": "completed",
                "timestamp": "2026-07-10T00:00:00+00:00",
                "estimated_usd": 0.003,
                "actual_usd": 0.003,
                "details": json.dumps({"category": "llm", "stage": request.stage}),
            }],
        })
        checkpoint_path = write_checkpoint(
            self.projects_dir,
            request.project_id,
            request.stage,
            status,
            {artifact_name: artifact},
            pipeline_type=request.pipeline_type,
            human_approved=approved,
            cost_snapshot={
                "budget_caps": request.budget_caps.__dict__,
                "spent_usd": 0.003,
                "reserved_usd": 0.0,
                "total_active_usd": 0.003,
                "entries": 1,
            },
            metadata={"executor": "hosted_stage_executor", "repo_sha": REPO_SHA},
        )
        return StageRunResult(
            project_id=request.project_id,
            pipeline_type=request.pipeline_type,
            stage=request.stage,
            status=status,
            checkpoint_path=checkpoint_path,
            repo_sha=REPO_SHA,
            artifact_name=artifact_name,
        )


class FakeCostTool:
    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.1


def _job_request() -> dict[str, Any]:
    return {
        "version": "1.0",
        "project_id": PROJECT_ID,
        "title": "Warli Saree MCP Cutover",
        "prompt": "Create a 30s vertical ad faithful to attached reference stills.",
        "aspect_ratio": "9:16",
        "duration_seconds": 30,
        "scene_count": 3,
        "video_model": "kling-v3",
        "video_model_label": "Kling 3",
        "video_provider": "kling",
        "model_variant": "v3/standard",
        "max_scene_seconds": 10,
        "budget_cap_usd": 5.0,
        "reference_assets": [
            {"url": "https://cdn.ikawn.in/ref1.png", "filename": "ref1.png", "content_type": "image/png"},
            {"url": "https://cdn.ikawn.in/ref2.png", "filename": "ref2.png", "content_type": "image/png"},
        ],
    }


def test_plan_job_uses_stage_executor_bundle(monkeypatch, tmp_path):
    FakeStageExecutor.calls = []
    monkeypatch.setattr(jobs, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(jobs, "StageExecutor", FakeStageExecutor)
    monkeypatch.setattr(jobs.ChatCompletionsDirectorClient, "from_env", staticmethod(lambda: object()))
    monkeypatch.setattr(jobs, "_video_tool", lambda model_config: FakeCostTool())

    init_project(PROJECT_ID, title="Warli Saree MCP Cutover", pipeline_type="cinematic", pipeline_dir=tmp_path)
    _write_json(tmp_path / PROJECT_ID / "artifacts" / "job_request.json", _job_request())

    result = jobs.plan_job(PROJECT_ID, force=True)

    assert result["ok"] is True
    assert result["planning_executor"] == "hosted_stage_executor"
    assert [call.stage for call in FakeStageExecutor.calls] == ["research", "proposal", "script", "scene_plan"]
    assert [call.preapprove_human_gates for call in FakeStageExecutor.calls] == [False, False, True, True]

    for stage in ("research", "proposal", "script", "scene_plan"):
        checkpoint = json.loads((tmp_path / PROJECT_ID / f"checkpoint_{stage}.json").read_text())
        assert checkpoint["metadata"]["executor"] == "hosted_stage_executor"
        assert checkpoint["metadata"]["repo_sha"] == REPO_SHA
        assert checkpoint["cost_snapshot"]["spent_usd"] == 0.003

    proposal_checkpoint = json.loads((tmp_path / PROJECT_ID / "checkpoint_proposal.json").read_text())
    assert proposal_checkpoint["status"] == "awaiting_human"
    assert proposal_checkpoint["artifacts"]["proposal_packet"]["metadata"]["planning_executor"] == "hosted_stage_executor"
    assert proposal_checkpoint["artifacts"]["proposal_packet"]["metadata"]["orchestration_cost_log"] == "artifacts/cost_log.json"
    assert proposal_checkpoint["artifacts"]["proposal_packet"]["conditioning_mode"] == "image_to_video"
    assert proposal_checkpoint["artifacts"]["proposal_packet"]["reference_asset_count"] == 2
    assert (tmp_path / PROJECT_ID / "artifacts" / "cost_log.json").is_file()


def test_legacy_prompt_planner_symbol_is_absent():
    forbidden = "_plan" + "_with_llm"
    assert forbidden not in Path(jobs.__file__).read_text(encoding="utf-8")
