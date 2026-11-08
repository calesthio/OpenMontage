"""Real instrumented tool calls must remain visible while a sibling runs."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from backlot.state import load_board_state
from lib import events
from tools.base_tool import BaseTool, ToolResult


@pytest.mark.parametrize("second_errors", [False, True])
def test_parallel_same_scene_keeps_unfinished_call_visible(tmp_path, monkeypatch, second_errors):
    root = tmp_path / "projects"
    project = root / "film"
    (project / "artifacts").mkdir(parents=True)
    (project / "artifacts" / "scene_plan.json").write_text(json.dumps({
        "version": "1.0", "scenes": [{"id": "scene-1"}],
    }))
    monkeypatch.setattr(events, "PROJECTS_DIR", root)
    entered = [Event(), Event()]
    release = [Event(), Event()]

    class LocalGeneration(BaseTool):
        name = "local-generation"

        def execute(self, inputs):
            index = inputs["index"]
            entered[index].set()
            assert release[index].wait(5), "test release timed out"
            if index == 1 and second_errors:
                raise RuntimeError("local fixture failure")
            return ToolResult(success=True)

    def scene():
        return load_board_state(project)["storyboard"]["scenes"][0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = []
        try:
            for index in range(2):
                futures.append(pool.submit(LocalGeneration().execute, {
                    "project_dir": str(project), "scene_id": "scene-1", "index": index,
                }))
                assert entered[index].wait(5)
            assert scene()["generating"] is True
            release[0].set()
            futures[0].result(timeout=5)
            assert scene()["generating"] is True
            assert scene()["generating_tool"] == "local-generation"
        finally:
            for barrier in release:
                barrier.set()
            for index, future in enumerate(futures):
                if index == 1 and second_errors:
                    with pytest.raises(RuntimeError, match="local fixture failure"):
                        future.result(timeout=5)
                else:
                    future.result(timeout=5)
    assert scene()["generating"] is False

    stream = events.read_events(project)
    starts = [e for e in stream if e["event"] == "start"]
    assert len({e["call_id"] for e in starts}) == 2
    for start in starts:
        assert len([e for e in stream if e["call_id"] == start["call_id"]]) == 2


def test_legacy_events_pair_one_matching_tool_call(tmp_path):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "scene_plan.json").write_text(json.dumps({
        "version": "1.0", "scenes": [{"id": "scene-1"}],
    }))
    for tool, event in [("image", "start"), ("video", "start"), ("image", "finish")]:
        events.emit_event(tmp_path, {"tool": tool, "event": event, "scene_id": "scene-1"})
    scene = load_board_state(tmp_path)["storyboard"]["scenes"][0]
    assert scene["generating"] is True
    assert scene["generating_tool"] == "video"
    events.emit_event(tmp_path, {"tool": "video", "event": "error", "scene_id": "scene-1"})
    assert load_board_state(tmp_path)["storyboard"]["scenes"][0]["generating"] is False


def test_nested_provider_completion_does_not_clear_selector(tmp_path):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "scene_plan.json").write_text(json.dumps({
        "version": "1.0", "scenes": [{"id": "scene-1"}],
    }))
    for payload in [
        {"tool": "selector", "event": "start", "call_id": "outer"},
        {"tool": "provider", "event": "start", "call_id": "inner", "depth": 1},
        {"tool": "provider", "event": "finish", "call_id": "inner", "depth": 1},
    ]:
        events.emit_event(tmp_path, {**payload, "scene_id": "scene-1"})
    scene = load_board_state(tmp_path)["storyboard"]["scenes"][0]
    assert scene["generating"] is True
    assert scene["generating_tool"] == "selector"
