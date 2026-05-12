from __future__ import annotations

import json
from pathlib import Path

from schemas.artifacts import load_schema, validate_artifact
from tools.project.variant_manager import VariantManager
from tools.tool_registry import ToolRegistry


def _variant(variant_id: str, *, video: str = "renders/final.mp4") -> dict:
    return {
        "id": variant_id,
        "name": f"Variant {variant_id}",
        "status": "candidate",
        "purpose": "handoff_intro",
        "created_at": "2026-05-12T00:00:00+00:00",
        "lineage": {
            "parent": None,
            "change_summary": "Initial candidate",
        },
        "inputs": {
            "script": "artifacts/script.json",
            "audio": "assets/audio/narration.mp3",
            "captions": "artifacts/captions.json",
            "render_props": "render-inputs/props.json",
        },
        "outputs": {
            "video": video,
            "duration_seconds": 42.0,
            "profile": "youtube_landscape",
            "speed": 1.0,
        },
        "review": {
            "decision": "needs_review",
            "notes": "Generated for comparison",
            "known_issues": [],
        },
        "tags": ["handoff", "candidate"],
    }


def _init_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "variants.json"
    tool = VariantManager()
    result = tool.execute(
        {
            "operation": "init",
            "manifest_path": str(path),
            "project_id": "demo-project",
        }
    )
    assert result.success, result.error
    return path


def test_variant_manifest_schema_is_registered():
    schema = load_schema("variant_manifest")
    assert schema["title"] == "Variant Manifest"


def test_init_creates_schema_valid_manifest(tmp_path: Path):
    path = _init_manifest(tmp_path)
    manifest = json.loads(path.read_text())

    validate_artifact("variant_manifest", manifest)
    assert manifest == {
        "version": "1.0",
        "project_id": "demo-project",
        "current": {},
        "variants": [],
    }


def test_add_and_list_variant(tmp_path: Path):
    path = _init_manifest(tmp_path)
    tool = VariantManager()

    result = tool.execute(
        {
            "operation": "add",
            "manifest_path": str(path),
            "variant": _variant("v1"),
        }
    )

    assert result.success, result.error
    listed = tool.execute({"operation": "list", "manifest_path": str(path)})
    assert listed.success
    assert listed.data["count"] == 1
    assert listed.data["variants"][0]["id"] == "v1"
    assert listed.data["variants"][0]["video"] == "renders/final.mp4"


def test_execute_returns_error_when_operation_missing(tmp_path: Path):
    result = VariantManager().execute({"manifest_path": str(tmp_path / "variants.json")})

    assert not result.success
    assert "operation is required" in result.error


def test_add_rejects_duplicate_without_update_flag(tmp_path: Path):
    path = _init_manifest(tmp_path)
    tool = VariantManager()
    payload = {"operation": "add", "manifest_path": str(path), "variant": _variant("v1")}
    assert tool.execute(payload).success

    duplicate = tool.execute(payload)

    assert not duplicate.success
    assert "already exists" in duplicate.error


def test_promote_sets_current_channel_and_approves_candidate(tmp_path: Path):
    path = _init_manifest(tmp_path)
    tool = VariantManager()
    tool.execute({"operation": "add", "manifest_path": str(path), "variant": _variant("v1")})

    result = tool.execute(
        {
            "operation": "promote",
            "manifest_path": str(path),
            "variant_id": "v1",
            "channel": "handoff_intro",
        }
    )

    assert result.success, result.error
    manifest = json.loads(path.read_text())
    assert manifest["current"] == {"handoff_intro": "v1"}
    assert manifest["variants"][0]["status"] == "approved"


def test_archive_blocks_current_variant(tmp_path: Path):
    path = _init_manifest(tmp_path)
    tool = VariantManager()
    tool.execute({"operation": "add", "manifest_path": str(path), "variant": _variant("v1")})
    tool.execute(
        {
            "operation": "promote",
            "manifest_path": str(path),
            "variant_id": "v1",
            "channel": "default",
        }
    )

    result = tool.execute(
        {
            "operation": "archive",
            "manifest_path": str(path),
            "variant_id": "v1",
            "archive_reason": "Superseded",
        }
    )

    assert not result.success
    assert "Promote another variant" in result.error


def test_promote_blocks_archived_variant_without_restore_status(tmp_path: Path):
    path = _init_manifest(tmp_path)
    tool = VariantManager()
    archived = _variant("v1")
    archived["status"] = "archived"
    tool.execute({"operation": "add", "manifest_path": str(path), "variant": archived})

    result = tool.execute(
        {
            "operation": "promote",
            "manifest_path": str(path),
            "variant_id": "v1",
            "channel": "default",
        }
    )

    assert not result.success
    assert "intentionally restore" in result.error


def test_list_status_archived_includes_archived_without_extra_flag(tmp_path: Path):
    path = _init_manifest(tmp_path)
    tool = VariantManager()
    archived = _variant("v1")
    archived["status"] = "archived"
    tool.execute({"operation": "add", "manifest_path": str(path), "variant": archived})

    result = tool.execute(
        {
            "operation": "list",
            "manifest_path": str(path),
            "status": "archived",
        }
    )

    assert result.success, result.error
    assert result.data["count"] == 1
    assert result.data["variants"][0]["status"] == "archived"


def test_compare_reports_changed_fields(tmp_path: Path):
    path = _init_manifest(tmp_path)
    tool = VariantManager()
    tool.execute({"operation": "add", "manifest_path": str(path), "variant": _variant("v1")})
    tool.execute(
        {
            "operation": "add",
            "manifest_path": str(path),
            "variant": _variant("v2", video="renders/final-v2.mp4"),
        }
    )

    result = tool.execute(
        {
            "operation": "compare",
            "manifest_path": str(path),
            "variant_a": "v1",
            "variant_b": "v2",
        }
    )

    assert result.success, result.error
    assert "outputs" in result.data["changed_fields"]
    assert result.data["diff"]["outputs"]["b"]["video"] == "renders/final-v2.mp4"


def test_validate_reports_missing_current_reference(tmp_path: Path):
    path = _init_manifest(tmp_path)
    manifest = json.loads(path.read_text())
    manifest["current"] = {"default": "missing"}
    path.write_text(json.dumps(manifest), encoding="utf-8")

    result = VariantManager().execute({"operation": "validate", "manifest_path": str(path)})

    assert not result.success
    assert "points to missing variant" in result.error


def test_variant_manager_is_discoverable():
    registry = ToolRegistry()
    registry.discover()

    tool = registry.get("variant_manager")

    assert tool is not None
    assert "promote_variant" in tool.capabilities
