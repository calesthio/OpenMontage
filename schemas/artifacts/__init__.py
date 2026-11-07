"""Artifact schema loading and validation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from .migrations import migrate_artifact
from .validation import (
    ArtifactSemanticValidationError,
    validate_artifact_handoffs,
    validate_artifact_semantics,
)

SCHEMA_DIR = Path(__file__).parent
VERSIONED_SCHEMA_DIR = SCHEMA_DIR / "versions"
DEFAULT_SCHEMA_VERSION = "1.0"

ARTIFACT_NAMES = [
    "research_brief",
    "proposal_packet",
    "brief",
    "script",
    "character_design",
    "rig_plan",
    "pose_library",
    "scene_plan",
    "action_timeline",
    "asset_manifest",
    "edit_decisions",
    "render_report",
    "publish_log",
    "review",
    "cost_log",
    "decision_log",
    "source_media_review",
    "final_review",
    "character_qa_report",
    "video_analysis_brief",
    "video_analysis_bundle",
]


def _schema_path(name: str, version: str | None = None) -> Path:
    resolved_version = version or DEFAULT_SCHEMA_VERSION
    if resolved_version == DEFAULT_SCHEMA_VERSION:
        return SCHEMA_DIR / f"{name}.schema.json"
    return VERSIONED_SCHEMA_DIR / name / f"{resolved_version}.schema.json"


def load_schema(name: str, version: str | None = None) -> dict[str, Any]:
    """Load an artifact schema, dispatching by explicit artifact version."""
    path = _schema_path(name, version)
    if not path.exists():
        raise FileNotFoundError(
            f"Schema not found for artifact {name!r} version {version or DEFAULT_SCHEMA_VERSION!r}: {path}"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_artifact(name: str, data: dict[str, Any]) -> None:
    """Validate an artifact's shape and version-specific semantic invariants."""
    if not isinstance(data, dict):
        raise TypeError(f"Artifact {name!r} must be a JSON object")
    schema = load_schema(name, str(data.get("version", DEFAULT_SCHEMA_VERSION)))
    jsonschema.validate(instance=data, schema=schema)
    validate_artifact_semantics(name, data)


def list_schemas() -> list[str]:
    """List all base artifact schema names."""
    return sorted(p.stem.replace(".schema", "") for p in SCHEMA_DIR.glob("*.schema.json"))


def list_schema_versions(name: str) -> list[str]:
    """Return available versions for an artifact, including the legacy base."""
    versions = [DEFAULT_SCHEMA_VERSION]
    version_dir = VERSIONED_SCHEMA_DIR / name
    if version_dir.exists():
        versions.extend(
            p.stem.replace(".schema", "")
            for p in version_dir.glob("*.schema.json")
        )
    return sorted(set(versions), key=lambda value: tuple(int(part) for part in value.split(".")))
