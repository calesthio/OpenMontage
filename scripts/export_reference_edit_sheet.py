"""Export a JSON edit-sheet template from a pending reference package."""

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


APPROVED_STATUSES = {"approved", "approved_with_changes"}


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-edit-sheet"


def _load_package(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("replication package must be a JSON object")
    return data


def _source_name(package: dict[str, Any]) -> str:
    source = package.get("source") or {}
    return _safe_slug(
        Path(str(source.get("local_video_path") or source.get("input") or "reference")).stem
    )


def _asset_placeholders(package: dict[str, Any]) -> list[dict[str, Any]]:
    placeholders: list[dict[str, Any]] = []
    for scene in package.get("scenes") or []:
        scene_id = str(scene.get("scene_id", "")).strip()
        production_inputs = scene.get("production_inputs") or {}
        for slot in production_inputs.get("asset_slots") or []:
            if not isinstance(slot, dict):
                continue
            placeholders.append(
                {
                    "scene_id": scene_id,
                    "role": slot.get("slot") or slot.get("role") or "reference_asset",
                    "type": slot.get("type", "image"),
                    "description": slot.get("description", ""),
                    "example_asset": {
                        "path": "/path/to/team-owned-asset.png",
                        "scene_id": scene_id,
                        "id": f"{scene_id}-{slot.get('slot') or 'asset'}",
                        "role": slot.get("slot") or slot.get("role") or "reference_asset",
                        "authorized": True,
                    },
                }
            )
    return placeholders


def build_edit_sheet(package: dict[str, Any]) -> dict[str, Any]:
    approval_status = str((package.get("approval") or {}).get("status", ""))
    if approval_status in APPROVED_STATUSES:
        raise ValueError("Cannot export an edit sheet for an already approved package")

    scene_edits: list[dict[str, Any]] = []
    for scene in package.get("scenes") or []:
        production_inputs = scene.get("production_inputs") or {}
        scene_edits.append(
            {
                "scene_id": str(scene.get("scene_id", "")).strip(),
                "script_text": str(production_inputs.get("script_text", "")),
                "seedance_prompt": str(production_inputs.get("seedance_prompt", "")),
                "reference": {
                    "start": scene.get("start"),
                    "end": scene.get("end"),
                    "visual_summary": scene.get("visual_summary", ""),
                },
            }
        )

    return {
        "version": "1.0",
        "source_package_status": approval_status or "unknown",
        "instructions": [
            "Edit rewrite_text, scene_edits[].script_text, and scene_edits[].seedance_prompt.",
            "Move any needed example_asset entries into assets after replacing path/id values.",
            "Use only team-owned or explicitly authorized face, product, brand, and background assets.",
            "Apply with scripts/apply_reference_edit_sheet.py; applying this sheet does not approve production.",
        ],
        "rewrite_text": str((package.get("rewrite_draft") or {}).get("text", "")),
        "scene_edits": scene_edits,
        "assets": [],
        "asset_placeholders": _asset_placeholders(package),
    }


def write_edit_sheet(
    *,
    package: dict[str, Any],
    project_dir: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    out_path = (
        Path(output_path)
        if output_path
        else Path(project_dir)
        / "artifacts"
        / "reference-edit-sheets"
        / f"{_source_name(package)}-edit-sheet.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(build_edit_sheet(package), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replication_package_path", help="Pending replication package JSON")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project workspace root, for example projects/my-reference-video",
    )
    parser.add_argument("--output-path", help="Optional explicit JSON edit-sheet path")
    args = parser.parse_args(argv)

    try:
        package = _load_package(args.replication_package_path)
        edit_sheet_path = write_edit_sheet(
            package=package,
            project_dir=args.project_dir,
            output_path=args.output_path,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "edit_sheet_path": str(edit_sheet_path),
                "next_step": "apply_reference_edit_sheet",
                "apply_command": " ".join(
                    [
                        ".venv/bin/python",
                        "scripts/apply_reference_edit_sheet.py",
                        str(args.replication_package_path),
                        "--project-dir",
                        str(args.project_dir),
                        "--edit-sheet",
                        str(edit_sheet_path),
                    ]
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
