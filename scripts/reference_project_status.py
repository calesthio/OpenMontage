"""Inspect a reference-video project and print the safest next command."""

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


ARTIFACT_PATTERNS: list[tuple[str, str]] = [
    ("seedance_sample_generated", "artifacts/*-seedance-sample-result.json"),
    ("seedance_dry_run_ready", "artifacts/*-seedance-batch-dry-run.json"),
    ("production_plan_ready", "artifacts/*-production-plan.json"),
    ("approved_for_production", "artifacts/reference-review/*-approved-package.json"),
    ("assets_bound_needs_approval", "artifacts/reference-assets/*-assets-bound-package.json"),
    ("edited_needs_assets_or_approval", "artifacts/reference-edits/*-text-edited-package.json"),
    ("prompts_reversed_needs_edit", "artifacts/reference-prompts/*-prompts-reversed-package.json"),
    ("analysis_ready_needs_prompt_or_edit", "artifacts/*-replication-package.json"),
    ("source_imported_needs_analysis", "artifacts/reference-source/*-source-import.json"),
]


def _quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def _command(*parts: str | Path) -> str:
    return " ".join(_quote(part) for part in parts)


def _latest(project_dir: Path, pattern: str) -> Path | None:
    candidates = [path for path in project_dir.glob(pattern) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path)))


