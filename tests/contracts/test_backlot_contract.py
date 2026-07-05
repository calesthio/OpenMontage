"""Contract tests for Backlot Phase 0: gate enforcement, checkpoint history,
project markers, and tool-event instrumentation."""

import json

import pytest

from lib.checkpoint import (
    CheckpointValidationError,
    HISTORY_DIRNAME,
    PROJECT_MARKER_FILENAME,
    init_project,
    read_checkpoint,
    write_checkpoint,
)
from lib.events import emit_event, infer_project_dir, read_events


def _minimal_script() -> dict:
    return {
        "version": "1.0",
        "title": "Test Script",
        "total_duration_seconds": 10,
        "sections": [
            {"id": "s1", "text": "Hello.", "start_seconds": 0, "end_seconds": 10}
        ],
    }


class TestGateEnforcement:
    """GI-4: gated stages cannot be completed without approval evidence."""

    def test_completed_without_approval_raises(self, tmp_path):
        with pytest.raises(CheckpointValidationError, match="GATE VIOLATION"):
            write_checkpoint(
                tmp_path, "proj", "script", "completed",
                artifacts={"script": _minimal_script()},
                pipeline_type="animated-explainer",
            )

    def test_awaiting_human_is_the_correct_gate_state(self, tmp_path):
        path = write_checkpoint(
            tmp_path, "proj", "script", "awaiting_human",
            artifacts={"script": _minimal_script()},
            pipeline_type="animated-explainer",
        )
        cp = json.loads(path.read_text())
        assert cp["status"] == "awaiting_human"
        # Manifest gating is reflected in the checkpoint even when the
        # caller didn't pass human_approval_required.
        assert cp["human_approval_required"] is True

    def test_completed_with_approval_passes(self, tmp_path):
        path = write_checkpoint(
            tmp_path, "proj", "script", "completed",
            artifacts={"script": _minimal_script()},
            pipeline_type="animated-explainer",
            human_approved=True,
        )
        assert path.exists()

    def test_assets_stage_now_gates(self, tmp_path):
        """The assets gate flip: every pipeline's assets stage requires approval."""
        manifest_assets = {"version": "1.0", "assets": [], "total_cost_usd": 0.0}
        with pytest.raises(CheckpointValidationError, match="GATE VIOLATION"):
            write_checkpoint(
                tmp_path, "proj", "assets", "completed",
                artifacts={"asset_manifest": manifest_assets},
                pipeline_type="cinematic",
            )

    def test_ungated_stage_unaffected(self, tmp_path):
        from tests.contracts.test_phase0_contracts import sample_artifact

        path = write_checkpoint(
            tmp_path, "proj", "research", "completed",
            artifacts={"research_brief": sample_artifact("research_brief")},
            pipeline_type="animated-explainer",
        )
        assert path.exists()


class TestCheckpointHistory:
    """Superseded checkpoints are archived, not destroyed."""

    def test_overwrite_archives_previous(self, tmp_path):
        write_checkpoint(
            tmp_path, "proj", "script", "awaiting_human",
            artifacts={"script": _minimal_script()},
            pipeline_type="animated-explainer",
        )
        write_checkpoint(
            tmp_path, "proj", "script", "completed",
            artifacts={"script": _minimal_script()},
            pipeline_type="animated-explainer",
            human_approved=True,
        )
        history = list((tmp_path / "proj" / HISTORY_DIRNAME).glob("checkpoint_script_*.json"))
        assert len(history) == 1
        archived = json.loads(history[0].read_text())
        assert archived["status"] == "awaiting_human"
        current = read_checkpoint(tmp_path, "proj", "script")
        assert current["status"] == "completed"

    def test_in_progress_refreshes_are_not_archived(self, tmp_path):
        for _ in range(3):
            write_checkpoint(
                tmp_path, "proj", "assets", "in_progress",
                artifacts={},
                pipeline_type="cinematic",
                metadata={"partial_progress": {"completed_scene_ids": ["sc1"]}},
            )
        history_dir = tmp_path / "proj" / HISTORY_DIRNAME
        assert not history_dir.exists() or not list(history_dir.iterdir())


