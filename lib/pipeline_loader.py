"""Pipeline manifest loader.

Loads and validates pipeline YAML manifests from pipeline_defs/.
"""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DEFS_DIR = Path(__file__).resolve().parent.parent / "pipeline_defs"
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "schemas"
    / "pipelines"
    / "pipeline_manifest.schema.json"
)


class PipelineSemanticError(ValueError):
    """Raised when a schema-valid pipeline contains contradictory references."""

    def __init__(self, pipeline_name: str, errors: list[str]) -> None:
        self.pipeline_name = pipeline_name
        self.errors = tuple(errors)
        details = "\n".join(f"- {error}" for error in errors)
        super().__init__(
            f"Pipeline {pipeline_name!r} failed semantic validation:\n{details}"
        )

@lru_cache(maxsize=1)
def _load_manifest_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=64)
def _load_pipeline_cached(name: str, defs_dir_key: str) -> dict[str, Any]:
    """Cached manifest load. Treat the returned dict as READ-ONLY."""
    return load_pipeline(name, Path(defs_dir_key) if defs_dir_key else None)


def load_pipeline_readonly(name: str, defs_dir: Optional[Path] = None) -> dict[str, Any]:
    """Load a manifest through a cache. The result MUST NOT be mutated.

    Manifests are immutable within a run; hot paths (gate checks on every
    checkpoint write, board state derivation) should use this instead of
    re-parsing YAML + re-validating the schema each call.
    """
    return _load_pipeline_cached(name, str(defs_dir) if defs_dir else "")


