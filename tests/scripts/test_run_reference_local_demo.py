from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_local_demo_runner_analyzes_source_and_writes_demo_report(monkeypatch, tmp_path):
    runner = importlib.import_module("scripts.run_reference_local_demo")
    project_dir = tmp_path / "project"
    source = tmp_path / "reference.mp4"
    source.write_bytes(b"fake mp4")
    package_path = project_dir / "artifacts" / "sample-replication-package.json"
    report_path = project_dir / "artifacts" / "reference-demo-report" / "sample-demo-report.json"

    def fake_analyze(source: str, project_dir: Path | None = None):
        assert source == str(tmp_path / "reference.mp4")
        assert project_dir == tmp_path / "project"
        package_path.parent.mkdir(parents=True)
        package_path.write_text(
            json.dumps({"approval": {"status": "pending_human_review"}}),
            encoding="utf-8",
        )
        return {
            "json_path": str(package_path),
            "markdown_path": str(package_path.with_suffix(".md")),
        }

    def fake_demo_report(**kwargs):
        assert kwargs["project_dir"] == project_dir
        assert kwargs["duration"] == "15"
        assert kwargs["resolution"] == "480p"
        assert kwargs["batch_size"] == 1
        report_path.parent.mkdir(parents=True)
        report_path.write_text("{}", encoding="utf-8")
        return {
            "json_report_path": str(report_path),
            "markdown_report_path": str(report_path.with_suffix(".md")),
            "seedance_preview": {
                "status": "blocked_until_approval",
                "paid_generation_started": False,
            },
            "status": {"status": "analysis_ready_needs_prompt_or_edit"},
        }

    monkeypatch.setattr(runner, "analyze_reference_source", fake_analyze)
    monkeypatch.setattr(runner, "build_demo_report", fake_demo_report)

    result = runner.run_local_demo(
        source=str(source),
        project_dir=project_dir,
    )

    assert result["status"] == "ready_for_human_edit"
    assert result["project_dir"] == str(project_dir)
    assert result["replication_package_path"] == str(package_path)
    assert result["prompt_reverse"]["enabled"] is False
    assert result["paid_generation_started"] is False
    assert result["demo_report"]["json_report_path"] == str(report_path)
    assert result["next_commands"][0]["script"] == "scripts/reference_review_wizard.py"


def test_local_demo_runner_can_run_optional_prompt_reverse(monkeypatch, tmp_path):
    runner = importlib.import_module("scripts.run_reference_local_demo")
    project_dir = tmp_path / "project"
    package_path = project_dir / "artifacts" / "sample-replication-package.json"
    reversed_path = (
        project_dir / "artifacts" / "reference-prompts" / "sample-prompts-reversed-package.json"
    )

    def fake_analyze(source: str, project_dir: Path | None = None):
        package_path.parent.mkdir(parents=True)
        package_path.write_text(json.dumps({"scenes": []}), encoding="utf-8")
        return {"json_path": str(package_path), "markdown_path": str(package_path.with_suffix(".md"))}

    class FakePromptReverse:
        def execute(self, inputs):
            from tools.base_tool import ToolResult

            assert inputs["provider"] == "doubao"
            assert inputs["replication_package_path"] == str(package_path)
            reversed_path.parent.mkdir(parents=True)
            reversed_path.write_text(json.dumps({"scenes": []}), encoding="utf-8")
            return ToolResult(
                success=True,
                data={
                    "json_path": str(reversed_path),
                    "scene_results": [{"scene_id": "s1", "status": "updated"}],
                },
            )

    monkeypatch.setattr(runner, "analyze_reference_source", fake_analyze)
    monkeypatch.setattr(runner, "ReferencePromptReverse", FakePromptReverse)
    monkeypatch.setattr(
        runner,
        "run_preflight",
        lambda **kwargs: {"status": "ready", "issues": [], "safety": {"paid_generation_started": False}},
    )
    monkeypatch.setattr(
        runner,
        "build_demo_report",
        lambda **kwargs: {
            "json_report_path": str(project_dir / "demo.json"),
            "seedance_preview": {
                "status": "blocked_until_approval",
                "paid_generation_started": False,
            },
        },
    )

    result = runner.run_local_demo(
        source="https://v.douyin.com/example/",
        project_dir=project_dir,
        reverse_prompts=True,
        provider="doubao",
    )

    assert result["replication_package_path"] == str(reversed_path)
    assert result["prompt_reverse"]["enabled"] is True
    assert result["prompt_reverse"]["scene_results"][0]["status"] == "updated"
    assert result["paid_generation_started"] is False


def test_local_demo_runner_blocks_when_preflight_blocks(monkeypatch, tmp_path):
    runner = importlib.import_module("scripts.run_reference_local_demo")

    def fail_analyze(source: str, project_dir: Path | None = None):
        raise AssertionError("analysis should not run when preflight blocks")

    monkeypatch.setattr(runner, "analyze_reference_source", fail_analyze)
    monkeypatch.setattr(
        runner,
        "run_preflight",
        lambda **kwargs: {
            "status": "blocked",
            "issues": [{"level": "blocker", "code": "missing_local_source"}],
            "safety": {"paid_generation_started": False},
        },
    )

    try:
        runner.run_local_demo(
            source=str(tmp_path / "missing.mp4"),
            project_dir=tmp_path / "project",
        )
    except RuntimeError as exc:
        assert "preflight blocked" in str(exc)
    else:
        raise AssertionError("run_local_demo should raise when preflight blocks")


def test_local_demo_runner_main_returns_download_fallback(monkeypatch, tmp_path, capsys):
    runner = importlib.import_module("scripts.run_reference_local_demo")

    def fake_analyze(source: str, project_dir: Path | None = None):
        raise runner.ReferenceDownloadError(
            url=source,
            reason="login required",
            project_dir=project_dir or tmp_path / "project",
            platform="douyin",
        )

    monkeypatch.setattr(runner, "analyze_reference_source", fake_analyze)

    exit_code = runner.main(
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
