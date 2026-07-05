"""Validate an edited reference package and prepare a production handoff plan."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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
from tools.analysis.reference_asset_policy import validate_required_face_or_avatar_asset
from tools.analysis.reference_target_modes import (
    DEFERRED_REFERENCE_TARGET_MODE_ERROR,
    SUPPORTED_REFERENCE_TARGET_MODES,
)
from tools.video.seedance_constraints import (
    ALLOWED_RESOLUTIONS,
    DEFAULT_RESOLUTION,
    MAX_DURATION_SECONDS,
    MAX_GENERATIONS_PER_BATCH,
    seedance_duration,
    seedance_resolution,
    validate_seedance_constraints,
)


APPROVED_STATUSES = {"approved", "approved_with_changes"}
TARGET_MODES = SUPPORTED_REFERENCE_TARGET_MODES


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-production"


def _load_package(inputs: dict[str, Any]) -> dict[str, Any]:
    if inputs.get("replication_package"):
        return dict(inputs["replication_package"])
    package_path = inputs.get("replication_package_path")
    if not package_path:
        raise ValueError("replication_package or replication_package_path is required")
    return json.loads(Path(package_path).read_text(encoding="utf-8"))


def _asset_lookup(package: dict[str, Any]) -> dict[str, dict[str, Any]]:
    custom_assets = (package.get("editable_inputs") or {}).get("custom_assets") or []
    return {
        str(asset.get("id")): asset
        for asset in custom_assets
        if str(asset.get("id", "")).strip()
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


class ReferenceProductionPlan(BaseTool):
    name = "reference_production_plan"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "production_planning"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "No external dependencies."
    capabilities = [
        "reference_review_validation",
        "seedance_production_handoff",
        "team_asset_authorization_check",
    ]
    supports = {
        "target_modes": list(TARGET_MODES),
        "paid_generation": False,
        "writes_plan_only": True,
    }
    best_for = [
        "turning a human-approved reference replication package into a safe production handoff",
        "checking editable script, prompts, uploaded assets, and Seedance limits before generation",
    ]
    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=128,
        vram_mb=0,
        disk_mb=20,
        network_required=False,
    )
    idempotency_key_fields = [
        "replication_package",
        "replication_package_path",
        "target_mode",
        "duration",
        "resolution",
        "batch_size",
    ]
    side_effects = ["writes production plan JSON"]

    input_schema = {
        "type": "object",
        "required": ["project_dir"],
        "properties": {
            "project_dir": {"type": "string"},
            "replication_package": {"type": "object"},
            "replication_package_path": {"type": "string"},
            "target_mode": {
                "type": "string",
                "enum": list(TARGET_MODES),
                "default": "seedance",
            },
            "duration": {
                "type": "string",
                "enum": [str(seconds) for seconds in range(4, 16)],
                "default": str(MAX_DURATION_SECONDS),
            },
            "resolution": {
                "type": "string",
                "enum": list(ALLOWED_RESOLUTIONS),
                "default": DEFAULT_RESOLUTION,
            },
            "batch_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_GENERATIONS_PER_BATCH,
                "default": 1,
            },
            "output_dir": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "production_plan": {"type": "object"},
            "json_path": {"type": "string"},
        },
    }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            package = _load_package(inputs)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return ToolResult(success=False, error=str(exc))

        target_mode = str(inputs.get("target_mode", "seedance"))
        if target_mode not in TARGET_MODES:
            return ToolResult(
                success=False,
                error=DEFERRED_REFERENCE_TARGET_MODE_ERROR.format(target_mode=target_mode),
            )

        constraint_error = validate_seedance_constraints(inputs)
        if target_mode == "seedance" and constraint_error:
            return ToolResult(success=False, error=constraint_error)

        errors = self._validate_package(package, target_mode)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        project_dir = Path(inputs["project_dir"])
        output_dir = Path(inputs.get("output_dir") or project_dir / "artifacts")
        output_dir.mkdir(parents=True, exist_ok=True)

        plan = self._build_plan(package, inputs, target_mode)
        source_name = _safe_slug(
            Path(
                str(
                    (package.get("source") or {}).get("local_video_path")
                    or (package.get("source") or {}).get("input")
                    or "reference"
                )
            ).stem
        )
        json_path = output_dir / f"{source_name}-{target_mode}-production-plan.json"
        json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={"production_plan": plan, "json_path": str(json_path)},
            artifacts=[str(json_path)],
        )

    def _validate_package(self, package: dict[str, Any], target_mode: str) -> list[str]:
        errors: list[str] = []
        approval_status = str((package.get("approval") or {}).get("status", ""))
        if approval_status not in APPROVED_STATUSES:
            errors.append(
                "replication_package approval.status must be approved before production"
            )

        scenes = package.get("scenes") or []
        if not scenes:
            errors.append("replication_package must include at least one scene")

        lookup = _asset_lookup(package)
        for index, scene in enumerate(scenes, start=1):
            scene_id = scene.get("scene_id") or f"scene-{index}"
            production_inputs = scene.get("production_inputs") or {}
            script_text = str(production_inputs.get("script_text", "")).strip()
            seedance_prompt = str(production_inputs.get("seedance_prompt", "")).strip()

            if not script_text:
                errors.append(f"{scene_id} production_inputs.script_text is required")
            if target_mode == "seedance" and not seedance_prompt:
                errors.append(f"{scene_id} production_inputs.seedance_prompt is required")

            unauthorized = [
                str(asset.get("id") or asset.get("path") or "unnamed_asset")
                for asset in _selected_assets(scene)
                if not _is_authorized(asset, lookup)
            ]
            if unauthorized:
                errors.append(
                    f"{scene_id} selected assets must be team-authorized: {', '.join(unauthorized)}"
                )

        errors.extend(validate_required_face_or_avatar_asset(package))
        return errors

    def _build_plan(
        self,
        package: dict[str, Any],
        inputs: dict[str, Any],
        target_mode: str,
    ) -> dict[str, Any]:
        scenes: list[dict[str, Any]] = []
        for scene in package.get("scenes") or []:
            production_inputs = scene.get("production_inputs") or {}
            selected_assets = _selected_assets(scene)
            scenes.append(
                {
                    "scene_id": scene.get("scene_id", ""),
                    "source_timing": {
                        "start": float(scene.get("start", 0.0)),
                        "end": float(scene.get("end", 0.0)),
                    },
                    "script_text": str(production_inputs.get("script_text", "")).strip(),
                    "seedance_prompt": str(
                        production_inputs.get("seedance_prompt", "")
                    ).strip(),
                    "selected_asset_ids": [
                        str(asset.get("id"))
                        for asset in selected_assets
                        if str(asset.get("id", "")).strip()
                    ],
                    "selected_assets": selected_assets,
                    "keyframes": scene.get("keyframes", []),
                    "production_hint": scene.get("production_hint", ""),
                }
            )

        return {
            "version": "1.0",
            "status": "ready_for_production",
            "target_mode": target_mode,
            "source": package.get("source", {}),
            "seedance_constraints": {
                "duration": seedance_duration(inputs),
                "resolution": seedance_resolution(inputs),
                "batch_size": int(inputs.get("batch_size", 1)),
                "max_duration_seconds": MAX_DURATION_SECONDS,
                "max_generations_per_batch": MAX_GENERATIONS_PER_BATCH,
            },
            "scenes": scenes,
            "approval": {
                "source_package_status": (package.get("approval") or {}).get("status"),
                "team_authorized_assets_checked": True,
                "paid_generation_started": False,
            },
            "next_actions": [
                "Review production_plan scenes one final time.",
                "Run Seedance generation only after explicit production approval.",
                "Continue to final edit and compose after sample review.",
            ],
        }
