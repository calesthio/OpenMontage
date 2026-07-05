"""Run reference analysis and optional prompt reverse in one safe preview step."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_reference_video import ReferenceDownloadError, analyze_reference_source
from tools.analysis.reference_prompt_reverse import ReferencePromptReverse


def _project_dir_from(package_path: str, explicit_project_dir: str | None) -> Path:
    if explicit_project_dir:
        return Path(explicit_project_dir).expanduser().resolve()
    path = Path(package_path).expanduser().resolve()
    if path.parent.name == "artifacts":
        return path.parent.parent
    return path.parent


def _command(*parts: str) -> str:
    return " ".join(parts)


def _next_steps(package_path: str, project_dir: Path) -> list[dict[str, str]]:
    package = str(package_path)
    project = str(project_dir)
    return [
        {
            "name": "edit_copy_and_prompts",
            "script": "scripts/edit_reference_package.py",
            "command": _command(
                ".venv/bin/python",
                "scripts/edit_reference_package.py",
                package,
                "--project-dir",
                project,
                '--rewrite-text "人工修改后的复刻文案"',
            ),
        },
        {
            "name": "bind_team_assets",
            "script": "scripts/bind_reference_assets.py",
            "command": _command(
                ".venv/bin/python",
                "scripts/bind_reference_assets.py",
                package,
                "--project-dir",
                project,
                "--asset",
                "/path/to/team-face.png",
                "s1",
                "subject_or_face_reference",
                "face-ref",
                "--authorized",
            ),
        },
        {
            "name": "approve_for_seedance",
            "script": "scripts/approve_reference_package.py",
            "command": _command(
                ".venv/bin/python",
                "scripts/approve_reference_package.py",
                package,
                "--project-dir",
                project,
                "--target-mode",
                "seedance",
                "--reviewer",
                "operator",
                '--approval-phrase "APPROVE REFERENCE PACKAGE"',
            ),
        },
        {
            "name": "preview_seedance_dry_run_after_approval",
            "script": "scripts/preview_reference_seedance.py",
            "command": _command(
                ".venv/bin/python",
                "scripts/preview_reference_seedance.py",
                "projects/<project>/artifacts/reference-review/<reference>-seedance-approved-package.json",
                "--project-dir",
                project,
                "--duration",
                "15",
                "--resolution",
                "480p",
                "--batch-size",
                "1",
                "--provider",
                "runninghub",
            ),
        },
    ]


def _run_prompt_reverse(args: argparse.Namespace, package_path: str) -> dict[str, Any]:
    result = ReferencePromptReverse().execute(
        {
            "project_dir": args.project_dir,
            "replication_package_path": package_path,
            "provider": args.provider,
            "max_keyframes_per_scene": args.max_keyframes_per_scene,
            "max_tokens": args.max_tokens,
            **({"model": args.model} if args.model else {}),
            **({"output_dir": args.prompt_output_dir} if args.prompt_output_dir else {}),
        }
    )
    if not result.success:
        raise RuntimeError(result.error or "Reference prompt reverse failed")
    return {
        "enabled": True,
        "provider": args.provider,
        "replication_package_path": result.data["json_path"],
        "scene_results": result.data.get("scene_results", []),
    }


def _payload(
    *,
    source: str,
    project_dir: Path,
    analysis_result: dict[str, Any],
    prompt_reverse: dict[str, Any],
) -> dict[str, Any]:
    package_path = prompt_reverse.get("replication_package_path") or analysis_result["json_path"]
    return {
        "status": "ready_for_human_edit",
        "source": source,
        "project_dir": str(project_dir),
        "replication_package_path": package_path,
        "markdown_review_path": analysis_result.get("markdown_path"),
        "prompt_reverse": prompt_reverse,
        "paid_generation_started": False,
        "next_steps": _next_steps(package_path, project_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Local reference video path or video URL")
    parser.add_argument("--project-dir", help="Output project directory")
    parser.add_argument(
        "--reverse-prompts",
        action="store_true",
        help="Call a configured vision provider to reverse Seedance prompts from keyframes.",
    )
    parser.add_argument(
        "--provider",
        choices=["doubao"],
        default="doubao",
        help="Vision provider used when --reverse-prompts is set. Defaults to doubao.",
    )
    parser.add_argument("--model", help="Optional vision provider model or endpoint id")
    parser.add_argument(
        "--max-keyframes-per-scene",
        type=int,
        default=3,
        help="Maximum keyframes sent to the vision model per scene.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum output tokens requested from the vision model.",
    )
    parser.add_argument("--prompt-output-dir", help="Optional prompt-reverse artifact directory")
    args = parser.parse_args(argv)

    try:
        project_dir_arg = Path(args.project_dir) if args.project_dir else None
        analysis_result = analyze_reference_source(args.source, project_dir=project_dir_arg)
        project_dir = _project_dir_from(analysis_result["json_path"], args.project_dir)
        args.project_dir = str(project_dir)
        prompt_reverse = {"enabled": False}
        if args.reverse_prompts:
            prompt_reverse = _run_prompt_reverse(args, analysis_result["json_path"])
        print(
            json.dumps(
                _payload(
                    source=args.source,
                    project_dir=project_dir,
                    analysis_result=analysis_result,
                    prompt_reverse=prompt_reverse,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except ReferenceDownloadError as exc:
        print(json.dumps(exc.to_payload(), ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Reference preview pipeline failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
