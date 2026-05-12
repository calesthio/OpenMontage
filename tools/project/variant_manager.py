"""Lightweight deliverable variant registry for OpenMontage projects."""

from __future__ import annotations

import copy
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from schemas.artifacts import load_schema
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


STATUSES = {"draft", "candidate", "approved", "rejected", "archived", "published"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _variant_index(manifest: dict[str, Any]) -> dict[str, int]:
    return {variant["id"]: i for i, variant in enumerate(manifest.get("variants", []))}


def _variant_summary(variant: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": variant["id"],
        "name": variant["name"],
        "status": variant["status"],
        "purpose": variant["purpose"],
        "created_at": variant["created_at"],
        "tags": variant.get("tags", []),
        "video": variant.get("outputs", {}).get("video"),
    }


class VariantManager(BaseTool):
    name = "variant_manager"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "project_management"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    capabilities = [
        "init_variant_manifest",
        "add_variant",
        "list_variants",
        "show_variant",
        "promote_variant",
        "archive_variant",
        "compare_variants",
        "validate_variant_manifest",
    ]
    best_for = [
        "tracking deliverable variants across one project",
        "recording which script/audio/caption/render inputs produced each output",
        "marking the current approved variant for named channels",
    ]
    not_good_for = [
        "storing large media blobs",
        "replacing review platforms or asset management systems",
        "automatically judging creative quality",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation", "manifest_path"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "init",
                    "add",
                    "list",
                    "show",
                    "promote",
                    "archive",
                    "compare",
                    "validate",
                ],
            },
            "manifest_path": {
                "type": "string",
                "description": "Path to variants.json or another variant manifest file.",
            },
            "project_id": {
                "type": "string",
                "description": "Project id for operation='init'.",
            },
            "overwrite": {
                "type": "boolean",
                "default": False,
                "description": "Allow init to replace an existing manifest.",
            },
            "variant": {
                "type": "object",
                "description": "Variant object for operation='add'.",
            },
            "variant_id": {
                "type": "string",
                "description": "Target variant id for show/promote/archive.",
            },
            "variant_a": {"type": "string"},
            "variant_b": {"type": "string"},
            "channel": {
                "type": "string",
                "default": "default",
                "description": "Current-channel key for promote, e.g. handoff_intro.",
            },
            "status": {
                "type": "string",
                "enum": sorted(STATUSES),
                "description": "Status filter for list or status to assign during promote.",
            },
            "purpose": {"type": "string", "description": "Purpose filter for list."},
            "tag": {"type": "string", "description": "Tag filter for list."},
            "include_archived": {
                "type": "boolean",
                "default": False,
                "description": "Include archived variants in list results.",
            },
            "update_existing": {
                "type": "boolean",
                "default": False,
                "description": "Allow add to update an existing variant id.",
            },
            "archive_reason": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = ["operation", "manifest_path", "variant_id", "channel"]
    side_effects = ["writes variant manifest JSON for mutating operations"]
    user_visible_verification = [
        "Review the manifest current channels and variant summaries before delivery",
    ]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        operation = inputs.get("operation")
        try:
            if not operation:
                result = ToolResult(success=False, error="operation is required")
            elif operation == "init":
                result = self._init(inputs)
            elif operation == "add":
                result = self._add(inputs)
            elif operation == "list":
                result = self._list(inputs)
            elif operation == "show":
                result = self._show(inputs)
            elif operation == "promote":
                result = self._promote(inputs)
            elif operation == "archive":
                result = self._archive(inputs)
            elif operation == "compare":
                result = self._compare(inputs)
            elif operation == "validate":
                result = self._validate(inputs)
            else:
                result = ToolResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as exc:
            result = ToolResult(success=False, error=f"{type(exc).__name__}: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _manifest_path(self, inputs: dict[str, Any]) -> Path:
        return Path(inputs["manifest_path"]).expanduser().resolve()

    def _read(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Variant manifest not found: {path}")
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, path: Path, manifest: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        tmp.replace(path)

    def _check(self, manifest: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        schema = load_schema("variant_manifest")
        try:
            jsonschema.validate(instance=manifest, schema=schema)
        except jsonschema.ValidationError as exc:
            errors.append(exc.message)

        seen: set[str] = set()
        for variant in manifest.get("variants", []):
            vid = variant.get("id")
            if vid in seen:
                errors.append(f"Duplicate variant id: {vid}")
            seen.add(vid)

        for channel, variant_id in manifest.get("current", {}).items():
            if variant_id not in seen:
                errors.append(
                    f"Current channel {channel!r} points to missing variant {variant_id!r}"
                )
        return errors

    def _save_checked(self, path: Path, manifest: dict[str, Any]) -> ToolResult | None:
        errors = self._check(manifest)
        if errors:
            return ToolResult(success=False, error="; ".join(errors), data={"errors": errors})
        self._write(path, manifest)
        return None

    def _init(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        if path.exists() and not inputs.get("overwrite", False):
            return ToolResult(
                success=False,
                error=f"Manifest already exists: {path}. Pass overwrite=true to replace it.",
            )
        project_id = inputs.get("project_id")
        if not project_id:
            return ToolResult(success=False, error="project_id is required for init")
        manifest = {
            "version": "1.0",
            "project_id": project_id,
            "current": {},
            "variants": [],
        }
        self._write(path, manifest)
        return ToolResult(
            success=True,
            data={"operation": "init", "manifest_path": str(path), "manifest": manifest},
            artifacts=[str(path)],
        )

    def _add(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        variant = copy.deepcopy(inputs.get("variant") or {})
        if not variant:
            return ToolResult(success=False, error="variant is required for add")
        now = _now()
        variant.setdefault("status", "candidate")
        variant.setdefault("created_at", now)
        variant["updated_at"] = now
        variant.setdefault("inputs", {})
        variant.setdefault("outputs", {})
        variant.setdefault("tags", [])

        index = _variant_index(manifest)
        vid = variant.get("id")
        if not vid:
            return ToolResult(success=False, error="variant.id is required")
        if vid in index and not inputs.get("update_existing", False):
            return ToolResult(
                success=False,
                error=f"Variant {vid!r} already exists. Pass update_existing=true to replace it.",
            )

        if vid in index:
            manifest["variants"][index[vid]] = variant
            action = "updated"
        else:
            manifest.setdefault("variants", []).append(variant)
            action = "added"

        failed = self._save_checked(path, manifest)
        if failed:
            return failed
        return ToolResult(
            success=True,
            data={"operation": "add", "action": action, "variant": variant},
            artifacts=[str(path)],
        )

    def _list(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        status = inputs.get("status")
        purpose = inputs.get("purpose")
        tag = inputs.get("tag")
        include_archived = inputs.get("include_archived", False)
        variants = []
        for variant in manifest.get("variants", []):
            if (
                not include_archived
                and status != "archived"
                and variant.get("status") == "archived"
            ):
                continue
            if status and variant.get("status") != status:
                continue
            if purpose and variant.get("purpose") != purpose:
                continue
            if tag and tag not in variant.get("tags", []):
                continue
            variants.append(_variant_summary(variant))
        return ToolResult(
            success=True,
            data={
                "operation": "list",
                "project_id": manifest.get("project_id"),
                "current": manifest.get("current", {}),
                "count": len(variants),
                "variants": variants,
            },
        )

    def _get_variant(self, manifest: dict[str, Any], variant_id: str) -> dict[str, Any]:
        for variant in manifest.get("variants", []):
            if variant.get("id") == variant_id:
                return variant
        raise KeyError(f"Variant not found: {variant_id}")

    def _show(self, inputs: dict[str, Any]) -> ToolResult:
        manifest = self._read(self._manifest_path(inputs))
        variant_id = inputs.get("variant_id")
        if not variant_id:
            return ToolResult(success=False, error="variant_id is required for show")
        variant = self._get_variant(manifest, variant_id)
        channels = [
            channel
            for channel, current_id in manifest.get("current", {}).items()
            if current_id == variant_id
        ]
        return ToolResult(
            success=True,
            data={"operation": "show", "variant": variant, "current_channels": channels},
        )

    def _promote(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        variant_id = inputs.get("variant_id")
        if not variant_id:
            return ToolResult(success=False, error="variant_id is required for promote")
        variant = self._get_variant(manifest, variant_id)
        restore_status = inputs.get("status")
        if variant.get("status") in {"archived", "rejected"} and restore_status not in {
            "approved",
            "published",
        }:
            return ToolResult(
                success=False,
                error=(
                    f"Variant {variant_id!r} is {variant.get('status')}; "
                    "pass status='approved' or status='published' to intentionally restore it."
                ),
            )
        channel = inputs.get("channel") or "default"
        manifest.setdefault("current", {})[channel] = variant_id
        new_status = inputs.get("status")
        if new_status:
            variant["status"] = new_status
        elif variant.get("status") in {"draft", "candidate"}:
            variant["status"] = "approved"
        variant["updated_at"] = _now()

        failed = self._save_checked(path, manifest)
        if failed:
            return failed
        return ToolResult(
            success=True,
            data={
                "operation": "promote",
                "channel": channel,
                "variant": _variant_summary(variant),
                "current": manifest["current"],
            },
            artifacts=[str(path)],
        )

    def _archive(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        variant_id = inputs.get("variant_id")
        if not variant_id:
            return ToolResult(success=False, error="variant_id is required for archive")
        variant = self._get_variant(manifest, variant_id)
        current_channels = [
            channel
            for channel, current_id in manifest.get("current", {}).items()
            if current_id == variant_id
        ]
        if current_channels:
            return ToolResult(
                success=False,
                error=(
                    f"Variant {variant_id!r} is current for {current_channels}. "
                    "Promote another variant before archiving it."
                ),
                data={"current_channels": current_channels},
            )
        variant["status"] = "archived"
        variant["archived_at"] = _now()
        variant["updated_at"] = variant["archived_at"]
        if inputs.get("archive_reason"):
            variant["archive_reason"] = inputs["archive_reason"]
        failed = self._save_checked(path, manifest)
        if failed:
            return failed
        return ToolResult(
            success=True,
            data={"operation": "archive", "variant": _variant_summary(variant)},
            artifacts=[str(path)],
        )

    def _compare(self, inputs: dict[str, Any]) -> ToolResult:
        manifest = self._read(self._manifest_path(inputs))
        a_id = inputs.get("variant_a")
        b_id = inputs.get("variant_b")
        if not a_id or not b_id:
            return ToolResult(success=False, error="variant_a and variant_b are required")
        a = self._get_variant(manifest, a_id)
        b = self._get_variant(manifest, b_id)
        fields = ["status", "purpose", "inputs", "outputs", "review", "tags", "lineage"]
        diff: dict[str, Any] = {}
        for field in fields:
            if a.get(field) != b.get(field):
                diff[field] = {"a": a.get(field), "b": b.get(field)}
        return ToolResult(
            success=True,
            data={
                "operation": "compare",
                "variant_a": a_id,
                "variant_b": b_id,
                "changed_fields": sorted(diff),
                "diff": diff,
            },
        )

    def _validate(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._manifest_path(inputs)
        manifest = self._read(path)
        errors = self._check(manifest)
        return ToolResult(
            success=not errors,
            error=None if not errors else "; ".join(errors),
            data={
                "operation": "validate",
                "manifest_path": str(path),
                "valid": not errors,
                "errors": errors,
                "variant_count": len(manifest.get("variants", [])),
                "current": manifest.get("current", {}),
            },
        )
