"""Run a safe local reference-video demo from source to human-edit handoff.

This runner intentionally stops before approval and paid generation. It analyzes
the reference source, optionally reverses editable prompts with a configured
vision provider, writes the local demo report, and prints the safest next steps.
"""

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

from scripts.analyze_reference_video import ReferenceDownloadError, analyze_reference_source
from scripts.reference_demo_preflight import run_preflight
from scripts.reference_demo_report import build_demo_report
from scripts.reference_project_status import inspect_project
from tools.analysis.reference_prompt_reverse import ReferencePromptReverse
from tools.video.seedance_constraints import DEFAULT_DURATION, DEFAULT_RESOLUTION


def _quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def _command(*parts: str | Path) -> str:
    return " ".join(_quote(part) for part in parts)


def _project_dir_from(package_path: str | Path, explicit_project_dir: str | Path | None) -> Path:
    if explicit_project_dir:
        return Path(explicit_project_dir).expanduser().resolve()
    path = Path(package_path).expanduser().resolve()
    if path.parent.name == "artifacts":
        return path.parent.parent
    return path.parent


def _run_prompt_reverse(
    *,
    project_dir: Path,
    package_path: str,
    provider: str,
    model: str | None,
    max_keyframes_per_scene: int,
    max_tokens: int,
) -> dict[str, Any]:
    result = ReferencePromptReverse().execute(
        {
            "project_dir": str(project_dir),
            "replication_package_path": package_path,
            "provider": provider,
            "max_keyframes_per_scene": max_keyframes_per_scene,
            "max_tokens": max_tokens,
            **({"model": model} if model else {}),
        }
    )
    if not result.success:
        raise RuntimeError(result.error or "Reference prompt reverse failed")
    return {
        "enabled": True,
        "provider": provider,
        "replication_package_path": result.data["json_path"],
        "scene_results": result.data.get("scene_results", []),
    }


def _next_command_hint(project_dir: Path, package_path: str) -> list[dict[str, str]]:
    return [
        {
            "name": "open_review_wizard",
            "script": "scripts/reference_review_wizard.py",
            "command": _command(
                ".venv/bin/python",
                "scripts/reference_review_wizard.py",
                project_dir,
            ),
        },
        {
            "name": "edit_exported_sheet",
            "script": "manual_review",
            "command": "Edit the exported JSON sheet, then rerun reference_review_wizard.py with --edit-sheet.",
        },
        {
            "name": "inspect_project_status",
            "script": "scripts/reference_project_status.py",
            "command": _command(
                ".venv/bin/python",
                "scripts/reference_project_status.py",
                project_dir,
            ),
        },
        {
            "name": "manual_package_path",
            "script": "manual_review",
            "command": f"Current editable package: {package_path}",
        },
    ]


