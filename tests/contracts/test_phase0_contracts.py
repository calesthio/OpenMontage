"""Phase 0 contract tests — infrastructure layer.

Tests config, schemas, checkpoints, pipeline manifests, tools, cost tracker,
and media profiles. The intelligence layer (orchestrator, reviewer, checkpoint
policy, handlers) has been replaced by instruction-driven architecture:
pipeline manifests + stage director skills + meta skills.
"""

import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.config_model import OpenMontageConfig
from lib.checkpoint import (
    CheckpointValidationError,
    STAGES,
    get_next_stage,
    get_project_cost_tracker,
    read_checkpoint,
    write_checkpoint,
)
from lib.media_profiles import get_profile, ffmpeg_output_args, ALL_PROFILES
from lib.pipeline_loader import (
    get_required_tools,
    get_stage_order,
    get_stage_skill,
    get_stage_sub_stages,
    get_stage_review_focus,
    list_pipelines,
    load_pipeline,
    pipeline_supports_reference_input,
)
from tools.base_tool import BaseTool, ToolResult, ToolTier, ToolStatus
from tools.tool_registry import ToolRegistry
from tools.cost_tracker import CostTracker, BudgetMode, BudgetExceededError, ApprovalRequiredError
from schemas.artifacts import load_schema, validate_artifact, list_schemas


