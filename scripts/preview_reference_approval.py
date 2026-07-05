"""Preview whether a reference package is ready for human approval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis.reference_review_approval import ReferenceReviewApproval
from tools.analysis.reference_target_modes import SUPPORTED_REFERENCE_TARGET_MODES
from tools.video.seedance_constraints import (
    DEFAULT_DURATION,
    DEFAULT_RESOLUTION,
    validate_seedance_constraints,
)


def _load_package(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("replication package must be a JSON object")
    return data


def _asset_lookup(package: dict[str, Any]) -> dict[str, dict[str, Any]]:
    custom_assets = (package.get("editable_inputs") or {}).get("custom_assets") or []
    return {
        str(asset.get("id")): asset
        for asset in custom_assets
        if isinstance(asset, dict) and str(asset.get("id", "")).strip()
    }


def _selected_assets(scene: dict[str, Any]) -> list[dict[str, Any]]:
    production_inputs = scene.get("production_inputs") or {}
    assets = production_inputs.get("selected_assets") or []
    return [asset for asset in assets if isinstance(asset, dict)]


def _is_authorized(asset: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> bool:
    if asset.get("authorized") is True:
        return True
    if asset.get("authorized") is False:
        return False
    asset_id = str(asset.get("id", ""))
    return bool(asset_id and lookup.get(asset_id, {}).get("authorized") is True)


def _scene_summaries(package: dict[str, Any], lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for scene in package.get("scenes") or []:
        production_inputs = scene.get("production_inputs") or {}
        selected_assets = _selected_assets(scene)
        unauthorized_assets = [
            str(asset.get("id") or asset.get("path") or "unnamed_asset")
            for asset in selected_assets
            if not _is_authorized(asset, lookup)
        ]
        summaries.append(
            {
                "scene_id": scene.get("scene_id", ""),
                "script_text_present": bool(str(production_inputs.get("script_text", "")).strip()),
                "seedance_prompt_present": bool(
                    str(production_inputs.get("seedance_prompt", "")).strip()
                ),
                "selected_asset_count": len(selected_assets),
                "unauthorized_assets": unauthorized_assets,
            }
        )
    return summaries


def preview_approval(
    package: dict[str, Any],
    *,
    target_mode: str,
    duration: str,
    resolution: str,
    batch_size: int,
) -> dict[str, Any]:
    errors = ReferenceReviewApproval()._validate_package(package, target_mode)
    if target_mode == "seedance":
        constraint_error = validate_seedance_constraints(
            {
                "duration": duration,
                "resolution": resolution,
                "batch_size": batch_size,
            }
        )
        if constraint_error:
            errors.append(constraint_error)

    lookup = _asset_lookup(package)
    scene_summaries = _scene_summaries(package, lookup)
    selected_asset_count = sum(scene["selected_asset_count"] for scene in scene_summaries)
    unauthorized_asset_count = sum(
        len(scene["unauthorized_assets"]) for scene in scene_summaries
    )
    warnings: list[str] = []
    approval = package.get("approval") or {}
    if approval.get("requires_team_authorized_face_or_avatar") is True and selected_asset_count == 0:
        warnings.append("No selected assets found; confirm this package does not need a face/presenter reference.")

    return {
        "ready_to_approve": not errors,
        "target_mode": target_mode,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "scene_count": len(package.get("scenes") or []),
            "selected_asset_count": selected_asset_count,
            "unauthorized_asset_count": unauthorized_asset_count,
            "approval_status": approval.get("status"),
            "required_before_production": approval.get("required_before_production"),
            "paid_generation_started": approval.get("paid_generation_started", False),
        },
        "scene_summaries": scene_summaries,
        "seedance_constraints": {
            "duration": str(duration),
            "resolution": str(resolution),
            "batch_size": int(batch_size),
        },
        "next_step": "approve_reference_package" if not errors else "fix_package_before_approval",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replication_package_path", help="Edited replication package JSON")
    parser.add_argument("--project-dir", help="Project workspace root; accepted for command symmetry")
    parser.add_argument(
        "--target-mode",
        choices=list(SUPPORTED_REFERENCE_TARGET_MODES),
        default="seedance",
        help="Downstream mode to validate. Reference-video v1 supports Seedance only.",
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
        report = preview_approval(
            _load_package(args.replication_package_path),
            target_mode=args.target_mode,
            duration=args.duration,
            resolution=args.resolution,
            batch_size=args.batch_size,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready_to_approve"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