def run_local_demo(
    *,
    source: str,
    project_dir: str | Path | None = None,
    reverse_prompts: bool = False,
    provider: str = "doubao",
    model: str | None = None,
    max_keyframes_per_scene: int = 3,
    max_tokens: int = 4096,
    duration: str = DEFAULT_DURATION,
    resolution: str = DEFAULT_RESOLUTION,
    batch_size: int = 1,
    seedance_provider: str = "runninghub",
    model_variant: str = "sparkvideo-2.0-mini",
    aspect_ratio: str = "9:16",
    generate_audio: bool = True,
    skip_preflight: bool = False,
) -> dict[str, Any]:
    explicit_project_dir = Path(project_dir).expanduser().resolve() if project_dir else None
    preflight = {"status": "skipped", "issues": []}
    if explicit_project_dir and not skip_preflight:
        preflight = run_preflight(
            source=source,
            project_dir=explicit_project_dir,
            reverse_prompts=reverse_prompts,
            seedance_provider=seedance_provider,
        )
        if preflight.get("status") == "blocked":
            raise RuntimeError(f"preflight blocked reference demo: {preflight.get('issues', [])}")

    analysis_result = analyze_reference_source(source, project_dir=explicit_project_dir)
    resolved_project_dir = _project_dir_from(analysis_result["json_path"], explicit_project_dir)

    prompt_reverse: dict[str, Any] = {"enabled": False}
    package_path = str(analysis_result["json_path"])
    if reverse_prompts:
        prompt_reverse = _run_prompt_reverse(
            project_dir=resolved_project_dir,
            package_path=package_path,
            provider=provider,
            model=model,
            max_keyframes_per_scene=max_keyframes_per_scene,
            max_tokens=max_tokens,
        )
        package_path = str(prompt_reverse["replication_package_path"])

    demo_report = build_demo_report(
        project_dir=resolved_project_dir,
        duration=duration,
        resolution=resolution,
        batch_size=batch_size,
        provider=seedance_provider,
        model_variant=model_variant,
        aspect_ratio=aspect_ratio,
        generate_audio=generate_audio,
    )
    status = inspect_project(resolved_project_dir)
    paid_generation_started = bool(
        (demo_report.get("seedance_preview") or {}).get("paid_generation_started")
    )

    return {
        "status": "ready_for_human_edit",
        "source": source,
        "project_dir": str(resolved_project_dir),
        "replication_package_path": package_path,
        "markdown_review_path": analysis_result.get("markdown_path"),
        "prompt_reverse": prompt_reverse,
        "demo_report": {
            "json_report_path": demo_report.get("json_report_path"),
            "markdown_report_path": demo_report.get("markdown_report_path"),
            "seedance_preview_status": (demo_report.get("seedance_preview") or {}).get("status"),
        },
        "preflight": preflight,
        "project_status": status,
        "paid_generation_started": paid_generation_started,
        "safety": {
            "local_only": not reverse_prompts,
            "paid_generation_started": paid_generation_started,
            "approved_package_written": False,
            "requires_team_authorized_assets": True,
        },
        "next_commands": _next_command_hint(resolved_project_dir, package_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Local reference video path or video URL")
    parser.add_argument("--project-dir", help="Output project directory")
    parser.add_argument(
        "--reverse-prompts",
        action="store_true",
        help="Call a configured vision provider to reverse editable Seedance prompts.",
    )
    parser.add_argument("--provider", choices=["doubao"], default="doubao")
    parser.add_argument("--model", help="Optional Doubao/Ark model or endpoint id")
    parser.add_argument("--max-keyframes-per-scene", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument(
        "--duration",
        default=DEFAULT_DURATION,
        choices=[str(seconds) for seconds in range(4, 16)],
        help="Seedance preview duration. Defaults to 15.",
    )
    parser.add_argument(
        "--resolution",
        default=DEFAULT_RESOLUTION,
        choices=["480p", "720p"],
        help="Seedance preview resolution. Defaults to 480p.",
    )
    parser.add_argument("--batch-size", type=int, default=1, help="Seedance preview batch size. Max 5.")
    parser.add_argument(
        "--seedance-provider",
        choices=["runninghub", "fal", "replicate"],
        default="runninghub",
        help="Provider task shape for the dry-run preview.",
    )
    parser.add_argument("--model-variant", default="sparkvideo-2.0-mini")
    parser.add_argument(
        "--aspect-ratio",
        choices=["adaptive", "16:9", "4:3", "1:1", "3:4", "9:16", "21:9"],
        default="9:16",
    )
    parser.add_argument("--no-audio", action="store_true", help="Set generate_audio=false.")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip local readiness checks.")
    args = parser.parse_args(argv)

    try:
        payload = run_local_demo(
            source=args.source,
            project_dir=args.project_dir,
            reverse_prompts=args.reverse_prompts,
            provider=args.provider,
            model=args.model,
            max_keyframes_per_scene=args.max_keyframes_per_scene,
            max_tokens=args.max_tokens,
            duration=args.duration,
            resolution=args.resolution,
            batch_size=args.batch_size,
            seedance_provider=args.seedance_provider,
            model_variant=args.model_variant,
            aspect_ratio=args.aspect_ratio,
            generate_audio=not args.no_audio,
            skip_preflight=args.skip_preflight,
        )
    except ReferenceDownloadError as exc:
        print(json.dumps(exc.to_payload(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Reference local demo failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
