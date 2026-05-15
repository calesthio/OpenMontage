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


def test_review_writes_interactive_page(tmp_path: Path):
    path = _init_manifest(tmp_path)
    output_dir = tmp_path / "variant-review"
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "captions.json").write_text(
        json.dumps({"lines": ["生产问题出现后，先找到线索，再定位调用链。"]}),
        encoding="utf-8",
    )
    (tmp_path / "renders").mkdir()
    (tmp_path / "renders" / "final.mp4").write_bytes(b"fake mp4")
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
            "operation": "review",
            "manifest_path": str(path),
            "channel": "standalone",
            "output_dir": str(output_dir),
            "run_id": "round-1",
        }
    )

    assert result.success, result.error
    html = (output_dir / "variant_review.html").read_text(encoding="utf-8")
    assert result.data["language"] == "zh"
    assert 'lang="zh-CN"' in html
    assert "Variant Manager 版本评审" in html
    assert "选用这个版本" in html
    assert "要求生成新版本" in html
    assert "<video controls" in html
    assert "&quot;tool&quot;" not in html
    assert '"tool": "variant_manager"' in html
    assert "onplay=" in html
    assert "round-1" in html
    assert result.data["variant_count"] == 2


def test_annotate_promotes_approved_selection(tmp_path: Path):
    path = _init_manifest(tmp_path)
    (tmp_path / "renders").mkdir()
    (tmp_path / "renders" / "final-v2.mp4").write_bytes(b"fake video")
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "script.json").write_text(
        json.dumps({"version": "1.0", "title": "Demo", "sections": []}),
        encoding="utf-8",
    )
    (tmp_path / "artifacts" / "captions.json").write_text(
        json.dumps({"lines": ["Hello"]}),
        encoding="utf-8",
    )
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
            "operation": "annotate",
            "manifest_path": str(path),
            "review_payload": {
                "version": "1.0",
                "run_id": "round-1",
                "channel": "standalone",
                "selected_variant_id": "v2",
                "decision": "APPROVED",
                "notes": "",
            },
        }
    )

    assert result.success, result.error
    assert result.data["review_complete"] is True
    assert result.data["next_operation"] == "package_or_publish"
    assert result.data["package_inputs"]["project_id"] == "demo-project"
    assert result.data["package_inputs"]["variant_id"] == "v2"
    assert result.data["package_inputs"]["channel"] == "standalone"
    assert result.data["package_inputs"]["video_path"].endswith("renders/final-v2.mp4")
    assert result.data["package_inputs"]["script_path"].endswith("artifacts/script.json")
    roles = {item["role"] for item in result.data["package_inputs"]["extra_files"]}
    assert {"captions", "variant_review_notes"} <= roles
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["current"] == {"standalone": "v2"}
    assert manifest["variants"][1]["status"] == "approved"
    assert manifest["variants"][1]["review"]["decision"] == "approved"


def test_annotate_keeps_candidate_when_revision_requested(tmp_path: Path):
    path = _init_manifest(tmp_path)
    tool = VariantManager()
    tool.execute({"operation": "add", "manifest_path": str(path), "variant": _variant("v1")})

    result = tool.execute(
        {
            "operation": "annotate",
            "manifest_path": str(path),
            "review_payload": {
                "version": "1.0",
                "run_id": "round-1",
                "channel": "default",
                "selected_variant_id": "v1",
                "decision": "NEEDS_REVISION",
                "notes": "The closing frame should hold longer.",
            },
        }
    )

    assert result.success, result.error
    assert result.data["review_complete"] is False
    assert result.data["next_operation"] == "revise_variant"
    assert result.data["pending_variant_ids"] == ["v1"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["current"] == {}
    assert manifest["variants"][0]["status"] == "candidate"
    assert manifest["variants"][0]["review"]["decision"] == "needs_revision"


def test_annotate_records_new_variant_request(tmp_path: Path):
    path = _init_manifest(tmp_path)
    result = VariantManager().execute(
        {
            "operation": "annotate",
            "manifest_path": str(path),
            "review_payload": {
                "version": "1.0",
                "run_id": "round-1",
                "channel": "default",
                "decision": "REQUEST_NEW_VARIANT",
                "notes": "None of these work for a standalone teaser.",
                "action": {
                    "decision": "REQUEST_NEW_VARIANT",
                    "notes": "None of these work for a standalone teaser.",
                },
            },
        }
    )

    assert result.success, result.error
    assert result.data["review_complete"] is False
    assert result.data["next_operation"] == "add_variant"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    requests = manifest["metadata"]["variant_review_requests"]
    assert requests[0]["decision"] == "request_new_variant"
    assert "standalone teaser" in requests[0]["notes"]


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