class TestInitProject:
    def test_creates_layout_and_marker(self, tmp_path):
        pdir = init_project(
            "my-film", title="My Film", pipeline_type="cinematic",
            pipeline_dir=tmp_path, style_playbook="clean-professional",
        )
        assert (pdir / "artifacts").is_dir()
        assert (pdir / "assets" / "images").is_dir()
        assert (pdir / "renders").is_dir()
        marker = json.loads((pdir / PROJECT_MARKER_FILENAME).read_text())
        assert marker["project_id"] == "my-film"
        assert marker["pipeline_type"] == "cinematic"
        assert marker["style_playbook"] == "clean-professional"
        assert "created_at" in marker

    def test_idempotent_preserves_created_at(self, tmp_path):
        pdir = init_project("p", title="P", pipeline_type="cinematic", pipeline_dir=tmp_path)
        created = json.loads((pdir / PROJECT_MARKER_FILENAME).read_text())["created_at"]
        init_project("p", title="P2", pipeline_type="cinematic", pipeline_dir=tmp_path)
        marker = json.loads((pdir / PROJECT_MARKER_FILENAME).read_text())
        assert marker["created_at"] == created
        assert marker["title"] == "P2"


class TestEvents:
    def test_emit_and_read_roundtrip(self, tmp_path):
        emit_event(tmp_path, {"tool": "t1", "event": "start", "scene_id": "sc1"})
        emit_event(tmp_path, {"tool": "t1", "event": "finish", "duration_s": 1.2})
        events = read_events(tmp_path)
        assert len(events) == 2
        assert events[0]["event"] == "start"
        assert events[1]["duration_s"] == 1.2
        assert all("ts" in e for e in events)

    def test_read_tolerates_garbage_lines(self, tmp_path):
        (tmp_path / "events.jsonl").write_text('{"ok": 1}\nnot json\n{"ok": 2}\n')
        events = read_events(tmp_path)
        assert [e["ok"] for e in events] == [1, 2]

    def test_infer_project_dir_from_output_path(self):
        from lib.events import PROJECTS_DIR
        target = PROJECTS_DIR / "some-proj" / "assets" / "images" / "x.png"
        assert infer_project_dir({"output_path": str(target)}) == PROJECTS_DIR / "some-proj"
        assert infer_project_dir({"output_path": "C:/elsewhere/x.png"}) is None
        assert infer_project_dir("not-a-dict") is None


class TestBaseToolInstrumentation:
    def test_execute_emits_events(self, tmp_path, monkeypatch):
        import lib.events as events_mod
        monkeypatch.setattr(events_mod, "PROJECTS_DIR", tmp_path)

        from tools.base_tool import BaseTool, ToolResult

        class FakeTool(BaseTool):
            name = "fake_tool"

            def execute(self, inputs):
                return ToolResult(success=True, cost_usd=0.05)

        project = tmp_path / "proj-x"
        project.mkdir()
        out = project / "assets" / "clip.mp4"
        FakeTool().execute({"output_path": str(out), "scene_id": "sc3"})

        events = read_events(project)
        assert [e["event"] for e in events] == ["start", "finish"]
        assert events[0]["scene_id"] == "sc3"
        assert events[1]["success"] is True
        assert events[1]["cost_usd"] == 0.05

    def test_execute_emits_error_event_and_reraises(self, tmp_path, monkeypatch):
        import lib.events as events_mod
        monkeypatch.setattr(events_mod, "PROJECTS_DIR", tmp_path)

        from tools.base_tool import BaseTool

        class BoomTool(BaseTool):
            name = "boom_tool"

            def execute(self, inputs):
                raise RuntimeError("kaput")

        project = tmp_path / "proj-y"
        project.mkdir()
        with pytest.raises(RuntimeError, match="kaput"):
            BoomTool().execute({"output_path": str(project / "a.png")})
        events = read_events(project)
        assert [e["event"] for e in events] == ["start", "error"]
        assert "kaput" in events[1]["error"]

    def test_unattributable_call_emits_nothing_and_works(self, tmp_path):
        from tools.base_tool import BaseTool, ToolResult

        class PlainTool(BaseTool):
            name = "plain_tool"

            def execute(self, inputs):
                return ToolResult(success=True)

        result = PlainTool().execute({"text": "hello"})
        assert result.success is True
