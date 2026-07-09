from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hosted_pipeline.executor import BudgetCaps, StageExecutor, StageRunRequest
from lib.checkpoint import init_project
from tools.base_tool import BaseTool, ToolResult, ToolRuntime
from tools.tool_registry import registry


class FakeDirector:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls = 0
        self.messages: list[dict[str, str]] = []
        self.tools: list[dict[str, Any]] = []

    def step(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        self.calls += 1
        self.messages = messages
        self.tools = tools
        return self.responses.pop(0)


def valid_research_brief() -> dict[str, Any]:
    sources = [
        {"url": f"https://example.com/source-{idx}", "title": f"Source {idx}", "used_for": "fixture", "reliability": "secondary"}
        for idx in range(1, 6)
    ]
    return {
        "version": "1.0",
        "topic": "Warli heritage saree",
        "research_date": "2026-07-09",
        "landscape": {
            "existing_content": [
                {"title": f"Reference {idx}", "source": "fixture", "angle": "craft", "what_it_covers": "textile detail"}
                for idx in range(1, 4)
            ],
            "saturated_angles": ["generic luxury closeups"],
            "underserved_gaps": ["craft motifs as cultural memory"],
        },
        "data_points": [
            {"claim": f"Fixture claim {idx}", "source_url": sources[idx - 1]["url"], "credibility": "secondary_source"}
            for idx in range(1, 4)
        ],
        "audience_insights": {
            "common_questions": ["How is it made?", "What motifs are shown?", "How should it be styled?"],
            "misconceptions": [{"myth": "All motifs are printed", "reality": "Some pieces include hand-led detail"}],
            "knowledge_level": "Style-aware buyers with limited craft context.",
        },
        "angles_discovered": [
            {"name": f"Craft angle {idx}", "hook": "A saree can carry a whole village memory.", "type": "narrative", "why_now": "Heritage-led fashion is visible.", "grounded_in": ["fixture"]}
            for idx in range(1, 4)
        ],
        "sources": sources,
        "research_summary": "A premium saree film should anchor product truth in craft detail and quiet studio-grade motion.",
        "metadata": {"research_execution_mode": "recorded_only_no_web_search_tool"},
    }


def valid_script() -> dict[str, Any]:
    return {
        "version": "1.0",
        "title": "Warli Heritage Saree",
        "total_duration_seconds": 30,
        "sections": [
            {"id": "s1", "text": "A story woven in ivory and ochre.", "start_seconds": 0, "end_seconds": 8},
            {"id": "s2", "text": "Motifs move like memory across the border.", "start_seconds": 8, "end_seconds": 20},
            {"id": "s3", "text": "Handcrafted. Heirloom. Yours.", "start_seconds": 20, "end_seconds": 30},
        ],
    }


def response_for(name: str, artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "final_artifact",
        "artifact_name": name,
        "artifact": artifact,
        "review": {"decision": "PASS", "findings": [], "summary": "Fixture passed."},
    }


def executor(tmp_path: Path, director: FakeDirector) -> StageExecutor:
    return StageExecutor(projects_dir=tmp_path, model_client=director)


def test_final_artifact_is_checkpointed_and_written(tmp_path, monkeypatch):
    monkeypatch.setattr(StageExecutor, "_provider_menu_summary", staticmethod(lambda: {}))
    director = FakeDirector([response_for("research_brief", valid_research_brief())])
    result = executor(tmp_path, director).run_stage(StageRunRequest(
        project_id="p",
        title="P",
        pipeline_type="cinematic",
        stage="research",
        brief="Warli saree ad",
    ))

    assert result.status == "completed"
    checkpoint = json.loads((tmp_path / "p" / "checkpoint_research.json").read_text())
    assert checkpoint["status"] == "completed"
    assert checkpoint["artifacts"]["research_brief"]["version"] == "1.0"
    assert (tmp_path / "p" / "artifacts" / "research_brief.json").is_file()


def test_research_context_uses_registered_web_search(tmp_path, monkeypatch):
    monkeypatch.setattr(StageExecutor, "_provider_menu_summary", staticmethod(lambda: {}))
    director = FakeDirector([response_for("research_brief", valid_research_brief())])

    result = executor(tmp_path, director).run_stage(StageRunRequest(
        project_id="p",
        title="P",
        pipeline_type="cinematic",
        stage="research",
        brief="Warli saree ad",
    ))

    assert result.status == "completed"
    context = json.loads(director.messages[1]["content"])
    assert context["execution_constraints"]["research_execution_mode"] == "web_search"
    assert any(tool["name"] == "web_search" for tool in director.tools)


def test_budget_blocks_before_director_call_and_writes_failed_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(StageExecutor, "_provider_menu_summary", staticmethod(lambda: {}))
    director = FakeDirector([response_for("research_brief", valid_research_brief())])
    result = executor(tmp_path, director).run_stage(StageRunRequest(
        project_id="p",
        title="P",
        pipeline_type="cinematic",
        stage="research",
        brief="x" * 2000,
        budget_caps=BudgetCaps(total_budget_cap_usd=0.0, llm_budget_cap_usd=0.0, media_budget_cap_usd=0.0),
    ))

    assert director.calls == 0
    assert result.status == "blocked"
    assert result.blocker == "budget_cap_exceeded"
    checkpoint = json.loads((tmp_path / "p" / "checkpoint_research.json").read_text())
    assert checkpoint["status"] == "failed"
    assert checkpoint["metadata"]["blocker"] == "budget_cap_exceeded"


def test_schema_repair_loop_then_gated_preapproval(tmp_path, monkeypatch):
    monkeypatch.setattr(StageExecutor, "_provider_menu_summary", staticmethod(lambda: {}))
    director = FakeDirector([
        response_for("script", {"version": "1.0"}),
        response_for("script", valid_script()),
    ])
    result = executor(tmp_path, director).run_stage(StageRunRequest(
        project_id="p",
        title="P",
        pipeline_type="cinematic",
        stage="script",
        brief="Warli saree ad",
        preapprove_human_gates=True,
        approval_note="test preapproval",
    ))

    assert director.calls == 2
    assert result.status == "completed"
    checkpoint = json.loads((tmp_path / "p" / "checkpoint_script.json").read_text())
    assert checkpoint["status"] == "completed"
    assert checkpoint["human_approved"] is True
    history = list((tmp_path / "p" / "history").glob("checkpoint_script_*.json"))
    assert history
    assert json.loads(history[0].read_text())["status"] == "awaiting_human"


def test_tool_idempotency_returns_cached_result(tmp_path):
    class PaidDummyTool(BaseTool):
        name = "test_paid_dummy"
        runtime = ToolRuntime.API
        calls = 0

        def estimate_cost(self, inputs: dict[str, Any]) -> float:
            return 0.25

        def execute(self, inputs: dict[str, Any]) -> ToolResult:
            type(self).calls += 1
            return ToolResult(success=True, data={"call": type(self).calls}, cost_usd=0.25)

    registry.register(PaidDummyTool())
    init_project("p", title="P", pipeline_type="cinematic", pipeline_dir=tmp_path)
    runner = StageExecutor(projects_dir=tmp_path, model_client=FakeDirector([]))
    request = StageRunRequest(
        project_id="p",
        title="P",
        pipeline_type="cinematic",
        stage="assets",
        budget_caps=BudgetCaps(total_budget_cap_usd=1.0, media_budget_cap_usd=1.0),
    )

    first = runner._execute_tool_call(request=request, stage="assets", tool_name="test_paid_dummy", arguments={"scene_id": "s1"})
    second = runner._execute_tool_call(request=request, stage="assets", tool_name="test_paid_dummy", arguments={"scene_id": "s1"})

    assert first["data"]["call"] == 1
    assert second["data"]["call"] == 1
    assert second["cached_from_idempotency"] is True
    assert PaidDummyTool.calls == 1