def sample_artifact(name: str) -> dict:
    """Return a minimal schema-valid artifact for tests."""
    if name == "research_brief":
        return {
            "version": "1.0",
            "topic": "Test Topic",
            "research_date": "2026-03-27",
            "landscape": {
                "existing_content": [
                    {"title": "Existing Video 1", "source": "youtube", "angle": "tutorial", "what_it_covers": "basics"},
                    {"title": "Existing Video 2", "source": "blog", "angle": "deep dive", "what_it_covers": "advanced"},
                    {"title": "Existing Video 3", "source": "youtube", "angle": "comparison", "what_it_covers": "alternatives"},
                ],
                "saturated_angles": ["basic tutorial"],
                "underserved_gaps": ["misconceptions about topic"],
            },
            "data_points": [
                {"claim": "73% of users prefer X", "source_url": "https://example.com/study", "credibility": "primary_source"},
                {"claim": "Market grew 40% in 2025", "source_url": "https://example.com/report", "credibility": "secondary_source"},
                {"claim": "Most experts agree on Y", "source_url": "https://example.com/survey", "credibility": "primary_source"},
            ],
            "audience_insights": {
                "common_questions": ["What is X?", "How does X work?", "Why is X important?"],
                "misconceptions": [{"myth": "X is slow", "reality": "X is fast"}],
                "knowledge_level": "Beginner to intermediate",
            },
            "angles_discovered": [
                {"name": "The Surprising Truth", "hook": "You think X is slow. It's not.", "type": "contrarian", "why_now": "New benchmark data", "grounded_in": ["data_point_1"]},
                {"name": "X From Scratch", "hook": "Build X in 5 minutes.", "type": "evergreen", "why_now": "Audience demand", "grounded_in": ["audience_q1"]},
                {"name": "Why X Matters Now", "hook": "X just changed everything.", "type": "trending", "why_now": "Recent announcement", "grounded_in": ["trending_1"]},
            ],
            "sources": [
                {"url": "https://example.com/study", "title": "Study on X", "used_for": "data_points"},
                {"url": "https://example.com/report", "title": "Market Report", "used_for": "data_points"},
                {"url": "https://example.com/survey", "title": "Expert Survey", "used_for": "data_points"},
                {"url": "https://example.com/reddit", "title": "Reddit Discussion", "used_for": "audience_insights"},
                {"url": "https://example.com/blog", "title": "Tech Blog", "used_for": "landscape"},
            ],
        }
    if name == "proposal_packet":
        return {
            "version": "1.0",
            "concept_options": [
                {
                    "id": "c1", "title": "The Surprising Truth About X", "hook": "You think X is slow.",
                    "narrative_structure": "myth_busting", "visual_approach": "animated diagrams",
                    "target_duration_seconds": 60, "why_this_works": "Strong misconception found in research",
                },
                {
                    "id": "c2", "title": "X From Scratch", "hook": "Build X in 5 minutes.",
                    "narrative_structure": "tutorial", "visual_approach": "code walkthrough",
                    "target_duration_seconds": 90, "why_this_works": "High demand in audience questions",
                },
                {
                    "id": "c3", "title": "Why X Matters Now", "hook": "X just changed everything.",
                    "narrative_structure": "timeline", "visual_approach": "motion graphics",
                    "target_duration_seconds": 75, "why_this_works": "Recent announcement creates timeliness",
                },
            ],
            "selected_concept": {"concept_id": "c1", "rationale": "Strongest research backing"},
            "production_plan": {
                "pipeline": "animated-explainer",
                "render_runtime": "remotion",
                "stages": [
                    {"stage": "script", "tools": [], "approach": "Write from research"},
                    {"stage": "assets", "tools": [{"tool_name": "tts_selector", "role": "narration", "available": True}], "approach": "Generate assets"},
                ],
            },
            "cost_estimate": {
                "total_estimated_usd": 0.52,
                "line_items": [{"tool": "elevenlabs_tts", "operation": "narration", "estimated_usd": 0.18}],
                "budget_verdict": "within_budget",
            },
            "approval": {"status": "approved"},
        }
    if name == "brief":
        return {
            "version": "1.0",
            "title": "Test Brief",
            "hook": "Did you know?",
            "key_points": ["point 1"],
            "tone": "casual",
            "style": "clean-professional",
            "target_platform": "youtube",
            "target_duration_seconds": 60,
        }
    if name == "script":
        return {
            "version": "1.0",
            "title": "Test Script",
            "total_duration_seconds": 60,
            "sections": [
                {
                    "id": "s1",
                    "text": "Hello world",
                    "start_seconds": 0,
                    "end_seconds": 10,
                }
            ],
        }
    if name == "scene_plan":
        return {
            "version": "1.0",
            "scenes": [
                {
                    "id": "scene-1",
                    "type": "talking_head",
                    "description": "Host on camera",
                    "start_seconds": 0,
                    "end_seconds": 10,
                }
            ],
        }
    if name == "asset_manifest":
        return {
            "version": "1.0",
            "assets": [
                {
                    "id": "asset-1",
                    "type": "video",
                    "path": "assets/clip.mp4",
                    "source_tool": "ffmpeg",
                    "scene_id": "scene-1",
                }
            ],
        }
    if name == "edit_decisions":
        return {
            "version": "1.0",
            "cuts": [
                {
                    "id": "cut-1",
                    "source": "asset-1",
                    "in_seconds": 0,
                    "out_seconds": 10,
                }
            ],
        }
    if name == "render_report":
        return {
            "version": "1.0",
            "outputs": [
                {
                    "path": "renders/output.mp4",
                    "format": "mp4",
                    "resolution": "1920x1080",
                    "duration_seconds": 60,
                }
            ],
        }
    if name == "publish_log":
        return {
            "version": "1.0",
            "entries": [
                {
                    "platform": "youtube",
                    "status": "draft",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }
    if name == "video_analysis_brief":
        return {
            "version": "1.0",
            "source": {
                "type": "youtube",
                "url": "https://example.com/watch?v=abc123def45",
                "title": "Reference Video",
                "duration_seconds": 60,
            },
            "content_analysis": {
                "summary": "A fast explainer reference.",
                "topics": ["quantum computing"],
                "target_audience": "general",
            },
            "structure_analysis": {
                "total_scenes": 3,
                "scenes": [
                    {
                        "scene_index": 0,
                        "start_time": 0,
                        "end_time": 5,
                        "description": "Hook",
                    },
                    {
                        "scene_index": 1,
                        "start_time": 5,
                        "end_time": 20,
                        "description": "Setup",
                    },
                    {
                        "scene_index": 2,
                        "start_time": 20,
                        "end_time": 60,
                        "description": "Payoff",
                    },
                ],
                "pacing_profile": {
                    "avg_scene_duration_seconds": 20,
                    "cuts_per_minute": 3,
                    "pacing_style": "steady_educational",
                },
            },
        }
    raise KeyError(f"Unknown artifact sample: {name}")


# ---- Config ----

class TestConfig:
    def test_load_defaults(self):
        config = OpenMontageConfig()
        assert config.llm.provider == "anthropic"
        assert config.budget.mode.value == "warn"
        assert config.checkpoint.policy.value == "guided"

    def test_load_from_yaml(self):
        config = OpenMontageConfig.load()
        assert config.budget.total_usd == 10.0


# ---- Schemas ----

class TestSchemas:
    def test_all_schemas_loadable(self):
        names = list_schemas()
        assert len(names) >= 7
        for name in names:
            schema = load_schema(name)
            assert "$schema" in schema

    def test_brief_validates(self):
        validate_artifact("brief", sample_artifact("brief"))

    def test_brief_rejects_invalid(self):
        with pytest.raises(Exception):
            validate_artifact("brief", {"version": "1.0"})

    def test_video_analysis_brief_validates(self):
        validate_artifact("video_analysis_brief", sample_artifact("video_analysis_brief"))


# ---- Checkpoint ----

class TestCheckpoint:
    def test_write_read_roundtrip(self, tmp_path):
        write_checkpoint(
            tmp_path, "test_project", "research", "completed",
            {"research_brief": sample_artifact("research_brief")},
        )
        cp = read_checkpoint(tmp_path, "test_project", "research")
        assert cp is not None
        assert cp["stage"] == "research"
        assert cp["status"] == "completed"
        assert cp["artifacts"]["research_brief"]["topic"] == "Test Topic"

    def test_get_next_stage(self, tmp_path):
        assert get_next_stage(tmp_path, "proj") == "research"
        write_checkpoint(
            tmp_path,
            "proj",
            "research",
            "completed",
            {"research_brief": sample_artifact("research_brief")},
        )
        assert get_next_stage(tmp_path, "proj") == "proposal"

    def test_invalid_stage_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            write_checkpoint(tmp_path, "proj", "invalid_stage", "completed", {})

    def test_invalid_canonical_artifact_rejected(self, tmp_path):
        with pytest.raises(CheckpointValidationError):
            write_checkpoint(
                tmp_path,
                "proj",
                "research",
                "completed",
                {"research_brief": {"topic": "missing schema fields"}},
            )

    def test_missing_canonical_artifact_rejected(self, tmp_path):
        with pytest.raises(CheckpointValidationError):
            write_checkpoint(tmp_path, "proj", "research", "completed", {})

    def test_invalid_status_rejected(self, tmp_path):
        with pytest.raises(CheckpointValidationError):
            write_checkpoint(
                tmp_path,
                "proj",
                "research",
                "mystery",
                {"research_brief": sample_artifact("research_brief")},
            )

    def test_supplementary_video_analysis_brief_is_validated(self, tmp_path):
        write_checkpoint(
            tmp_path,
            "proj",
            "proposal",
            "completed",
            {
                "proposal_packet": sample_artifact("proposal_packet"),
                "video_analysis_brief": sample_artifact("video_analysis_brief"),
            },
        )
        cp = read_checkpoint(tmp_path, "proj", "proposal")
        assert cp is not None
        assert "video_analysis_brief" in cp["artifacts"]


# ---- Pipeline manifests ----

class TestPipelineManifests:
    def test_framework_smoke_manifest_loads(self):
        manifest = load_pipeline("framework-smoke")
        assert manifest["name"] == "framework-smoke"
        assert get_stage_order(manifest) == ["research", "script"]
        assert get_required_tools(manifest) == set()

    def test_framework_smoke_manifest_listed(self):
        assert "framework-smoke" in list_pipelines()

    def test_reference_sub_stage_helpers(self):
        manifest = load_pipeline("animated-explainer")
        assert pipeline_supports_reference_input(manifest) is True
        assert "video_analyzer" in get_required_tools(manifest)

        all_units = get_stage_order(manifest, include_sub_stages=True)
        assert "proposal.sample" in all_units

        active_sub_stages = get_stage_sub_stages(
            manifest,
            "proposal",
            context={"video_analysis_brief_exists": True},
            include_inactive=False,
        )
        assert any(s["name"] == "sample" for s in active_sub_stages)


# ---- BaseTool ----

class DummyTool(BaseTool):
    name = "dummy"
    version = "0.1.0"
    tier = ToolTier.CORE
    capabilities = ["test"]
    dependencies = []

    def execute(self, inputs):
        return ToolResult(success=True, data={"echo": inputs})


class TestBaseTool:
    def test_get_info(self):
        tool = DummyTool()
        info = tool.get_info()
        assert info["name"] == "dummy"
        assert info["tier"] == "core"
        assert info["status"] == "available"

    def test_execute(self):
        tool = DummyTool()
        result = tool.execute({"msg": "hello"})
        assert result.success

    def test_unavailable_when_deps_missing(self):
        class MissingDepTool(BaseTool):
            name = "missing"
            dependencies = ["cmd:nonexistent_binary_xyz"]
            def execute(self, inputs):
                return ToolResult(success=True)

        tool = MissingDepTool()
        assert tool.get_status() == ToolStatus.UNAVAILABLE


# ---- ToolRegistry ----

class TestToolRegistry:
    def test_register_and_find(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        assert reg.get("dummy") is not None
        assert "dummy" in reg.list_all()
        assert len(reg.get_by_tier(ToolTier.CORE)) == 1
        assert len(reg.find_by_capability("test")) == 1

    def test_support_envelope(self):
        reg = ToolRegistry()
        reg.register(DummyTool())
        envelope = reg.support_envelope()
        assert "dummy" in envelope
        assert envelope["dummy"]["status"] == "available"

    def test_discovers_concrete_tools_from_package(self, tmp_path, monkeypatch):
        package_dir = tmp_path / "demo_tools"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "demo_tool.py").write_text(
            "\n".join(
                [
                    "from tools.base_tool import BaseTool, ToolResult, ToolTier",
                    "",
                    "class DiscoveredTool(BaseTool):",
                    "    name = 'discovered'",
                    "    tier = ToolTier.CORE",
                    "    capabilities = ['discover']",
                    "    dependencies = []",
                    "",
                    "    def execute(self, inputs):",
                    "        return ToolResult(success=True, data=inputs)",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        monkeypatch.syspath_prepend(str(tmp_path))
        importlib.invalidate_caches()

        reg = ToolRegistry()
        discovered = reg.discover("demo_tools")

        assert discovered == ["discovered"]
        assert reg.get("discovered") is not None
        assert reg.find_by_capability("discover")[0].name == "discovered"


# ---- CostTracker ----

class TestCostTracker:
    def test_estimate_reserve_reconcile(self):
        tracker = CostTracker(budget_total_usd=10.0, mode=BudgetMode.OBSERVE)
        entry_id = tracker.estimate("image_selector", "generate", 0.05)
        tracker.reserve(entry_id)
        assert tracker.budget_reserved_usd == 0.05
        tracker.reconcile(entry_id, 0.04, success=True)
        assert tracker.budget_spent_usd == 0.04
        assert tracker.budget_reserved_usd == 0.0

    def test_cap_mode_blocks_overspend(self):
        tracker = CostTracker(
            budget_total_usd=1.0,
            mode=BudgetMode.CAP,
            single_action_approval_usd=10.0,  # raise threshold so budget check triggers
        )
        tracker.approve_tool("expensive")
        eid = tracker.estimate("expensive", "op", 5.0)
        with pytest.raises(BudgetExceededError):
            tracker.reserve(eid)

    def test_persistence(self, tmp_path):
        log_path = tmp_path / "cost_log.json"
        t1 = CostTracker(budget_total_usd=10.0, mode=BudgetMode.OBSERVE, cost_log_path=log_path)
        eid = t1.estimate("tool", "op", 0.10)
        t1.reserve(eid)
        t1.reconcile(eid, 0.08)

        t2 = CostTracker(cost_log_path=log_path)
        assert t2.budget_spent_usd == 0.08

    def test_reference_estimate_falls_back_when_scene_types_are_unclassified(self):
        tracker = CostTracker(mode=BudgetMode.OBSERVE)
        brief = {
            "source": {"type": "shorts", "duration_seconds": 60},
            "structure_analysis": {
                "total_scenes": 12,
                "pacing_profile": {"pacing_style": "rapid_fire"},
                "scenes": [{"visual_type": "other"} for _ in range(12)],
            },
            "narration_transcript": {"word_count": 180},
            "replication_guidance": {"motion_required": True, "suggested_pipeline": "animation"},
        }
        plan = {
            "video_generation": {"tool": "kling_fal", "cost_per_unit": 0.3, "clip_duration_seconds": 5},
            "image_generation": {"tool": "flux_fal", "cost_per_unit": 0.05},
            "tts": {"tool": "elevenlabs_tts", "cost_per_word": 0.00003},
            "music": {"tool": "music_gen", "cost_per_track": 0.1},
        }

        estimate = tracker.estimate_from_reference(brief, 60, plan)

        assert estimate["motion_ratio"] >= 0.6
        assert estimate["estimated_clips"] >= 7
        assert any(
            "scene visual types have not been enriched yet" in note
            for note in estimate["assumptions"]
        )


# ---- Project Cost Tracker (wired to project cost_log.json) ----

class TestProjectCostTracker:
    def test_factory_sets_project_cost_log_path(self, tmp_path):
        tracker = get_project_cost_tracker(tmp_path, "proj_a")
        assert tracker.cost_log_path == tmp_path / "proj_a" / "cost_log.json"

    def test_factory_persists_cost_log_on_first_operation(self, tmp_path):
        tracker = get_project_cost_tracker(tmp_path, "proj_b")
        tracker.approve_tool("image_selector")
        eid = tracker.estimate("image_selector", "generate", 0.10)
        tracker.reserve(eid)
        tracker.reconcile(eid, 0.08, success=True)
        assert (tmp_path / "proj_b" / "cost_log.json").exists()

    def test_factory_tracks_failed_paid_attempts(self, tmp_path):
        tracker = get_project_cost_tracker(tmp_path, "proj_c")
        tracker.approve_tool("kling_fal")
        eid = tracker.estimate("kling_fal", "video_generate", 0.30)
        tracker.reserve(eid)
        tracker.reconcile(eid, 0.30, success=False)
        assert tracker.budget_spent_usd == 0.30
        log = json.loads((tmp_path / "proj_c" / "cost_log.json").read_text())
        assert any(e["status"] == "failed" for e in log["entries"])

    def test_factory_reloads_prior_entries_across_stages(self, tmp_path):
        t1 = get_project_cost_tracker(tmp_path, "proj_d")
        t1.approve_tool("elevenlabs_tts")
        eid = t1.estimate("elevenlabs_tts", "narration", 0.05)
        t1.reserve(eid)
        t1.reconcile(eid, 0.05)

        t2 = get_project_cost_tracker(tmp_path, "proj_d")
        assert t2.budget_spent_usd == 0.05

    def test_different_projects_have_isolated_cost_logs(self, tmp_path):
        ta = get_project_cost_tracker(tmp_path, "proj_x")
        ta.approve_tool("flux_fal")
        eid = ta.estimate("flux_fal", "image", 0.20)
        ta.reserve(eid)
        ta.reconcile(eid, 0.20)

        tb = get_project_cost_tracker(tmp_path, "proj_y")
        assert tb.budget_spent_usd == 0.0


# ---- Pipeline Instruction Architecture ----

class TestPipelineInstructionArchitecture:
    """Verify that the instruction-driven architecture is in place:
    manifests reference skills, not Python handlers."""

    def test_animated_explainer_stages_have_skills(self):
        try:
            manifest = load_pipeline("animated-explainer")
        except FileNotFoundError:
            pytest.skip("animated-explainer manifest not yet created")
        for stage in manifest["stages"]:
            assert "skill" in stage, f"Stage {stage['name']} missing skill field"

    def test_stage_skill_lookup(self):
        manifest = load_pipeline("framework-smoke")
        # framework-smoke may not have skills yet — just verify the function works
        result = get_stage_skill(manifest, "idea")
        assert result is None or isinstance(result, str)

    def test_stage_review_focus_lookup(self):
        manifest = load_pipeline("framework-smoke")
        result = get_stage_review_focus(manifest, "idea")
        assert isinstance(result, list)


# ---- Agent context files ----

class TestAgentContextFiles:
    def test_agent_guide_contains_canonical_sections(self):
        contents = (PROJECT_ROOT / "AGENT_GUIDE.md").read_text(encoding="utf-8")
        for header in (
            "## Orchestrator",
            "## Stage Agents",
            "## Reviewer Protocol",
            "## Communication Protocol",
            "## Human Checkpoint Protocol",
        ):
            assert header in contents

    def test_platform_wrappers_reference_agent_guide(self):
        for path in ("CLAUDE.md", "CODEX.md", "CURSOR.md", "COPILOT.md", "AGENTS.md"):
            contents = (PROJECT_ROOT / path).read_text(encoding="utf-8")
            assert "AGENT_GUIDE.md" in contents


# ---- Media Profiles ----

class TestMediaProfiles:
    def test_all_profiles_exist(self):
        assert len(ALL_PROFILES) >= 9

    def test_get_profile(self):
        p = get_profile("youtube_landscape")
        assert p.width == 1920
        assert p.height == 1080

    def test_ffmpeg_args(self):
        args = ffmpeg_output_args(get_profile("tiktok"))
        assert "-c:v" in args
        assert "1080" in args[-1]

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError):
            get_profile("nonexistent")
