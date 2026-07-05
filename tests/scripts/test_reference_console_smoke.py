from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def test_reference_console_smoke_walks_local_contract(tmp_path):
    smoke = importlib.import_module("scripts.reference_console_smoke")
    source = tmp_path / "reference.mp4"
    source.write_bytes(b"fake mp4")

    result = smoke.run_smoke(
        project_name="Console Smoke",
        source_path=source,
        projects_root=tmp_path / "projects",
        action_id="analyze_imported_reference",
        wait=True,
    )

    assert result["status"] in {"passed", "job_failed"}
    assert result["failure_stage"] in {None, "job"}
    assert [step["stage"] for step in result["steps"]] == [
        "health",
        "load_console",
        "create_project",
        "import_source",
        "load_state",
        "select_action",
        "execute_action",
        "poll_job",
        "list_jobs",
        "final_state",
    ]
    assert all(step["status"] in {"passed", "failed", "skipped"} for step in result["steps"])
    assert result["paid_generation_started"] is False
    assert result["console"]["status"] == "ok"
    assert result["console"]["markers"]["has_copy_button"] is True
    assert result["console"]["markers"]["has_download_button"] is True
    assert result["console"]["markers"]["has_guidance_renderer"] is True
    assert result["console"]["markers"]["no_raw_shell"] is True
    assert result["project"]["status"] == "created"
    assert result["import_source"]["status"] == "imported"
    assert result["initial_state"]["status"]["status"] == "source_imported_needs_analysis"
    assert result["action"]["id"] == "analyze_imported_reference"
    assert result["action"]["can_execute"] is True
    assert result["job"]["action_id"] == "analyze_imported_reference"
    assert Path(result["job"]["job_path"]).is_file()
    assert Path(result["job"]["log_path"]).is_file()
    assert result["jobs"]["jobs"][0]["job_id"] == result["job"]["job_id"]
    assert "command" not in json.dumps(result, ensure_ascii=False)
    assert ".venv/bin/python" not in json.dumps(result, ensure_ascii=False)


def test_reference_console_smoke_blocks_prepare_only_actions(tmp_path):
    smoke = importlib.import_module("scripts.reference_console_smoke")
    source = tmp_path / "reference.mp4"
    source.write_bytes(b"fake mp4")

    result = smoke.run_smoke(
        project_name="Console Smoke",
        source_path=source,
        projects_root=tmp_path / "projects",
        action_id="run_one_paid_seedance_sample",
        wait=False,
    )

    assert result["status"] == "blocked"
    assert result["failure_stage"] == "select_action"
    assert result["recommended_action"] == "choose_can_execute_action"
    assert any(
        step["stage"] == "select_action" and step["status"] == "failed"
        for step in result["steps"]
    )
    assert result["paid_generation_started"] is False
    assert "safe auto-executable action" in result["error"]
    assert "command" not in json.dumps(result, ensure_ascii=False)


def test_reference_console_smoke_main_prints_json(tmp_path, capsys):
    smoke = importlib.import_module("scripts.reference_console_smoke")
    source = tmp_path / "reference.mp4"
    source.write_bytes(b"fake mp4")

    exit_code = smoke.main(
        [
            str(source),
            "--project-name",
            "Console Smoke",
            "--projects-root",
            str(tmp_path / "projects"),
            "--action-id",
            "analyze_imported_reference",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code in {0, 1}
    assert payload["project"]["status"] == "created"
    assert payload["paid_generation_started"] is False


def test_reference_console_smoke_can_run_against_real_local_http_server(tmp_path):
    smoke = importlib.import_module("scripts.reference_console_smoke")
    source = tmp_path / "reference.mp4"
    source.write_bytes(b"fake mp4")

    try:
        result = smoke.run_smoke(
            project_name="Console Smoke HTTP",
            source_path=source,
            projects_root=tmp_path / "projects",
            action_id="analyze_imported_reference",
            wait=True,
            server_mode="http",
            port=0,
        )
    except PermissionError as error:
        pytest.skip(f"Local port binding is unavailable in this sandbox: {error}")

    assert result["status"] in {"passed", "job_failed"}
    assert result["failure_stage"] in {None, "job"}
    assert result["server_mode"] == "http"
    assert result["base_url"].startswith("http://127.0.0.1:")
    assert result["health"]["service"] == "reference_local_api"
    assert result["console"]["status"] == "ok"
    assert result["console"]["markers"]["has_copy_button"] is True
    assert result["console"]["markers"]["has_download_button"] is True
    assert result["project"]["status"] == "created"
    assert result["paid_generation_started"] is False
    assert "command" not in json.dumps(result, ensure_ascii=False)
