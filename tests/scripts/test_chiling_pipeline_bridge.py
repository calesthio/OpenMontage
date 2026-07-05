from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "web" / "chiling-workbench" / "pipeline_bridge.py"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("chiling_pipeline_bridge", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _task(payload: dict) -> dict:
    return {
        "id": "task_001",
        "title": "参考视频复刻",
        "createdAt": 1783185000000,
        "payload": {
            "duration": 15,
            "resolution": "480p",
            "count": 1,
            "script": "第一句\n第二句",
            "referenceName": "ref.mp4",
            "portraitName": "face.png",
            **payload,
        },
    }


def test_chiling_bridge_imports_local_video_as_reference_source(tmp_path):
    bridge = _load_bridge()
    source = tmp_path / "input.mp4"
    source.write_bytes(b"fake mp4")

    result = bridge.create_reference_pipeline_handoff(
        _task({"referenceUrl": str(source)}),
        projects_root=tmp_path / "projects",
        queue_root=tmp_path / "pipeline-queue",
    )

    project_dir = Path(result["reference_project_dir"])
    source_artifact = Path(result["source_artifact_path"])
    queue_item = Path(result["queue_item_path"])
    source_payload = json.loads(source_artifact.read_text(encoding="utf-8"))
    queue_payload = json.loads(queue_item.read_text(encoding="utf-8"))

    assert result["status"] == "source_imported_needs_analysis"
    assert project_dir.name.startswith("task_001")
    assert source_payload["status"] == "imported"
    assert Path(source_payload["local_video_path"]).is_file()
    assert queue_payload["pipeline_type"] == "reference-video-analysis"
    assert queue_payload["next_stage"] == "analyze"
    assert queue_payload["paid_generation_allowed"] is False
    assert (project_dir / "artifacts" / "chiling-web-intake.json").is_file()
    assert (project_dir / "agent-handoff.md").is_file()


def test_chiling_bridge_writes_pending_source_resolution_for_urls(tmp_path):
    bridge = _load_bridge()

    result = bridge.create_reference_pipeline_handoff(
        _task({"referenceUrl": "https://example.com/ref-video"}),
        projects_root=tmp_path / "projects",
        queue_root=tmp_path / "pipeline-queue",
    )

    source_payload = json.loads(Path(result["source_artifact_path"]).read_text(encoding="utf-8"))
    queue_payload = json.loads(Path(result["queue_item_path"]).read_text(encoding="utf-8"))

    assert result["status"] == "source_needs_resolution"
    assert source_payload["status"] == "pending_source_resolution"
    assert source_payload["fallback_reason"]["reason"] == "url_requires_agent_ingest"
    assert source_payload["original_input"] == "https://example.com/ref-video"
    assert queue_payload["next_stage"] == "ingest"
    assert queue_payload["paid_generation_allowed"] is False
