"""Approve an edited reference replication package for downstream planning."""

from __future__ import annotations

import copy
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


APPROVAL_PHRASE = "APPROVE REFERENCE PACKAGE"
TARGET_MODES = SUPPORTED_REFERENCE_TARGET_MODES


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-review"


def _load_package(inputs: dict[str, Any]) -> dict[str, Any]:
    if inputs.get("replication_package"):
        return copy.deepcopy(inputs["replication_package"])
    package_path = inputs.get("replication_package_path")
    if not package_path:
        raise ValueError("replication_package or replication_package_path is required")
    return json.loads(Path(package_path).read_text(encoding="utf-8"))


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


class ReferenceReviewApproval(BaseTool):
    name = "reference_review_approval"
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
        "reference_human_approval_gate",
        "edited_package_validation",
        "team_asset_authorization_check",
    ]
    supports = {
        "target_modes": sorted(TARGET_MODES),
        "paid_generation": False,
        "writes_approved_package_only": True,
        "approval_phrase": APPROVAL_PHRASE,
    }
    best_for = [
        "turning a human-edited replication package into an approved immutable handoff copy",
        "blocking Seedance planning until script, prompts, and selected assets are reviewed",
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
        "reviewer",
        "review_notes",
    ]
    side_effects = ["writes approved replication package JSON"]

    input_schema = {
        "type": "object",
        "required": ["project_dir", "target_mode", "reviewer", "approval_phrase"],
        "properties": {
            "project_dir": {"type": "string"},
            "replication_package": {"type": "object"},
            "replication_package_path": {"type": "string"},
            "target_mode": {
                "type": "string",
                "enum": list(TARGET_MODES),
                "default": "seedance",
            },
            "reviewer": {"type": "string"},
            "review_notes": {"type": "string"},
            "approval_phrase": {"type": "string"},
            "output_dir": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "approved_package": {"type": "object"},
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

        approval_phrase = str(inputs.get("approval_phrase", ""))
        if approval_phrase != APPROVAL_PHRASE:
            return ToolResult(
                success=False,
                error=f"Reference approval requires approval_phrase={APPROVAL_PHRASE!r}.",
            )

        reviewer = str(inputs.get("reviewer", "")).strip()
        if not reviewer:
            return ToolResult(success=False, error="reviewer is required")

        errors = self._validate_package(package, target_mode)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        approved = self._approve_package(package, inputs, target_mode, reviewer)
        project_dir = Path(inputs["project_dir"])
        output_dir = Path(inputs.get("output_dir") or project_dir / "artifacts" / "reference-review")
        output_dir.mkdir(parents=True, exist_ok=True)
        source_name = _safe_slug(
            Path(
                str(
                    (approved.get("source") or {}).get("local_video_path")
                    or (approved.get("source") or {}).get("input")
                    or "reference"
                )
            ).stem
        )
        json_path = output_dir / f"{source_name}-{target_mode}-approved-package.json"
        json_path.write_text(json.dumps(approved, ensure_ascii=False, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={"approved_package": approved, "json_path": str(json_path)},
            artifacts=[str(json_path)],
        )

    def _validate_package(self, package: dict[str, Any], target_mode: str) -> list[str]:
        errors: list[str] = []
        approval = package.get("approval") or {}
        if approval.get("required_before_production") is not True:
            errors.append("replication_package approval.required_before_production must be true")

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

    def _approve_package(
        self,
        package: dict[str, Any],
        inputs: dict[str, Any],
        target_mode: str,
        reviewer: str,
    ) -> dict[str, Any]:
        approved = copy.deepcopy(package)
        editable_inputs = approved.setdefault("editable_inputs", {})
        editable_inputs["status"] = "approved_for_production"

        approval = approved.setdefault("approval", {})
        approval["status"] = "approved"
        approval["target_mode"] = target_mode
        approval["reviewed_by"] = reviewer
        approval["review_notes"] = str(inputs.get("review_notes", "")).strip()
        approval["required_before_production"] = True
        approval["requires_team_authorized_face_or_avatar"] = bool(
            approval.get("requires_team_authorized_face_or_avatar", True)
        )
        approval["paid_generation_started"] = False
        approval["approved_package_generated_by"] = self.name
        return approved
