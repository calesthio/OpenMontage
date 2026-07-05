"""Run safe local reference-video actions as tracked jobs."""

from __future__ import annotations

import json
import shlex
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from scripts.reference_action_gate import prepare_action


ROOT = Path(__file__).resolve().parent.parent
ACTIVE_JOBS: dict[str, subprocess.Popen] = {}


class ActionExecutionBlocked(ValueError):
    """Raised when an action is visible in the UI but not safe to auto-execute."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


BLOCKED_EXECUTION_RISKS: dict[str, tuple[str, str]] = {
    "paid_generation": (
        "paid_generation_prepare_only",
        "Paid generation actions are not safe local actions; prepare them manually after explicit approval.",
    ),
    "production_approval": (
        "production_approval_prepare_only",
        "Production approval actions are not safe local actions; prepare them manually after human review.",
    ),
    "delivery_export": (
        "delivery_export_prepare_only",
        "Delivery export actions are not safe local actions; prepare them manually after final business approval.",
    ),
    "manual_review": (
        "manual_review_required",
        "Manual-review actions are not executable jobs; complete the review in the human workflow.",
    ),
}


def _now() -> float:
    return round(time.time(), 3)


def _job_dir(project_dir: str | Path) -> Path:
    path = Path(project_dir).expanduser().resolve() / "artifacts" / "reference-jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_path(project_dir: str | Path, job_id: str) -> Path:
    return _job_dir(project_dir) / f"{job_id}.json"


def _log_path(project_dir: str | Path, job_id: str) -> Path:
    log_dir = Path(project_dir).expanduser().resolve() / "logs" / "reference-jobs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{job_id}.log"


def _write_job(project_dir: str | Path, record: dict[str, Any]) -> dict[str, Any]:
    path = _job_path(project_dir, str(record["job_id"]))
    payload = {**record, "job_path": str(path)}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _read_job(project_dir: str | Path, job_id: str) -> dict[str, Any]:
    path = _job_path(project_dir, job_id)
    if not path.is_file():
        raise ValueError(f"Unknown job_id: {job_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid job record: {job_id}")
    return data


def _public_job(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"argv", "command"}
    }


def _validate_safe_action(action: dict[str, Any]) -> list[str]:
    risk = str(action.get("risk") or "")
    blocked = BLOCKED_EXECUTION_RISKS.get(risk)
    if blocked is not None:
        reason, message = blocked
        raise ActionExecutionBlocked(reason, message)
    if risk != "local":
        raise ActionExecutionBlocked(
            "unsafe_action",
            "Only safe local actions can be executed by the job queue.",
        )
    if action.get("paid_generation"):
        raise ActionExecutionBlocked(
            "paid_generation_prepare_only",
            "Paid generation actions are not safe local actions; prepare them manually after explicit approval.",
        )
    if action.get("requires_confirmation"):
        raise ActionExecutionBlocked(
            "confirmation_required",
            "Confirmation-gated actions are not safe local actions; prepare them manually instead of executing them by the job queue.",
        )

    script = str(action.get("script") or "")
    if not script.startswith("scripts/") or not script.endswith(".py"):
        raise ValueError(f"Unsupported executable action script: {script}")

    try:
        argv = shlex.split(str(action.get("command") or ""))
    except ValueError as error:
        raise ValueError(f"Invalid action command: {error}") from error

    if len(argv) < 2:
        raise ValueError("Action command is missing a Python script")
    if argv[0] != ".venv/bin/python":
        raise ValueError("Only .venv/bin/python script actions can be executed")
    if argv[1] != script:
        raise ValueError("Action command script does not match action metadata")
    return argv


def start_prepared_action(
    action: dict[str, Any],
    *,
    wait: bool = False,
) -> dict[str, Any]:
    """Start an already prepared safe local action as a tracked job."""

    argv = _validate_safe_action(action)
    project_dir = Path(action["project_dir"]).expanduser().resolve()
    job_id = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
    log_path = _log_path(project_dir, job_id)

    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            argv,
            cwd=ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

    ACTIVE_JOBS[job_id] = process
    record = _write_job(
        project_dir,
        {
            "version": "1.0",
            "job_id": job_id,
            "status": "running",
            "project_dir": str(project_dir),
            "action_id": action.get("action_id"),
            "label": action.get("label"),
            "script": action.get("script"),
            "risk": action.get("risk"),
            "paid_generation": False,
            "pid": process.pid,
            "started_at": _now(),
            "log_path": str(log_path),
        },
    )

    if wait:
        process.wait()
        return get_job_status(project_dir, job_id)
    return _public_job(record)


def start_action(
    project_dir: str | Path,
    action_id: str,
    *,
    confirmation_phrase: str | None = None,
    wait: bool = False,
) -> dict[str, Any]:
    """Prepare and start a safe local project action."""

    action = prepare_action(
        project_dir,
        action_id,
        confirmation_phrase=confirmation_phrase,
    )
    return start_prepared_action(action, wait=wait)


def get_job_status(project_dir: str | Path, job_id: str) -> dict[str, Any]:
    """Return a public job status, refreshing active in-process jobs."""

    record = _read_job(project_dir, job_id)
    process = ACTIVE_JOBS.get(job_id)
    if process is not None:
        returncode = process.poll()
        if returncode is None:
            record["status"] = "running"
        else:
            record["returncode"] = returncode
            record["status"] = "succeeded" if returncode == 0 else "failed"
            record.setdefault("finished_at", _now())
            ACTIVE_JOBS.pop(job_id, None)
        record = _write_job(project_dir, record)
    return _public_job(record)


def list_jobs(project_dir: str | Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Return public job records for a project, newest first."""

    records: list[dict[str, Any]] = []
    for path in _job_dir(project_dir).glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        job_id = str(record.get("job_id") or path.stem)
        try:
            public_record = get_job_status(project_dir, job_id)
        except ValueError:
            public_record = _public_job(record)
        records.append(public_record)

    records.sort(
        key=lambda record: (
            float(record.get("started_at") or 0),
            str(record.get("job_id") or ""),
        ),
        reverse=True,
    )
    if limit is None:
        return records
    return records[: max(0, limit)]
