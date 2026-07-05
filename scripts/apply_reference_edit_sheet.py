"""Apply a JSON edit sheet to a pending reference replication package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.reference_asset_binding import ReferenceAssetBinding
from tools.analysis.reference_text_edit import ReferenceTextEdit


APPROVED_STATUSES = {"approved", "approved_with_changes"}


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("edit_sheet must be a JSON object")
    return data


def _has_rewrite(sheet: dict[str, Any]) -> bool:
    return "rewrite_text" in sheet and str(sheet.get("rewrite_text", "")).strip() != ""


def _scene_edits(sheet: dict[str, Any]) -> list[dict[str, Any]]:
    scene_edits = sheet.get("scene_edits") or []
    if not isinstance(scene_edits, list):
        raise ValueError("edit_sheet.scene_edits must be a list")
    return [edit for edit in scene_edits if isinstance(edit, dict)]


def _has_scene_edits(sheet: dict[str, Any]) -> bool:
    return any(
        str(edit.get("script_text", "")).strip()
        or str(edit.get("seedance_prompt", "")).strip()
        for edit in _scene_edits(sheet)
    )


def _assets(sheet: dict[str, Any]) -> list[dict[str, Any]]:
    assets = sheet.get("assets") or []
    if not isinstance(assets, list):
        raise ValueError("edit_sheet.assets must be a list")
    return [asset for asset in assets if isinstance(asset, dict)]


def _has_assets(sheet: dict[str, Any]) -> bool:
    return bool(_assets(sheet))


def _validate_non_empty(sheet: dict[str, Any]) -> None:
    if not (_has_rewrite(sheet) or _has_scene_edits(sheet) or _has_assets(sheet)):
        raise ValueError("edit_sheet must include at least one rewrite_text, scene_edits, or assets entry")


def _scene_ids(package: dict[str, Any]) -> set[str]:
    return {
        str(scene.get("scene_id", "")).strip()
        for scene in package.get("scenes") or []
        if str(scene.get("scene_id", "")).strip()
    }


def _validation_error(errors: list[str], message: str) -> None:
    if message not in errors:
        errors.append(message)


def validate_edit_sheet(package: dict[str, Any], edit_sheet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    scene_ids = _scene_ids(package)
    approval_status = str((package.get("approval") or {}).get("status", ""))

    if approval_status in APPROVED_STATUSES:
        errors.append("Cannot apply an edit sheet to an already approved package")

    try:
        _validate_non_empty(edit_sheet)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        scene_edits = _scene_edits(edit_sheet)
    except ValueError as exc:
        scene_edits = []
        errors.append(str(exc))

    for index, edit in enumerate(scene_edits, start=1):
        scene_id = str(edit.get("scene_id", "")).strip()
        if not scene_id:
            _validation_error(errors, f"scene_edits[{index}] scene_id is required")
        elif scene_id not in scene_ids:
            _validation_error(errors, f"Unknown scene_id in scene_edits: {scene_id}")
        if not (
            str(edit.get("script_text", "")).strip()
            or str(edit.get("seedance_prompt", "")).strip()
        ):
            warnings.append(f"scene_edits[{index}] has no script_text or seedance_prompt")

    try:
        assets = _assets(edit_sheet)
    except ValueError as exc:
        assets = []
        errors.append(str(exc))

    for index, asset in enumerate(assets, start=1):
        scene_id = str(asset.get("scene_id", "")).strip()
        path = str(asset.get("path", "")).strip()
        if not path:
            _validation_error(errors, f"assets[{index}] path is required")
        elif not Path(path).expanduser().is_file():
            _validation_error(errors, f"Asset file not found: {path}")
        if not scene_id:
            _validation_error(errors, f"assets[{index}] scene_id is required")
        elif scene_id not in scene_ids:
            _validation_error(errors, f"Unknown scene_id in assets: {scene_id}")
        if asset.get("authorized") is not True:
            _validation_error(errors, f"assets[{index}] must set authorized=true")
        if not str(asset.get("id", "")).strip():
            warnings.append(f"assets[{index}] has no id; an automatic id may be generated")
        if not str(asset.get("role", "")).strip():
            warnings.append(f"assets[{index}] has no role; default reference_asset behavior may be used")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "would_apply": {
            "text_edits": _has_rewrite(edit_sheet) or _has_scene_edits(edit_sheet),
            "assets": bool(assets),
        },
    }


def apply_edit_sheet(
    *,
    replication_package_path: str,
    project_dir: str,
    edit_sheet: dict[str, Any],
) -> dict[str, Any]:
    _validate_non_empty(edit_sheet)

    current_path = replication_package_path
    text_edit_path: str | None = None
    asset_bound_path: str | None = None
    applied_text_edits = _has_rewrite(edit_sheet) or _has_scene_edits(edit_sheet)
    applied_assets = _has_assets(edit_sheet)

    if applied_text_edits:
        text_result = ReferenceTextEdit().execute(
            {
                "project_dir": project_dir,
                "replication_package_path": current_path,
                **({"rewrite_text": edit_sheet["rewrite_text"]} if _has_rewrite(edit_sheet) else {}),
                "scene_edits": _scene_edits(edit_sheet),
            }
        )
        if not text_result.success:
            raise RuntimeError(text_result.error or "Reference text edit failed")
        text_edit_path = text_result.data["json_path"]
        current_path = text_edit_path

    if applied_assets:
        asset_result = ReferenceAssetBinding().execute(
            {
                "project_dir": project_dir,
                "replication_package_path": current_path,
                "assets": _assets(edit_sheet),
            }
        )
        if not asset_result.success:
            raise RuntimeError(asset_result.error or "Reference asset binding failed")
        asset_bound_path = asset_result.data["json_path"]
        current_path = asset_bound_path

    return {
        "replication_package_path": current_path,
        "text_edit_path": text_edit_path,
        "asset_bound_path": asset_bound_path,
        "applied": {
            "text_edits": applied_text_edits,
            "assets": applied_assets,
        },
        "next_step": "approve_reference_package"
        if applied_assets
        else "bind_reference_assets_or_approve",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replication_package_path", help="Pending replication package JSON")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project workspace root, for example projects/my-reference-video",
    )
    parser.add_argument(
        "--edit-sheet",
        required=True,
        help="JSON file with rewrite_text, scene_edits, and/or assets.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the edit sheet against the package without writing any artifacts.",
    )
    args = parser.parse_args(argv)

    try:
        edit_sheet = _load_json(args.edit_sheet)
        if args.validate_only:
            report = validate_edit_sheet(_load_json(args.replication_package_path), edit_sheet)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["valid"] else 1
        result = apply_edit_sheet(
            replication_package_path=args.replication_package_path,
            project_dir=args.project_dir,
            edit_sheet=edit_sheet,
        )
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
