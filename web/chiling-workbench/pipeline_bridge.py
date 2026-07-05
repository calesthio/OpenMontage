"""Bridge 赤灵 Web tasks into the OpenMontage reference-video pipeline.

The bridge creates a normal reference-video project and a queue item for the
agent-led pipeline. It deliberately does not execute provider tools or paid
generation.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


WORKBENCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = WORKBENCH_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.reference_project_manager import (  # noqa: E402
    SUPPORTED_VIDEO_SUFFIXES,
    create_reference_project,
    import_reference_source,
)


DEFAULT_PROJECTS_ROOT = REPO_ROOT / "projects" / "chiling-reference-pipeline"
DEFAULT_QUEUE_ROOT = REPO_ROOT / "pipeline" / "chiling-reference-pipeline"
PIPELINE_TYPE = "reference-video-analysis"


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug.lower() or "chiling-task"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _task_project_name(task: dict[str, Any]) -> str:
    title = str(task.get("title") or "参考视频复刻")
    task_id = str(task.get("id") or "task")
    return f"{task_id} {title}"


def _reference_input(payload: dict[str, Any]) -> str:
    return str(payload.get("referenceUrl") or "").strip()


def _local_video_path(value: str) -> Path | None:
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme != "file":
        return None

    path_value = parsed.path if parsed.scheme == "file" else value
    path = Path(path_value).expanduser().resolve()
    if path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES:
        return path
    return None


def create_reference_pipeline_handoff(
    task: dict[str, Any],
    *,
    projects_root: str | Path = DEFAULT_PROJECTS_ROOT,
    queue_root: str | Path = DEFAULT_QUEUE_ROOT,
) -> dict[str, Any]:
    """Create a reference pipeline intake project from a Web task."""
    payload = dict(task.get("payload") or {})
    project = create_reference_project(
        project_name=_task_project_name(task),
        projects_root=projects_root,
    )
    project_dir = Path(project["project_dir"])

    intake_path = _write_intake(project_dir, task)
    local_video = _local_video_path(_reference_input(payload))
    if local_video:
        source_result = import_reference_source(project_dir=project_dir, source_path=local_video)
        source_artifact_path = Path(source_result["artifact_path"])
        status = "source_imported_needs_analysis"
        next_stage = "analyze"
    else:
        source_artifact_path = _write_pending_source(project_dir, task)
        status = "source_needs_resolution"
        next_stage = "ingest"

    handoff_path = _write_agent_handoff(project_dir, task, source_artifact_path, next_stage)
    queue_item_path = _write_queue_item(
        task=task,
        project_dir=project_dir,
        source_artifact_path=source_artifact_path,
        intake_path=intake_path,
        handoff_path=handoff_path,
        queue_root=Path(queue_root),
        next_stage=next_stage,
    )

    return {
        "status": status,
        "pipeline_type": PIPELINE_TYPE,
        "reference_project_dir": str(project_dir),
        "source_artifact_path": str(source_artifact_path),
        "intake_path": str(intake_path),
        "agent_handoff_path": str(handoff_path),
        "queue_item_path": str(queue_item_path),
        "next_stage": next_stage,
        "paid_generation_allowed": False,
    }


def _write_intake(project_dir: Path, task: dict[str, Any]) -> Path:
    payload = dict(task.get("payload") or {})
    intake = {
        "version": "1.0",
        "source": "chiling-workbench",
        "task_id": task.get("id"),
        "title": task.get("title"),
        "created_at": task.get("createdAt"),
        "pipeline_type": PIPELINE_TYPE,
        "payload": payload,
        "constraints": {
            "duration_seconds_max": 15,
            "batch_count_max": 5,
            "allowed_resolutions": ["480p", "720p"],
            "paid_generation_allowed": False,
            "digital_human_out_of_scope": True,
            "hide_provider_names_in_ui": True,
        },
    }
    return _write_json(project_dir / "artifacts" / "chiling-web-intake.json", intake)


def _write_pending_source(project_dir: Path, task: dict[str, Any]) -> Path:
    payload = dict(task.get("payload") or {})
    reference_input = _reference_input(payload)
    parsed = urlparse(reference_input)
    source_type = "reference_video_url" if parsed.scheme in {"http", "https"} else "reference_video_pending"
    source = {
        "version": "1.0",
        "status": "pending_source_resolution",
        "source_type": source_type,
        "original_input": reference_input,
        "project_dir": str(project_dir),
        "fallback_reason": {
            "reason": "url_requires_agent_ingest" if source_type == "reference_video_url" else "local_video_required",
            "message": "Agent must resolve the reference source through the reference-video ingest stage before analysis.",
        },
        "next_step": "resolve_reference_source",
    }
    filename = f"{_safe_slug(str(task.get('id') or 'web-task'))}-source-import.json"
    return _write_json(project_dir / "artifacts" / "reference-source" / filename, source)


def _write_agent_handoff(
    project_dir: Path,
    task: dict[str, Any],
    source_artifact_path: Path,
    next_stage: str,
) -> Path:
    payload = dict(task.get("payload") or {})
    reference_input = _reference_input(payload) or "<provide-local-reference-video>"
    text = "\n".join(
        [
            "# 赤灵 Web 任务管线交接",
            "",
            f"- Task ID: `{task.get('id')}`",
            f"- Pipeline: `{PIPELINE_TYPE}`",
            f"- Next Stage: `{next_stage}`",
            f"- Project Dir: `{project_dir}`",
            f"- Source Artifact: `{source_artifact_path}`",
            "- Paid Generation: `false`",
            "",
            "## Agent Next Step",
            "",
            "Run the reference-video-analysis pipeline from the source artifact. "
            "If the input is a URL, use the ingest director rules: try supported download, "
            "preserve provenance, and ask for a local file if access is blocked. "
            "Do not call Seedance, face replacement, digital-human, or composition providers before human approval.",
            "",
            "## Suggested Safe Command",
            "",
            "```bash",
            f".venv/bin/python scripts/reference_preview_pipeline.py {reference_input!r} --project-dir {str(project_dir)!r}",
            "```",
            "",
            "## Reviewed Script",
            "",
            "```text",
            str(payload.get("script") or ""),
            "```",
            "",
        ]
    )
    path = project_dir / "agent-handoff.md"
    path.write_text(text, encoding="utf-8")
    return path


def _write_queue_item(
    *,
    task: dict[str, Any],
    project_dir: Path,
    source_artifact_path: Path,
    intake_path: Path,
    handoff_path: Path,
    queue_root: Path,
    next_stage: str,
) -> Path:
    task_id = str(task.get("id") or "web-task")
    queue = {
        "version": "1.0",
        "status": "awaiting_agent",
        "source": "chiling-workbench",
        "task_id": task_id,
        "pipeline_type": PIPELINE_TYPE,
        "next_stage": next_stage,
        "reference_project_dir": str(project_dir),
        "source_artifact_path": str(source_artifact_path),
        "intake_path": str(intake_path),
        "agent_handoff_path": str(handoff_path),
        "paid_generation_allowed": False,
        "requires_human_approval_before_generation": True,
    }
    return _write_json(queue_root / _safe_slug(task_id) / "pipeline-entry.json", queue)
