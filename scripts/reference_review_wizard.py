"""Run the local review loop for a reference-video package.

The wizard is intentionally local-only: it can export an edit sheet, validate and
apply that sheet, and preview approval readiness. It never approves production
and never calls paid generation providers.
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

from scripts.apply_reference_edit_sheet import (
    _load_json,
    apply_edit_sheet,
    validate_edit_sheet,
)
from scripts.export_reference_edit_sheet import write_edit_sheet
from scripts.preview_reference_approval import preview_approval
from scripts.reference_project_status import inspect_project
from tools.analysis.reference_target_modes import SUPPORTED_REFERENCE_TARGET_MODES
from tools.video.seedance_constraints import DEFAULT_DURATION, DEFAULT_RESOLUTION


def _quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def _command(*parts: str | Path) -> str:
    return " ".join(_quote(part) for part in parts)


def _load_package(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("replication package must be a JSON object")
    return data


def _paid_generation_started(paths: list[Path]) -> bool:
    for path in paths:
        try:
            package = _load_package(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if ((package.get("approval") or {}).get("paid_generation_started")) is True:
            return True
    return False


def _safety(project_dir: Path, package_paths: list[Path]) -> dict[str, bool]:
    return {
        "paid_generation_started": _paid_generation_started(package_paths),
        "approved_package_written": any(
            project_dir.glob("artifacts/reference-review/*-approved-package.json")
        ),
    }


def _edit_sheet_payload(
    *,
    package: dict[str, Any],
    package_path: Path,
    project_dir: Path,
    output_path: str | Path | None,
) -> dict[str, str]:
    edit_sheet_path = write_edit_sheet(
        package=package,
        project_dir=project_dir,
        output_path=output_path,
    )
    return {
        "path": str(edit_sheet_path),
        "apply_command": _command(
            ".venv/bin/python",
            "scripts/reference_review_wizard.py",
            project_dir,
            "--edit-sheet",
            edit_sheet_path,
        ),
        "validate_only_command": _command(
            ".venv/bin/python",
            "scripts/apply_reference_edit_sheet.py",
            package_path,
            "--project-dir",
            project_dir,
            "--edit-sheet",
            edit_sheet_path,
            "--validate-only",
        ),
    }


def run_wizard(
    *,
    project_dir: str | Path,
    edit_sheet_path: str | Path | None = None,
    output_edit_sheet: str | Path | None = None,
    target_mode: str = "seedance",
    duration: str = DEFAULT_DURATION,
    resolution: str = DEFAULT_RESOLUTION,
    batch_size: int = 1,
) -> tuple[dict[str, Any], int]:
    project_path = Path(project_dir).expanduser().resolve()
    status = inspect_project(project_path)
    current_artifact = status.get("current_artifact_path")
    result: dict[str, Any] = {
        "project_dir": str(project_path),
        "status": status,
    }

    if not current_artifact:
        result["next_step"] = "analyze_reference_first"
        result["safety"] = _safety(project_path, [])
        return result, 1

    current_path = Path(current_artifact)
    package_paths = [current_path]

    if edit_sheet_path:
        package = _load_package(current_path)
        edit_sheet = _load_json(edit_sheet_path)
        validation = validate_edit_sheet(package, edit_sheet)
        result["edit_sheet_validation"] = validation
        if not validation["valid"]:
            result["next_step"] = "fix_edit_sheet"
            result["safety"] = _safety(project_path, package_paths)
            return result, 1

        applied = apply_edit_sheet(
            replication_package_path=str(current_path),
            project_dir=str(project_path),
            edit_sheet=edit_sheet,
        )
        applied_path = Path(applied["replication_package_path"])
        package_paths.append(applied_path)
        result["applied_edit_sheet"] = applied
        result["approval_preview"] = preview_approval(
            _load_package(applied_path),
            target_mode=target_mode,
            duration=duration,
            resolution=resolution,
            batch_size=batch_size,
        )
        result["next_step"] = result["approval_preview"]["next_step"]
        result["safety"] = _safety(project_path, package_paths)
        return result, 0 if result["approval_preview"]["ready_to_approve"] else 1

    if status["status"] == "assets_bound_needs_approval":
        result["approval_preview"] = preview_approval(
            _load_package(current_path),
            target_mode=target_mode,
            duration=duration,
            resolution=resolution,
            batch_size=batch_size,
        )
        result["next_step"] = result["approval_preview"]["next_step"]
        result["safety"] = _safety(project_path, package_paths)
        return result, 0 if result["approval_preview"]["ready_to_approve"] else 1

    result["edit_sheet"] = _edit_sheet_payload(
        package=_load_package(current_path),
        package_path=current_path,
        project_dir=project_path,
        output_path=output_edit_sheet,
    )
    result["next_step"] = "edit_sheet_ready_for_human"
    result["safety"] = _safety(project_path, package_paths)
    return result, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", help="Reference-video project directory")
    parser.add_argument("--edit-sheet", help="Apply this JSON edit sheet before previewing approval")
    parser.add_argument("--output-edit-sheet", help="Optional path for exported edit-sheet template")
    parser.add_argument(
        "--target-mode",
        choices=list(SUPPORTED_REFERENCE_TARGET_MODES),
        default="seedance",
        help="Downstream mode to preview. Reference-video v1 supports Seedance only.",
    )
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
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Seedance batch size to preview. Maximum 5.",
    )
    args = parser.parse_args(argv)

    try:
        payload, exit_code = run_wizard(
            project_dir=args.project_dir,
            edit_sheet_path=args.edit_sheet,
            output_edit_sheet=args.output_edit_sheet,
            target_mode=args.target_mode,
            duration=args.duration,
            resolution=args.resolution,
            batch_size=args.batch_size,
        )
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
