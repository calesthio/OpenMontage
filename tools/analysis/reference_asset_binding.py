"""Import user assets and bind them into a reference replication package."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from tools.assets.custom_asset_import import CustomAssetImport
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


APPROVED_STATUSES = {"approved", "approved_with_changes"}


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-assets"


def _load_package(inputs: dict[str, Any]) -> dict[str, Any]:
    if inputs.get("replication_package"):
        return copy.deepcopy(inputs["replication_package"])
    package_path = inputs.get("replication_package_path")
    if not package_path:
        raise ValueError("replication_package or replication_package_path is required")
    return json.loads(Path(package_path).read_text(encoding="utf-8"))


def _scene_ids(package: dict[str, Any]) -> set[str]:
    return {
        str(scene.get("scene_id"))
        for scene in package.get("scenes") or []
        if str(scene.get("scene_id", "")).strip()
    }


def _asset_index(assets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(asset.get("id")): asset
        for asset in assets
        if isinstance(asset, dict) and str(asset.get("id", "")).strip()
    }


def _replace_by_id(
    existing: list[dict[str, Any]],
    additions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = _asset_index(existing)
    for asset in additions:
        asset_id = str(asset.get("id", "")).strip()
        if asset_id:
            merged[asset_id] = asset
    return list(merged.values())


def _selected_asset_view(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": asset.get("id", ""),
        "type": asset.get("type", ""),
        "path": asset.get("path", ""),
        "scene_id": asset.get("scene_id", ""),
        "role": asset.get("role", ""),
        "authorized": bool(asset.get("authorized", False)),
        "source_tool": asset.get("source_tool", ""),
    }


class ReferenceAssetBinding(BaseTool):
    name = "reference_asset_binding"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "asset_management"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "No external dependencies. Provide existing local asset file paths."
    capabilities = [
        "import_reference_assets",
        "bind_assets_to_reference_scenes",
        "preserve_human_review_gate",
    ]
    supports = {
        "images": True,
        "video": True,
        "authorized_asset_gate": True,
        "mutates_approved_package": False,
    }
    best_for = [
        "adding team-approved face, product, brand, or background references to a replication package",
        "making Seedance dry-run tasks include real reference image paths before paid generation",
    ]
    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=128,
        vram_mb=0,
        disk_mb=500,
        network_required=False,
    )
    idempotency_key_fields = ["replication_package", "replication_package_path", "assets"]
    side_effects = ["copies user files into project assets and writes an updated package JSON"]

    input_schema = {
        "type": "object",
        "required": ["project_dir", "assets"],
        "properties": {
            "project_dir": {"type": "string"},
            "replication_package": {"type": "object"},
            "replication_package_path": {"type": "string"},
            "assets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path", "scene_id"],
                    "properties": {
                        "path": {"type": "string"},
                        "scene_id": {"type": "string"},
                        "id": {"type": "string"},
                        "type": {"type": "string"},
                        "role": {"type": "string"},
                        "authorized": {"type": "boolean", "default": False},
                        "license": {"type": "string"},
                        "original_url": {"type": "string"},
                        "resolution": {"type": "string"},
                    },
                },
            },
            "output_dir": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "replication_package": {"type": "object"},
            "asset_manifest": {"type": "object"},
            "json_path": {"type": "string"},
        },
    }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            package = _load_package(inputs)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return ToolResult(success=False, error=str(exc))

        approval_status = str((package.get("approval") or {}).get("status", ""))
        if approval_status in APPROVED_STATUSES:
            return ToolResult(
                success=False,
                error="Cannot bind assets to an already approved package; edit the pending package instead.",
            )

        assets = inputs.get("assets") or []
        if not isinstance(assets, list) or not assets:
            return ToolResult(success=False, error="assets must be a non-empty list")

        scene_ids = _scene_ids(package)
        unknown_scene_ids = sorted(
            {
                str(asset.get("scene_id", "")).strip()
                for asset in assets
                if str(asset.get("scene_id", "")).strip() not in scene_ids
            }
        )
        if unknown_scene_ids:
            return ToolResult(
                success=False,
                error=f"Unknown scene_id for reference asset binding: {', '.join(unknown_scene_ids)}",
            )

        import_result = CustomAssetImport().execute(
            {
                "project_dir": inputs["project_dir"],
                "assets": assets,
            }
        )
        if not import_result.success:
            return import_result

        imported_assets = import_result.data["asset_manifest"]["assets"]
        bound_assets = self._enrich_imported_assets(imported_assets, assets)
        updated_package = self._bind_assets(package, bound_assets)

        project_dir = Path(inputs["project_dir"])
        output_dir = Path(inputs.get("output_dir") or project_dir / "artifacts" / "reference-assets")
        output_dir.mkdir(parents=True, exist_ok=True)
        source_name = _safe_slug(
            Path(
                str(
                    (updated_package.get("source") or {}).get("local_video_path")
                    or (updated_package.get("source") or {}).get("input")
                    or "reference"
                )
            ).stem
        )
        json_path = output_dir / f"{source_name}-assets-bound-package.json"
        json_path.write_text(
            json.dumps(updated_package, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return ToolResult(
            success=True,
            data={
                "replication_package": updated_package,
                "asset_manifest": import_result.data["asset_manifest"],
                "json_path": str(json_path),
            },
            artifacts=[str(json_path), *import_result.artifacts],
            cost_usd=0.0,
        )

    def _enrich_imported_assets(
        self,
        imported_assets: list[dict[str, Any]],
        requested_assets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        by_id = {
            str(asset.get("id")): asset
            for asset in requested_assets
            if str(asset.get("id", "")).strip()
        }
        enriched: list[dict[str, Any]] = []
        for imported in imported_assets:
            asset = dict(imported)
            requested = by_id.get(str(asset.get("id", "")), {})
            asset["role"] = requested.get("role", "reference_asset")
            asset["authorized"] = bool(requested.get("authorized", False))
            if requested.get("authorization_note"):
                asset["authorization_note"] = requested["authorization_note"]
            enriched.append(asset)
        return enriched

    def _bind_assets(
        self,
        package: dict[str, Any],
        bound_assets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        updated = copy.deepcopy(package)
        editable_inputs = updated.setdefault("editable_inputs", {})
        editable_inputs["status"] = "needs_human_edit"
        editable_inputs["custom_assets"] = _replace_by_id(
            editable_inputs.get("custom_assets") or [],
            bound_assets,
        )

        assets_by_scene: dict[str, list[dict[str, Any]]] = {}
        for asset in bound_assets:
            assets_by_scene.setdefault(str(asset.get("scene_id", "")), []).append(
                _selected_asset_view(asset)
            )

        for scene in updated.get("scenes") or []:
            scene_id = str(scene.get("scene_id", ""))
            scene_assets = assets_by_scene.get(scene_id, [])
            if not scene_assets:
                continue
            production_inputs = scene.setdefault("production_inputs", {})
            production_inputs["status"] = "needs_human_edit"
            production_inputs["selected_assets"] = _replace_by_id(
                production_inputs.get("selected_assets") or [],
                scene_assets,
            )

        approval = updated.setdefault("approval", {})
        approval["status"] = "pending_human_review"
        approval["required_before_production"] = True
        approval["paid_generation_started"] = False
        return updated
