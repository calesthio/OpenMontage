from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_preview_pipeline_analyzes_source_without_prompt_reverse(monkeypatch, tmp_path, capsys):
    preview_pipeline = importlib.import_module("scripts.reference_preview_pipeline")

    package_path = tmp_path / "project" / "artifacts" / "sample-replication-package.json"
    markdown_path = tmp_path / "project" / "artifacts" / "sample-replication-package.md"

    def fake_analyze(source: str, project_dir: Path | None = None):
        assert source == str(tmp_path / "reference.mp4")
        assert project_dir == tmp_path / "project"
        package_path.parent.mkdir(parents=True)
        package_path.write_text(json.dumps({"approval": {"status": "pending_human_review"}}), encoding="utf-8")
        markdown_path.write_text("# Review", encoding="utf-8")
        return {
            "json_path": str(package_path),
            "markdown_path": str(markdown_path),
            "replication_package": {"approval": {"status": "pending_human_review"}},
        }

    monkeypatch.setattr(preview_pipeline, "analyze_reference_source", fake_analyze)

    exit_code = preview_pipeline.main(
        [
            str(tmp_path / "reference.mp4"),
            "--project-dir",
            str(tmp_path / "project"),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "ready_for_human_edit"
    assert payload["prompt_reverse"]["enabled"] is False
    assert payload["replication_package_path"] == str(package_path)
    assert payload["next_steps"][0]["script"] == "scripts/edit_reference_package.py"


def test_preview_pipeline_can_run_optional_prompt_reverse(monkeypatch, tmp_path, capsys):
    preview_pipeline = importlib.import_module("scripts.reference_preview_pipeline")

    analyzed_path = tmp_path / "project" / "artifacts" / "sample-replication-package.json"
    reversed_path = tmp_path / "project" / "artifacts" / "reference-prompts" / "sample-prompts-reversed-package.json"

    def fake_analyze(source: str, project_dir: Path | None = None):
        analyzed_path.parent.mkdir(parents=True)
        analyzed_path.write_text(json.dumps({"scenes": []}), encoding="utf-8")
        return {"json_path": str(analyzed_path), "markdown_path": "review.md"}

    class FakePromptReverse:
        def execute(self, inputs):
            from tools.base_tool import ToolResult

            assert inputs["replication_package_path"] == str(analyzed_path)
            assert inputs["project_dir"] == str(tmp_path / "project")
            assert inputs["provider"] == "doubao"
            reversed_path.parent.mkdir(parents=True)
            reversed_path.write_text(json.dumps({"scenes": []}), encoding="utf-8")
            return ToolResult(
                success=True,
                data={
                    "json_path": str(reversed_path),
                    "replication_package": {"scenes": []},
                    "scene_results": [{"scene_id": "s1", "status": "updated"}],
                },
            )

    monkeypatch.setattr(preview_pipeline, "analyze_reference_source", fake_analyze)
    monkeypatch.setattr(preview_pipeline, "ReferencePromptReverse", FakePromptReverse)

    exit_code = preview_pipeline.main(
        [
            "https://v.douyin.com/example/",
            "--project-dir",
            str(tmp_path / "project"),
            "--reverse-prompts",
            "--provider",
            "doubao",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "ready_for_human_edit"
    assert payload["prompt_reverse"]["enabled"] is True
    assert payload["prompt_reverse"]["provider"] == "doubao"
    assert payload["prompt_reverse"]["scene_results"][0]["status"] == "updated"
    assert payload["replication_package_path"] == str(reversed_path)


def test_preview_pipeline_returns_download_fallback(monkeypatch, tmp_path, capsys):
    preview_pipeline = importlib.import_module("scripts.reference_preview_pipeline")

    def fake_analyze(source: str, project_dir: Path | None = None):
        raise preview_pipeline.ReferenceDownloadError(
            url=source,
            reason="login required",
            project_dir=project_dir or tmp_path / "project",
            platform="other_url",
        )

    monkeypatch.setattr(preview_pipeline, "analyze_reference_source", fake_analyze)

    exit_code = preview_pipeline.main(
        [
            "https://v.douyin.com/blocked/",
            "--project-dir",
            str(tmp_path / "project"),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert exit_code == 3
    assert payload["status"] == "download_failed"
    assert payload["fallback_required"] == "local_video_file"
