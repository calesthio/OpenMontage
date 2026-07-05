from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _local_action(tmp_path: Path) -> dict:
    return {
        "version": "1.0",
        "status": "ready_to_execute",
        "project_dir": str(tmp_path),
        "phase": "start",
        "action_id": "doctor",
        "label": "Doctor",
        "script": "scripts/reference_console_doctor.py",
        "command": ".venv/bin/python scripts/reference_console_doctor.py --timeout 0.01",
        "risk": "local",
        "paid_generation": False,
        "requires_confirmation": False,
    }


def test_reference_job_queue_runs_safe_local_action_without_returning_command(tmp_path):
    queue = importlib.import_module("scripts.reference_job_queue")

    result = queue.start_prepared_action(_local_action(tmp_path), wait=True)

    job_path = Path(result["job_path"])
    log_path = Path(result["log_path"])
    status = queue.get_job_status(tmp_path, result["job_id"])

    assert result["status"] == "succeeded"
    assert status["status"] == "succeeded"
    assert status["returncode"] == 0
    assert job_path.is_file()
    assert log_path.is_file()
    assert "command" not in result
    assert "command" not in status


def test_reference_job_queue_lists_project_jobs_newest_first_without_commands(tmp_path):
    queue = importlib.import_module("scripts.reference_job_queue")

    first = queue.start_prepared_action(_local_action(tmp_path), wait=True)
    second = queue.start_prepared_action(_local_action(tmp_path), wait=True)

    jobs = queue.list_jobs(tmp_path)

    assert [job["job_id"] for job in jobs] == [second["job_id"], first["job_id"]]
    assert all(job["status"] == "succeeded" for job in jobs)
    assert all(Path(job["job_path"]).is_file() for job in jobs)
    assert all(Path(job["log_path"]).is_file() for job in jobs)
    assert all("command" not in job for job in jobs)
    assert all("argv" not in job for job in jobs)


def test_reference_job_queue_blocks_paid_generation_actions(tmp_path):
    queue = importlib.import_module("scripts.reference_job_queue")
    action = _local_action(tmp_path)
    action["risk"] = "paid_generation"
    action["paid_generation"] = True

    with pytest.raises(ValueError, match="Paid generation actions.*safe local actions") as blocked:
        queue.start_prepared_action(action)

    assert blocked.value.reason == "paid_generation_prepare_only"


def test_reference_job_queue_blocks_production_approval_actions(tmp_path):
    queue = importlib.import_module("scripts.reference_job_queue")
    action = _local_action(tmp_path)
    action["risk"] = "production_approval"
    action["script"] = "scripts/approve_reference_package.py"
    action["command"] = (
        ".venv/bin/python scripts/approve_reference_package.py package.json "
        "--approval-phrase 'APPROVE REFERENCE PACKAGE'"
    )
    action["requires_confirmation"] = True

    with pytest.raises(ValueError, match="Production approval actions.*safe local actions") as blocked:
        queue.start_prepared_action(action)

    assert blocked.value.reason == "production_approval_prepare_only"


def test_reference_job_queue_blocks_delivery_export_actions(tmp_path):
    queue = importlib.import_module("scripts.reference_job_queue")
    action = _local_action(tmp_path)
    action["risk"] = "delivery_export"
    action["script"] = "scripts/export_reference_delivery.py"
    action["command"] = (
        ".venv/bin/python scripts/export_reference_delivery.py project "
        "--approval-phrase 'APPROVE FINAL DELIVERY'"
    )
    action["requires_confirmation"] = True

    with pytest.raises(ValueError, match="Delivery export actions.*safe local actions") as blocked:
        queue.start_prepared_action(action)

    assert blocked.value.reason == "delivery_export_prepare_only"


def test_reference_job_queue_blocks_manual_review_actions(tmp_path):
    queue = importlib.import_module("scripts.reference_job_queue")
    action = _local_action(tmp_path)
    action["risk"] = "manual_review"
    action["script"] = "manual_review"
    action["command"] = "Review the generated sample clip before approving paid tasks."

    with pytest.raises(ValueError, match="Manual-review actions") as blocked:
        queue.start_prepared_action(action)

    assert blocked.value.reason == "manual_review_required"