def _safe_read_json(path: Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_project_path(project_dir: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_dir / path
    return path.resolve()


def _find_artifacts(project_dir: Path) -> dict[str, Path | None]:
    artifacts = {status: _latest(project_dir, pattern) for status, pattern in ARTIFACT_PATTERNS}
    artifacts["final_edit_plan"] = _latest(
        project_dir, "artifacts/reference-final-edit/*-final-edit-plan.json"
    )
    artifacts["render_report"] = _latest(
        project_dir, "artifacts/reference-render/*-render-report.json"
    )
    artifacts["final_review_report"] = _latest(
        project_dir, "artifacts/reference-final-review/*-final-review.json"
    )
    artifacts["delivery_manifest"] = _latest(
        project_dir, "deliveries/*/delivery-manifest.json"
    )
    artifacts["production_plan"] = _latest(project_dir, "artifacts/*-production-plan.json")
    artifacts["approved_package"] = _latest(
        project_dir, "artifacts/reference-review/*-approved-package.json"
    )
    return artifacts


def _next_commands(status: str, current_path: Path | None, project_dir: Path) -> list[dict[str, str]]:
    current = current_path or Path("<replication-package.json>")
    production_plan = current_path or project_dir / "artifacts" / "<reference>-seedance-production-plan.json"
    if status == "empty_project":
        return [
            {
                "name": "analyze_reference",
                "script": "scripts/reference_preview_pipeline.py",
                "command": _command(
                    ".venv/bin/python",
                    "scripts/reference_preview_pipeline.py",
                    "<video-url-or-local-path>",
                    "--project-dir",
                    project_dir,
                ),
            }
        ]
    if status == "source_imported_needs_analysis":
        payload = _safe_read_json(current_path) or {}
        local_video_path = str(payload.get("local_video_path") or "<local-video-path>")
        return [
            {
                "name": "analyze_imported_reference",
                "script": "scripts/reference_preview_pipeline.py",
                "command": _command(
                    ".venv/bin/python",
                    "scripts/reference_preview_pipeline.py",
                    local_video_path,
                    "--project-dir",
                    project_dir,
                ),
            }
        ]
    if status in {"analysis_ready_needs_prompt_or_edit", "prompts_reversed_needs_edit"}:
        commands = []
        if status == "analysis_ready_needs_prompt_or_edit":
            commands.append(
                {
                    "name": "optional_doubao_prompt_reverse",
                    "script": "scripts/reverse_reference_prompts.py",
                    "command": _command(
                        ".venv/bin/python",
                        "scripts/reverse_reference_prompts.py",
                        current,
                        "--project-dir",
                        project_dir,
                        "--provider",
                        "doubao",
                    ),
                }
            )
        commands.append(_review_wizard_command(project_dir))
        commands.extend(_edit_asset_approval_commands(current, project_dir))
        return commands
    if status in {"edited_needs_assets_or_approval", "assets_bound_needs_approval"}:
        commands = _edit_asset_approval_commands(current, project_dir)
        return (
            [_review_wizard_command(project_dir), *commands[1:]]
            if status == "edited_needs_assets_or_approval"
            else [_review_wizard_command(project_dir), *commands[2:]]
        )
    if status == "approved_for_production":
        return [
            _demo_report_command(project_dir),
            {
                "name": "preview_seedance_dry_run",
                "script": "scripts/preview_reference_seedance.py",
                "command": _command(
                    ".venv/bin/python",
                    "scripts/preview_reference_seedance.py",
                    current,
                    "--project-dir",
                    project_dir,
                    "--duration",
                    "15",
                    "--resolution",
                    "480p",
                    "--batch-size",
                    "1",
                    "--provider",
                    "runninghub",
                ),
            }
        ]
    if status == "production_plan_ready":
        return [
            {
                "name": "create_seedance_dry_run",
                "script": "scripts/plan_seedance_batch.py",
                "command": _command(
                    ".venv/bin/python",
                    "scripts/plan_seedance_batch.py",
                    production_plan,
                    "--project-dir",
                    project_dir,
                    "--provider",
                    "runninghub",
                ),
            }
        ]
    if status == "seedance_dry_run_ready":
        plan_path = _latest(project_dir, "artifacts/*-production-plan.json")
        return [
            _final_edit_command(current, project_dir),
            {
                "name": "run_one_paid_seedance_sample",
                "script": "scripts/plan_seedance_batch.py",
                "command": _command(
                    ".venv/bin/python",
                    "scripts/plan_seedance_batch.py",
                    plan_path or production_plan,
                    "--project-dir",
                    project_dir,
                    "--provider",
                    "runninghub",
                    "--execute",
                    "--allow-paid-generation",
                    "--approval-phrase",
                    "RUN SEEDANCE SAMPLE",
                ),
            }
        ]
    if status == "seedance_sample_generated":
        return [
            _final_edit_command(current, project_dir),
            {
                "name": "review_sample_before_more_generation",
                "script": "manual_review",
                "command": "Review the generated sample clip before approving any remaining paid tasks.",
            }
        ]
    if status == "final_edit_ready_for_compose":
        should_mix_audio = _final_edit_has_valid_audio_tracks(current, project_dir)
        return [
            _compose_final_command(current, project_dir, dry_run=True),
            _compose_final_command(
                current,
                project_dir,
                dry_run=False,
                mix_audio=should_mix_audio,
            ),
        ]
    if status == "final_render_ready":
        return [
            _review_final_render_command(current, project_dir),
            _export_delivery_command(current, project_dir),
        ]
    if status == "final_review_ready_for_delivery":
        render_report_path = _source_render_report_for_review(current, project_dir)
        return [
            _export_delivery_command(render_report_path or current, project_dir),
        ]
    if status == "delivery_exported":
        return [
            {
                "name": "archive_or_upload_delivery",
                "script": "manual_review",
                "command": "Archive or upload the delivery folder after final business approval.",
            }
        ]
    return []


def _edit_asset_approval_commands(current: Path, project_dir: Path) -> list[dict[str, str]]:
    return [
        {
            "name": "edit_copy_and_prompts",
            "script": "scripts/edit_reference_package.py",
            "command": _command(
                ".venv/bin/python",
                "scripts/edit_reference_package.py",
                current,
                "--project-dir",
                project_dir,
                "--rewrite-text",
                "人工修改后的复刻文案",
            ),
        },
        {
            "name": "bind_team_assets",
            "script": "scripts/bind_reference_assets.py",
            "command": _command(
                ".venv/bin/python",
                "scripts/bind_reference_assets.py",
                current,
                "--project-dir",
                project_dir,
                "--asset",
                "/path/to/team-face.png",
                "s1",
                "subject_or_face_reference",
                "face-ref",
                "--authorized",
            ),
        },
        {
            "name": "preview_seedance_approval_readiness",
            "script": "scripts/preview_reference_approval.py",
            "command": _command(
                ".venv/bin/python",
                "scripts/preview_reference_approval.py",
                current,
                "--project-dir",
                project_dir,
                "--target-mode",
                "seedance",
                "--duration",
                "15",
                "--resolution",
                "480p",
                "--batch-size",
                "1",
            ),
        },
        {
            "name": "approve_for_seedance",
            "script": "scripts/approve_reference_package.py",
            "command": _command(
                ".venv/bin/python",
                "scripts/approve_reference_package.py",
                current,
                "--project-dir",
                project_dir,
                "--target-mode",
                "seedance",
                "--reviewer",
                "operator",
                "--approval-phrase",
                "APPROVE REFERENCE PACKAGE",
            ),
        },
    ]


def _review_wizard_command(project_dir: Path) -> dict[str, str]:
    return {
        "name": "local_review_wizard",
        "script": "scripts/reference_review_wizard.py",
        "command": _command(
            ".venv/bin/python",
            "scripts/reference_review_wizard.py",
            project_dir,
        ),
    }


def _demo_report_command(project_dir: Path) -> dict[str, str]:
    return {
        "name": "local_demo_report",
        "script": "scripts/reference_demo_report.py",
        "command": _command(
            ".venv/bin/python",
            "scripts/reference_demo_report.py",
            project_dir,
        ),
    }


def _final_edit_command(seedance_batch_path: Path, project_dir: Path) -> dict[str, str]:
    return {
        "name": "preview_final_edit_readiness",
        "script": "scripts/preview_reference_final_edit.py",
        "command": _command(
            ".venv/bin/python",
            "scripts/preview_reference_final_edit.py",
            seedance_batch_path,
            "--project-dir",
            project_dir,
        ),
    }


def _compose_final_command(
    final_edit_plan_path: Path,
    project_dir: Path,
    *,
    dry_run: bool,
    mix_audio: bool = False,
) -> dict[str, str]:
    parts: list[str | Path] = [
        ".venv/bin/python",
        "scripts/compose_reference_final.py",
        final_edit_plan_path,
        "--project-dir",
        project_dir,
    ]
    if dry_run:
        parts.append("--dry-run")
    else:
        parts.append("--burn-subtitles")
        if mix_audio:
            parts.append("--mix-audio")
    return {
        "name": "dry_run_final_compose" if dry_run else "compose_final_video",
        "script": "scripts/compose_reference_final.py",
        "command": _command(*parts),
    }


def _export_delivery_command(render_report_path: Path, project_dir: Path) -> dict[str, str]:
    return {
        "name": "export_delivery_package",
        "script": "scripts/export_reference_delivery.py",
        "command": _command(
            ".venv/bin/python",
            "scripts/export_reference_delivery.py",
            project_dir,
            "--render-report",
            render_report_path,
            "--reviewer",
            "operator",
            "--approval-phrase",
            "APPROVE FINAL DELIVERY",
        ),
    }


def _review_final_render_command(render_report_path: Path, project_dir: Path) -> dict[str, str]:
    return {
        "name": "review_final_render",
        "script": "scripts/review_reference_final.py",
        "command": _command(
            ".venv/bin/python",
            "scripts/review_reference_final.py",
            project_dir,
            "--render-report",
            render_report_path,
            "--reviewer",
            "operator",
        ),
    }


def _source_render_report_for_review(
    final_review_report_path: Path | None, project_dir: Path
) -> Path | None:
    payload = _safe_read_json(final_review_report_path)
    if not payload:
        return None
    value = str(payload.get("source_render_report_path") or "").strip()
    if not value:
        return None
    path = _resolve_project_path(project_dir, value)
    return path if path.is_file() else None


def _final_edit_has_valid_audio_tracks(final_edit_plan_path: Path | None, project_dir: Path) -> bool:
    payload = _safe_read_json(final_edit_plan_path)
    if not payload:
        return False
    handoff = payload.get("compose_handoff") if isinstance(payload.get("compose_handoff"), dict) else {}
    raw_tracks = handoff.get("audio_tracks") or payload.get("audio_tracks") or []
    if not isinstance(raw_tracks, list) or not raw_tracks:
        return False
    for raw_track in raw_tracks:
        if not isinstance(raw_track, dict):
            return False
        track_path = str(raw_track.get("path") or "").strip()
        if not track_path:
            return False
        if not _resolve_project_path(project_dir, track_path).is_file():
            return False
    return True


def _render_output_path(payload: dict[str, Any] | None, project_dir: Path) -> Path | None:
    render = (payload or {}).get("render")
    nested_output = render.get("output_path") if isinstance(render, dict) else None
    output_value = str((payload or {}).get("output_path") or nested_output or "").strip()
    if not output_value:
        return None
    return _resolve_project_path(project_dir, output_value)


def _render_field(payload: dict[str, Any] | None, key: str) -> Any:
    if not payload:
        return None
    if key in payload:
        return payload.get(key)
    render = payload.get("render")
    if isinstance(render, dict):
        return render.get(key)
    return None


def _render_report_is_ready(render_report: Path | None, project_dir: Path) -> bool:
    payload = _safe_read_json(render_report)
    output_path = _render_output_path(payload, project_dir)
    return bool(
        render_report
        and payload
        and payload.get("status") == "rendered"
        and payload.get("dry_run") is False
        and output_path
        and output_path.is_file()
    )


def _final_review_is_ready(final_review_report: Path | None, project_dir: Path) -> bool:
    payload = _safe_read_json(final_review_report)
    output_path = _render_output_path(payload, project_dir)
    return bool(
        final_review_report
        and payload
        and payload.get("status") == "final_review_ready_for_delivery"
        and output_path
        and output_path.is_file()
        and _source_render_report_for_review(final_review_report, project_dir)
    )


def _current_status(artifacts: dict[str, Path | None], project_dir: Path) -> tuple[str, Path | None]:
    delivery_manifest = artifacts.get("delivery_manifest")
    delivery_payload = _safe_read_json(delivery_manifest)
    if delivery_manifest and (delivery_payload or {}).get("status") == "ready_for_distribution":
        return "delivery_exported", delivery_manifest

    final_review_report = artifacts.get("final_review_report")
    if _final_review_is_ready(final_review_report, project_dir):
        return "final_review_ready_for_delivery", final_review_report

    render_report = artifacts.get("render_report")
    if _render_report_is_ready(render_report, project_dir):
        return "final_render_ready", render_report

    final_edit_plan = artifacts.get("final_edit_plan")
    final_edit_payload = _safe_read_json(final_edit_plan)
    if final_edit_plan and (final_edit_payload or {}).get("status") == "ready_for_compose":
        return "final_edit_ready_for_compose", final_edit_plan
    for status, _pattern in ARTIFACT_PATTERNS:
        path = artifacts.get(status)
        if path:
            return status, path
    return "empty_project", None


def inspect_project(project_dir: str | Path) -> dict[str, Any]:
    project_path = Path(project_dir).expanduser().resolve()
    artifacts = _find_artifacts(project_path)
    status, current_path = _current_status(artifacts, project_path)
    production_plan = artifacts.get("production_plan")
    payload = _safe_read_json(current_path)
    render_output_path = _render_output_path(payload, project_path)
    return {
        "project_dir": str(project_path),
        "status": status,
        "current_artifact_path": str(current_path) if current_path else None,
        "production_plan_path": str(production_plan) if production_plan else None,
        "approval_status": ((payload or {}).get("approval") or {}).get("status"),
        "target_mode": (payload or {}).get("target_mode")
        or ((payload or {}).get("approval") or {}).get("target_mode"),
        "paid_generation_started": ((payload or {}).get("approval") or {}).get(
            "paid_generation_started"
        ),
        "render_output_path": str(render_output_path) if render_output_path else None,
        "render_output_exists": render_output_path.is_file() if render_output_path else None,
        "burned_subtitles": _render_field(payload, "burned_subtitles"),
        "mixed_audio": _render_field(payload, "mixed_audio"),
        "mixed_audio_path": _render_field(payload, "mixed_audio_path"),
        "delivery_dir": (payload or {}).get("delivery_dir"),
        "delivery_video_path": (payload or {}).get("video_path"),
        "next_commands": _next_commands(status, current_path, project_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Reference-video project directory")
    args = parser.parse_args(argv)
    print(json.dumps(inspect_project(args.project_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