def load_pipeline(name: str, defs_dir: Optional[Path] = None) -> dict[str, Any]:
    """Load and validate a pipeline manifest by name.

    Args:
        name: Pipeline name (without .yaml extension).
        defs_dir: Override directory for pipeline definitions.

    Returns:
        Validated pipeline manifest dict.
    """
    defs_dir = defs_dir or PIPELINE_DEFS_DIR
    path = defs_dir / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Pipeline manifest not found: {path}")

    with open(path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    schema = _load_manifest_schema()
    jsonschema.validate(instance=manifest, schema=schema)
    _validate_pipeline_semantics(
        manifest,
        repo_root=defs_dir.parent if defs_dir != PIPELINE_DEFS_DIR else REPO_ROOT,
    )

    return manifest


def _validate_pipeline_semantics(
    manifest: dict[str, Any],
    *,
    repo_root: Path,
) -> None:
    """Validate cross-field invariants that JSON Schema cannot express.

    The pipeline loader is the seam for manifest correctness, so callers get
    structural and semantic validation from the same unchanged interface.
    """
    errors: list[str] = []
    stages = manifest["stages"]
    stage_names = [stage["name"] for stage in stages]

    for stage_name, count in sorted(Counter(stage_names).items()):
        if count < 2:
            continue
        errors.append(f"duplicate stage name: {stage_name}")

    artifact_owners: dict[str, list[tuple[int, str]]] = {}
    for index, stage in enumerate(stages):
        sub_stage_names = [sub_stage["name"] for sub_stage in stage.get("sub_stages", [])]
        for sub_stage_name, count in sorted(Counter(sub_stage_names).items()):
            if count < 2:
                continue
            errors.append(
                f"stage {stage['name']!r} has duplicate sub-stage name: {sub_stage_name}"
            )

        for artifact in stage.get("produces", []):
            artifact_owners.setdefault(artifact, []).append((index, stage["name"]))

    for artifact, owners in sorted(artifact_owners.items()):
        if len(owners) > 1:
            owner_names = ", ".join(owner_name for _, owner_name in owners)
            errors.append(
                f"artifact {artifact!r} has multiple producing stages: {owner_names}"
            )

    for index, stage in enumerate(stages):
        for artifact in stage.get("required_artifacts_in", []):
            invalid_owners = [
                owner_name
                for owner_index, owner_name in artifact_owners.get(artifact, [])
                if owner_index >= index
            ]
            if invalid_owners:
                errors.append(
                    f"stage {stage['name']!r} requires artifact {artifact!r} before "
                    f"its producer: {', '.join(invalid_owners)}"
                )

        tools_available = set(stage.get("tools_available", []))
        for tool_field in ("required_tools", "optional_tools"):
            missing_tools = sorted(set(stage.get(tool_field, [])) - tools_available)
            if missing_tools:
                errors.append(
                    f"stage {stage['name']!r} lists {', '.join(missing_tools)} in "
                    f"{tool_field} but not tools_available"
                )

    declared_skills = set(manifest.get("required_skills", []))
    referenced_skills = {
        stage["skill"] for stage in stages if stage.get("skill")
    }
    orchestration_skill = manifest.get("orchestration", {}).get("skill")
    if orchestration_skill:
        referenced_skills.add(orchestration_skill)

    for skill in sorted(referenced_skills - declared_skills):
        errors.append(f"referenced skill {skill!r} is not listed in required_skills")

    for skill in sorted(declared_skills | referenced_skills):
        skill_path = Path(skill)
        if skill_path.suffix != ".md":
            skill_path = skill_path.with_suffix(".md")
        if not (repo_root / "skills" / skill_path).is_file():
            errors.append(f"skill path does not exist: skills/{skill_path.as_posix()}")

    artifact_names = {
        artifact
        for stage in stages
        for field in ("required_artifacts_in", "optional_artifacts_in", "produces")
        for artifact in stage.get(field, [])
    }
    for artifact in sorted(artifact_names):
        schema_path = repo_root / "schemas" / "artifacts" / f"{artifact}.schema.json"
        if not schema_path.is_file():
            errors.append(
                f"artifact {artifact!r} has no schema at "
                f"schemas/artifacts/{artifact}.schema.json"
            )

    if errors:
        raise PipelineSemanticError(manifest.get("name", "unknown"), errors)


def list_pipelines(defs_dir: Optional[Path] = None) -> list[str]:
    """List all available pipeline manifest names."""
    defs_dir = defs_dir or PIPELINE_DEFS_DIR
    return [p.stem for p in defs_dir.glob("*.yaml")]


def _condition_is_active(condition: Optional[str], context: Optional[dict[str, Any]]) -> bool:
    """Evaluate a simple manifest condition against runtime context."""
    if not condition:
        return True
    if not context:
        return False
    return bool(context.get(condition))


def get_reference_input_config(manifest: dict) -> dict[str, Any]:
    """Return reference-input configuration, defaulting to disabled."""
    return manifest.get("reference_input", {}) or {}


def pipeline_supports_reference_input(manifest: dict) -> bool:
    """Whether the manifest declares support for reference-video input."""
    return bool(get_reference_input_config(manifest).get("supported", False))


def get_stage_sub_stages(
    manifest: dict,
    stage_name: str,
    *,
    context: Optional[dict[str, Any]] = None,
    include_inactive: bool = True,
) -> list[dict[str, Any]]:
    """Return sub-stage definitions for a stage.

    By default this returns all declared sub-stages so agents can inspect the
    full workflow shape. Pass ``include_inactive=False`` with context to filter
    to active sub-stages only.
    """
    for stage in manifest["stages"]:
        if stage["name"] != stage_name:
            continue
        sub_stages = list(stage.get("sub_stages", []))
        if include_inactive:
            return sub_stages
        return [
            sub_stage
            for sub_stage in sub_stages
            if _condition_is_active(sub_stage.get("condition"), context)
        ]
    return []


def get_stage_order(
    manifest: dict,
    *,
    include_sub_stages: bool = False,
    context: Optional[dict[str, Any]] = None,
) -> list[str]:
    """Extract the ordered list of stage names from a manifest.

    ``include_sub_stages=True`` exposes declarative sample/preview units to the
    agent without turning them into mandatory checkpoint stages. Sub-stages are
    emitted as ``<stage>.<sub_stage>``.
    """
    order: list[str] = []
    for stage in manifest["stages"]:
        order.append(stage["name"])
        if not include_sub_stages:
            continue
        for sub_stage in get_stage_sub_stages(
            manifest,
            stage["name"],
            context=context,
            include_inactive=context is None,
        ):
            order.append(f"{stage['name']}.{sub_stage['name']}")
    return order


def get_required_tools(manifest: dict) -> set[str]:
    """Collect tools across stages, sub-stages, and reference-input analysis."""
    tools: set[str] = set()
    for stage in manifest["stages"]:
        tools.update(stage.get("preferred_tools", []))
        tools.update(stage.get("fallback_tools", []))
        tools.update(stage.get("tools_available", []))
        for sub_stage in stage.get("sub_stages", []):
            tools.update(sub_stage.get("tools_available", []))
    tools.update(get_reference_input_config(manifest).get("analysis_tools", []))
    return tools


def get_stage_skill(manifest: dict, stage_name: str) -> Optional[str]:
    """Get the skill path for an instruction-driven stage."""
    for stage in manifest["stages"]:
        if stage["name"] == stage_name:
            return stage.get("skill")
    return None


def get_stage_human_approval_default(manifest: dict, stage_name: str) -> Optional[bool]:
    """Whether a stage gates on human approval. None if the stage isn't declared.

    This is the single lookup used by gate enforcement (lib/checkpoint.py)
    and the Backlot board — keep them reading the same field the same way.
    """
    for stage in manifest["stages"]:
        if stage["name"] == stage_name:
            return bool(stage.get("human_approval_default", False))
    return None


def get_stage_review_focus(manifest: dict, stage_name: str) -> list[str]:
    """Get the review focus items for a stage."""
    for stage in manifest["stages"]:
        if stage["name"] == stage_name:
            return stage.get("review_focus", [])
    return []


# ---------------------------------------------------------------------------
# Capability-Extension Enforcement
# ---------------------------------------------------------------------------

class ExtensionNotPermitted(PermissionError):
    """Raised when a capability extension is used but not permitted by the pipeline."""


def check_extension_permitted(
    manifest: dict,
    extension_type: str,
) -> None:
    """Enforce that a capability extension is permitted by the pipeline manifest.

    Args:
        manifest: Loaded pipeline manifest dict.
        extension_type: One of 'custom_scripts', 'custom_playbooks',
                        'custom_skills', 'custom_tools'.

    Raises:
        ExtensionNotPermitted: If the extension is not allowed.
    """
    valid_extensions = {"custom_scripts", "custom_playbooks", "custom_skills", "custom_tools"}
    if extension_type not in valid_extensions:
        raise ValueError(
            f"Unknown extension type {extension_type!r}. "
            f"Valid types: {sorted(valid_extensions)}"
        )

    extensions = manifest.get("extensions", {})
    if not extensions.get(extension_type, False):
        raise ExtensionNotPermitted(
            f"Pipeline {manifest.get('name', 'unknown')!r} does not permit "
            f"{extension_type}. Set extensions.{extension_type}: true in the "
            f"pipeline manifest to allow this."
        )


def get_permitted_extensions(manifest: dict) -> dict[str, bool]:
    """Return the extension permission flags for a pipeline."""
    defaults = {
        "custom_scripts": False,
        "custom_playbooks": False,
        "custom_skills": False,
        "custom_tools": False,
    }
    extensions = manifest.get("extensions", {})
    return {k: extensions.get(k, v) for k, v in defaults.items()}
