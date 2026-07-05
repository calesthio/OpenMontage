"""Write a local end-to-end demo report for a reference-video project.

The report is safe to run during demos: it may export an edit sheet, preview
approval readiness, and create a Seedance dry-run task list from an already
approved package. It never writes an approved package and never starts paid
generation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reference_project_status import inspect_project
from scripts.reference_review_wizard import run_wizard
from scripts.preview_reference_final_edit import write_final_edit_preview
from tools.analysis.reference_production_plan import ReferenceProductionPlan
from tools.video.seedance_batch import SeedanceBatch
from tools.video.seedance_constraints import DEFAULT_DURATION, DEFAULT_RESOLUTION


def _load_package(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("replication package must be a JSON object")
    return data


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-demo"


def _source_name(status: dict[str, Any], project_dir: Path) -> str:
    artifact_path = status.get("current_artifact_path")
    if artifact_path:
        try:
            package = _load_package(artifact_path)
            source = package.get("source") or {}
            return _safe_slug(
                Path(str(source.get("local_video_path") or source.get("input") or "")).stem
            )
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return _safe_slug(project_dir.name)


def _report_output_paths(
    *,
    project_dir: Path,
    output_dir: str | Path | None,
    source_name: str,
) -> tuple[Path, Path]:
    report_dir = Path(output_dir) if output_dir else project_dir / "artifacts" / "reference-demo-report"
    report_dir.mkdir(parents=True, exist_ok=True)
    return (
        report_dir / f"{source_name}-demo-report.md",
        report_dir / f"{source_name}-demo-report.json",
    )


def _run_seedance_dry_run(
    *,
    project_dir: Path,
    approved_package_path: Path,
    duration: str,
    resolution: str,
    batch_size: int,
    provider: str,
    model_variant: str,
    aspect_ratio: str,
    generate_audio: bool,
) -> dict[str, Any]:
    production_result = ReferenceProductionPlan().execute(
        {
            "project_dir": str(project_dir),
            "replication_package_path": str(approved_package_path),
            "target_mode": "seedance",
            "duration": duration,
            "resolution": resolution,
            "batch_size": batch_size,
        }
    )
    if not production_result.success:
        return {
            "status": "production_plan_failed",
            "error": production_result.error or "Reference production plan failed",
            "dry_run": False,
            "paid_generation_started": False,
        }

    batch_result = SeedanceBatch().execute(
        {
            "project_dir": str(project_dir),
            "production_plan": production_result.data["production_plan"],
            "provider": provider,
            "model_variant": model_variant,
            "aspect_ratio": aspect_ratio,
            "generate_audio": generate_audio,
            "dry_run": True,
            "allow_paid_generation": False,
        }
    )
    if not batch_result.success:
        return {
            "status": "seedance_dry_run_failed",
            "error": batch_result.error or "Seedance dry-run preview failed",
            "production_plan_path": production_result.data["json_path"],
            "dry_run": False,
            "paid_generation_started": False,
        }

    return {
        "status": "ready",
        "dry_run": True,
        "paid_generation_started": False,
        "production_plan_path": production_result.data["json_path"],
        "seedance_batch_path": batch_result.data["json_path"],
        "production_plan": production_result.data["production_plan"],
        "seedance_batch": batch_result.data["seedance_batch"],
    }


def _next_command(status: dict[str, Any]) -> str:
    commands = status.get("next_commands") or []
    if not commands:
        return "No next command suggested."
    return str(commands[0].get("command") or commands[0].get("name") or "")


def _seedance_summary(seedance_preview: dict[str, Any]) -> tuple[str, list[str]]:
    if seedance_preview.get("status") == "ready":
        batch = seedance_preview.get("seedance_batch") or {}
        tasks = batch.get("tasks") or []
        provider_tools = sorted(
            {
                str(task.get("provider_tool"))
                for task in tasks
                if str(task.get("provider_tool", "")).strip()
            }
        )
        return (
            "Seedance dry-run: ready",
            [
                f"- Dry-run task count: {len(tasks)}",
                f"- Provider tools: {', '.join(provider_tools) if provider_tools else 'n/a'}",
                f"- Batch path: `{seedance_preview.get('seedance_batch_path')}`",
            ],
        )
    if seedance_preview.get("status") == "blocked_until_approval":
        return (
            "Seedance dry-run: blocked until approval",
            [
                "- Reason: approve the edited reference package before local Seedance planning.",
                f"- Next command: `{seedance_preview.get('next_command', '')}`",
            ],
        )
    return (
        f"Seedance dry-run: {seedance_preview.get('status', 'unknown')}",
        [f"- Error: {seedance_preview.get('error', 'n/a')}"],
    )


def _markdown_report(payload: dict[str, Any]) -> str:
    status = payload["status"]
    seedance_title, seedance_lines = _seedance_summary(payload["seedance_preview"])
    final_edit_preview = payload.get("final_edit_preview") or {}
    final_edit_plan = final_edit_preview.get("final_edit_plan") or {}
    review_wizard = payload.get("review_wizard") or {}
    edit_sheet = review_wizard.get("edit_sheet") or {}
    approval_preview = review_wizard.get("approval_preview") or {}
    safety = payload["safety"]

    lines = [
        "# Reference Video Demo Report",
        "",
        "## Project",
        f"- Project dir: `{payload['project_dir']}`",
        f"- Current status: `{status.get('status')}`",
        f"- Current artifact: `{status.get('current_artifact_path')}`",
        f"- Paid generation: {'started' if safety.get('paid_generation_started') else 'not started'}",
        f"- Approved package written: {'yes' if safety.get('approved_package_written') else 'no'}",
        "",
        "## Human Review",
        f"- Wizard next step: `{review_wizard.get('next_step', 'n/a')}`",
        f"- Edit sheet: `{edit_sheet.get('path', 'n/a')}`",
        f"- Approval preview ready: `{approval_preview.get('ready_to_approve', 'n/a')}`",
        "",
        "## Seedance Preview",
        seedance_title,
        *seedance_lines,
        "",
        "## Final Edit Preview",
        f"- Final edit: {final_edit_plan.get('status', 'not_ready')}",
        f"- Missing clips: `{final_edit_plan.get('missing_clip_count', 'n/a')}`",
        f"- Plan path: `{final_edit_preview.get('json_path', 'n/a')}`",
        "",
        "## Suggested Next Step",
        f"`{_next_command(status)}`",
        "",
        "## Safety Notes",
        "- This report is local-only.",
        "- It does not approve production.",
        "- It does not call RunningHub, fal.ai, Replicate, Doubao, or any paid generation provider.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_demo_report(
    *,
    project_dir: str | Path,
    duration: str = DEFAULT_DURATION,
    resolution: str = DEFAULT_RESOLUTION,
    batch_size: int = 1,
    provider: str = "runninghub",
    model_variant: str = "sparkvideo-2.0-mini",
    aspect_ratio: str = "9:16",
    generate_audio: bool = True,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    project_path = Path(project_dir).expanduser().resolve()
    status = inspect_project(project_path)
    source_name = _source_name(status, project_path)
    markdown_path, json_path = _report_output_paths(
        project_dir=project_path,
        output_dir=output_dir,
        source_name=source_name,
    )

    review_wizard: dict[str, Any] | None = None
    seedance_preview: dict[str, Any]
    final_edit_preview: dict[str, Any] | None = None
    approved_package_path = status.get("current_artifact_path")
    if status.get("status") == "approved_for_production" and approved_package_path:
        seedance_preview = _run_seedance_dry_run(
            project_dir=project_path,
            approved_package_path=Path(approved_package_path),
            duration=duration,
            resolution=resolution,
            batch_size=batch_size,
            provider=provider,
            model_variant=model_variant,
            aspect_ratio=aspect_ratio,
            generate_audio=generate_audio,
        )
        if seedance_preview.get("status") == "ready" and seedance_preview.get("seedance_batch_path"):
            final_edit_preview = write_final_edit_preview(
                seedance_batch_path=seedance_preview["seedance_batch_path"],
                project_dir=project_path,
            )
    else:
        try:
            review_wizard, _exit_code = run_wizard(
                project_dir=project_path,
                target_mode="seedance",
                duration=duration,
                resolution=resolution,
                batch_size=batch_size,
            )
        except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
            review_wizard = {"next_step": "review_wizard_failed", "error": str(exc)}
        seedance_preview = {
            "status": "blocked_until_approval",
            "dry_run": False,
            "paid_generation_started": False,
            "next_command": _next_command(status),
        }

    payload = {
        "project_dir": str(project_path),
        "status": status,
        "review_wizard": review_wizard,
        "seedance_preview": seedance_preview,
        "final_edit_preview": final_edit_preview,
        "safety": {
            "paid_generation_started": bool(seedance_preview.get("paid_generation_started")),
            "approved_package_written": bool(status.get("approved_package_path")),
        },
        "markdown_report_path": str(markdown_path),
        "json_report_path": str(json_path),
    }
    markdown_path.write_text(_markdown_report(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Reference-video project directory")
    parser.add_argument(
        "--duration",
        default=DEFAULT_DURATION,
        choices=[str(seconds) for seconds in range(4, 16)],
        help="Seedance clip duration to preview. Defaults to 15.",
    )
    parser.add_argument(
        "--resolution",
        default=DEFAULT_RESOLUTION,
        choices=["480p", "720p"],
        help="Seedance resolution to preview. Defaults to 480p.",
    )
    parser.add_argument("--batch-size", type=int, default=1, help="Seedance batch size. Max 5.")
    parser.add_argument(
        "--provider",
        choices=["runninghub", "fal", "replicate"],
        default="runninghub",
        help="Seedance provider task shape to preview. Defaults to runninghub.",
    )
    parser.add_argument("--model-variant", default="sparkvideo-2.0-mini")
    parser.add_argument(
        "--aspect-ratio",
        choices=["adaptive", "16:9", "4:3", "1:1", "3:4", "9:16", "21:9"],
        default="9:16",
    )
    parser.add_argument("--no-audio", action="store_true", help="Set generate_audio=false.")
    parser.add_argument("--output-dir", help="Optional report output directory")
    args = parser.parse_args(argv)

    try:
        payload = build_demo_report(
            project_dir=args.project_dir,
            duration=args.duration,
            resolution=args.resolution,
            batch_size=args.batch_size,
            provider=args.provider,
            model_variant=args.model_variant,
            aspect_ratio=args.aspect_ratio,
            generate_audio=not args.no_audio,
            output_dir=args.output_dir,
        )
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
