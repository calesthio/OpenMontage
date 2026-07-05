"""Edit script and prompt text in a pending reference replication package."""

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


APPROVED_STATUSES = {"approved", "approved_with_changes"}


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "reference-edits"


def _load_package(inputs: dict[str, Any]) -> dict[str, Any]:
    if inputs.get("replication_package"):
        return copy.deepcopy(inputs["replication_package"])
    package_path = inputs.get("replication_package_path")
    if not package_path:
        raise ValueError("replication_package or replication_package_path is required")
    return json.loads(Path(package_path).read_text(encoding="utf-8"))


def _scene_map(package: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(scene.get("scene_id")): scene
        for scene in package.get("scenes") or []
        if str(scene.get("scene_id", "")).strip()
    }


def _has_rewrite_edit(inputs: dict[str, Any]) -> bool:
    return "rewrite_text" in inputs and str(inputs.get("rewrite_text", "")).strip() != ""


def _has_scene_edit(scene_edit: dict[str, Any]) -> bool:
    return any(
        key in scene_edit and str(scene_edit.get(key, "")).strip() != ""
        for key in ("script_text", "seedance_prompt")
    )


class ReferenceTextEdit(BaseTool):
    name = "reference_text_edit"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "reference_analysis"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "No external dependencies."
    capabilities = [
        "edit_reference_rewrite_text",
        "edit_scene_script_text",
        "edit_seedance_prompt_text",
        "preserve_human_review_gate",
    ]
    supports = {
        "paid_generation": False,
        "mutates_approved_package": False,
        "scene_prompt_editing": True,
    }
    best_for = [
        "making human edits to replicated copy before approval",
        "preparing Seedance prompt text without manually editing JSON",
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
        "rewrite_text",
        "scene_edits",
    ]
    side_effects = ["writes edited replication package JSON"]

    input_schema = {
        "type": "object",
        "required": ["project_dir"],
        "properties": {
            "project_dir": {"type": "string"},
            "replication_package": {"type": "object"},
            "replication_package_path": {"type": "string"},
            "rewrite_text": {"type": "string"},
            "scene_edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["scene_id"],
                    "properties": {
                        "scene_id": {"type": "string"},
                        "script_text": {"type": "string"},
                        "seedance_prompt": {"type": "string"},
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
                error="Cannot edit an already approved package; edit the pending package instead.",
            )

        scene_edits = inputs.get("scene_edits") or []
        if not isinstance(scene_edits, list):
            return ToolResult(success=False, error="scene_edits must be a list")
        if not _has_rewrite_edit(inputs) and not any(_has_scene_edit(edit) for edit in scene_edits):
            return ToolResult(success=False, error="Provide at least one rewrite or scene text edit")

        scenes_by_id = _scene_map(package)
        unknown_scene_ids = sorted(
            {
                str(edit.get("scene_id", "")).strip()
                for edit in scene_edits
                if str(edit.get("scene_id", "")).strip() not in scenes_by_id
            }
        )
        if unknown_scene_ids:
            return ToolResult(
                success=False,
                error=f"Unknown scene_id for reference text edit: {', '.join(unknown_scene_ids)}",
            )

        edited = self._apply_edits(package, inputs, scene_edits, scenes_by_id)
        project_dir = Path(inputs["project_dir"])
        output_dir = Path(inputs.get("output_dir") or project_dir / "artifacts" / "reference-edits")
        output_dir.mkdir(parents=True, exist_ok=True)
        source_name = _safe_slug(
            Path(
                str(
                    (edited.get("source") or {}).get("local_video_path")
                    or (edited.get("source") or {}).get("input")
                    or "reference"
                )
            ).stem
        )
        json_path = output_dir / f"{source_name}-text-edited-package.json"
        json_path.write_text(json.dumps(edited, ensure_ascii=False, indent=2), encoding="utf-8")

        return ToolResult(
            success=True,
            data={"replication_package": edited, "json_path": str(json_path)},
            artifacts=[str(json_path)],
            cost_usd=0.0,
        )

    def _apply_edits(
        self,
        package: dict[str, Any],
        inputs: dict[str, Any],
        scene_edits: list[dict[str, Any]],
        scenes_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        edited = copy.deepcopy(package)
        edited_scenes_by_id = _scene_map(edited)

        if _has_rewrite_edit(inputs):
            rewrite_draft = edited.setdefault("rewrite_draft", {})
            rewrite_draft["status"] = "needs_human_edit"
            rewrite_draft["text"] = str(inputs["rewrite_text"]).strip()

        for scene_edit in scene_edits:
            scene_id = str(scene_edit.get("scene_id", "")).strip()
            source_scene = scenes_by_id[scene_id]
            scene = edited_scenes_by_id[str(source_scene.get("scene_id"))]
            production_inputs = scene.setdefault("production_inputs", {})
            production_inputs["status"] = "needs_human_edit"
            if str(scene_edit.get("script_text", "")).strip():
                production_inputs["script_text"] = str(scene_edit["script_text"]).strip()
            if str(scene_edit.get("seedance_prompt", "")).strip():
                production_inputs["seedance_prompt"] = str(scene_edit["seedance_prompt"]).strip()

        editable_inputs = edited.setdefault("editable_inputs", {})
        editable_inputs["status"] = "needs_human_edit"
        approval = edited.setdefault("approval", {})
        approval["status"] = "pending_human_review"
        approval["required_before_production"] = True
        approval["paid_generation_started"] = False
        edited.setdefault("edit_history", []).append(
            {
                "tool": self.name,
                "edited_fields": self._edited_fields(inputs, scene_edits),
            }
        )
        return edited

    def _edited_fields(
        self,
        inputs: dict[str, Any],
        scene_edits: list[dict[str, Any]],
    ) -> list[str]:
        fields: list[str] = []
        if _has_rewrite_edit(inputs):
            fields.append("rewrite_draft.text")
        for scene_edit in scene_edits:
            scene_id = str(scene_edit.get("scene_id", "")).strip()
            if str(scene_edit.get("script_text", "")).strip():
                fields.append(f"scenes[{scene_id}].production_inputs.script_text")
            if str(scene_edit.get("seedance_prompt", "")).strip():
                fields.append(f"scenes[{scene_id}].production_inputs.seedance_prompt")
        return fields
