"""Build a web/client-friendly JSON snapshot for a reference-video project."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reference_project_status import inspect_project


ARTIFACTS: dict[str, str] = {
    "reference_source_import": "artifacts/reference-source/*-source-import.json",
    "replication_package": "artifacts/*-replication-package.json",
    "prompt_reversed_package": "artifacts/reference-prompts/*-prompts-reversed-package.json",
    "text_edited_package": "artifacts/reference-edits/*-text-edited-package.json",
    "assets_bound_package": "artifacts/reference-assets/*-assets-bound-package.json",
    "approved_package": "artifacts/reference-review/*-approved-package.json",
    "production_plan": "artifacts/*-production-plan.json",
    "seedance_dry_run": "artifacts/*-seedance-batch-dry-run.json",
    "seedance_sample": "artifacts/*-seedance-sample-result.json",
    "final_edit_plan": "artifacts/reference-final-edit/*-final-edit-plan.json",
    "render_report": "artifacts/reference-render/*-render-report.json",
    "final_review_report": "artifacts/reference-final-review/*-final-review.json",
    "demo_report": "artifacts/reference-demo-report/*-demo-report.json",
    "edit_sheet": "artifacts/reference-edit-sheets/*-edit-sheet.json",
    "delivery_manifest": "deliveries/*/delivery-manifest.json",
}

PHASE_BY_STATUS = {
    "empty_project": "start",
    "source_imported_needs_analysis": "source_imported",
    "analysis_ready_needs_prompt_or_edit": "analysis",
    "prompts_reversed_needs_edit": "analysis",
    "edited_needs_assets_or_approval": "human_edit",
    "assets_bound_needs_approval": "human_edit",
    "approved_for_production": "approval",
    "production_plan_ready": "production_planning",
    "seedance_dry_run_ready": "generation_planning",
    "seedance_sample_generated": "sample_review",
    "final_edit_ready_for_compose": "compose",
    "final_render_ready": "final_review",
    "final_review_ready_for_delivery": "final_review",
    "delivery_exported": "delivery",
}


def _latest(project_dir: Path, pattern: str) -> Path | None:
    candidates = [path for path in project_dir.glob(pattern) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path)))


def _safe_read_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _artifact_paths(project_dir: Path) -> dict[str, str | None]:
    return {
        name: str(path) if (path := _latest(project_dir, pattern)) else None
        for name, pattern in ARTIFACTS.items()
    }


def _file_exists(path: str | None) -> bool | None:
    if not path:
        return None
    return Path(path).expanduser().is_file()


def _delivery_payload(artifacts: dict[str, str | None]) -> dict[str, Any] | None:
    manifest = _safe_read_json(artifacts.get("delivery_manifest"))
    if not manifest:
        return None
    return {
        "delivery_dir": manifest.get("delivery_dir"),
        "video_path": manifest.get("video_path"),
        "included_files": manifest.get("included_files") or [],
        "manifest_path": artifacts.get("delivery_manifest"),
    }


def _media_payload(status: dict[str, Any], delivery: dict[str, Any] | None) -> dict[str, Any]:
    delivery_video_path = (delivery or {}).get("video_path")
    return {
        "render_output_path": status.get("render_output_path"),
        "render_output_exists": status.get("render_output_exists"),
        "delivery_video_path": delivery_video_path,
        "delivery_video_exists": _file_exists(delivery_video_path),
    }


def _approval_payload(status: dict[str, Any], artifacts: dict[str, str | None]) -> dict[str, Any]:
    current = _safe_read_json(status.get("current_artifact_path"))
    approval = current.get("approval") if isinstance(current.get("approval"), dict) else {}
    return {
        "approval_status": status.get("approval_status") or approval.get("status"),
        "target_mode": status.get("target_mode") or approval.get("target_mode"),
        "approved_package_path": artifacts.get("approved_package"),
    }


def _command_parts(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _flag_value(parts: list[str], flag: str) -> str | None:
    try:
        index = parts.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def _risk_for_action(command: dict[str, Any]) -> str:
    name = str(command.get("name") or "")
    script = str(command.get("script") or "")
    raw_command = str(command.get("command") or "")
    if "--allow-paid-generation" in raw_command or "paid" in name:
        return "paid_generation"
    if "export_reference_delivery.py" in script or name == "export_delivery_package":
        return "delivery_export"
    if script == "manual_review":
        return "manual_review"
    if "approve_reference_package.py" in script:
        return "production_approval"
    return "local"


def _ui_action(command: dict[str, Any]) -> dict[str, Any]:
    raw_command = str(command.get("command") or "")
    parts = _command_parts(raw_command)
    confirmation_phrase = _flag_value(parts, "--approval-phrase")
    risk = _risk_for_action(command)
    return {
        "id": str(command.get("name") or command.get("script") or "action"),
        "label": str(command.get("name") or "action").replace("_", " ").title(),
        "script": command.get("script"),
        "command": raw_command,
        "risk": risk,
        "paid_generation": risk == "paid_generation",
        "requires_confirmation": bool(confirmation_phrase),
        "confirmation_phrase": confirmation_phrase,
        "enabled": True,
    }


def _ui_actions(status: dict[str, Any]) -> list[dict[str, Any]]:
    return [_ui_action(command) for command in status.get("next_commands") or []]


def build_snapshot(project_dir: str | Path) -> dict[str, Any]:
    project_path = Path(project_dir).expanduser().resolve()
    status = inspect_project(project_path)
    artifacts = _artifact_paths(project_path)
    delivery = _delivery_payload(artifacts)
    phase = PHASE_BY_STATUS.get(str(status.get("status")), "unknown")
    paid_generation_started = bool(status.get("paid_generation_started"))
    return {
        "version": "1.0",
        "project_dir": str(project_path),
        "phase": phase,
        "status": status,
        "artifacts": artifacts,
        "approval": _approval_payload(status, artifacts),
        "media": _media_payload(status, delivery),
        "delivery": delivery,
        "next_actions": status.get("next_commands") or [],
        "ui_actions": _ui_actions(status),
        "safety": {
            "secrets_redacted": True,
            "network_calls_started": False,
            "paid_generation_started": paid_generation_started,
            "requires_team_authorized_assets": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Reference-video project directory")
    args = parser.parse_args(argv)
    print(json.dumps(build_snapshot(args.project_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
