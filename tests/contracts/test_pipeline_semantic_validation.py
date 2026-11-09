"""Semantic contracts for declarative pipeline manifests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from lib.pipeline_loader import PipelineSemanticError, list_pipelines, load_pipeline


def _write_pipeline_repo(
    tmp_path: Path,
    *,
    stages: list[dict],
    required_skills: list[str] | None = None,
) -> Path:
    """Create the smallest repository layout accepted by load_pipeline."""
    required_skills = required_skills or ["pipelines/test/director"]
    defs_dir = tmp_path / "pipeline_defs"
    defs_dir.mkdir()

    for skill in required_skills:
        skill_path = tmp_path / "skills" / Path(skill).with_suffix(".md")
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text("# Test skill\n", encoding="utf-8")

    artifact_names = {
        artifact
        for stage in stages
        for field in ("required_artifacts_in", "optional_artifacts_in", "produces")
        for artifact in stage.get(field, [])
    }
    schema_dir = tmp_path / "schemas" / "artifacts"
    schema_dir.mkdir(parents=True)
    for artifact in artifact_names:
        (schema_dir / f"{artifact}.schema.json").write_text(
            json.dumps({"type": "object"}),
            encoding="utf-8",
        )

    manifest = {
        "name": "test-pipeline",
        "version": "1.0",
        "required_skills": required_skills,
        "stages": stages,
    }
    (defs_dir / "test-pipeline.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )
    return defs_dir


def _valid_stages() -> list[dict]:
    return [
        {
            "name": "script",
            "skill": "pipelines/test/director",
            "produces": ["script"],
            "required_tools": ["writer"],
            "tools_available": ["writer"],
        },
        {
            "name": "compose",
            "skill": "pipelines/test/director",
            "required_artifacts_in": ["script"],
            "produces": ["render_report"],
            "tools_available": [],
        },
    ]


def test_all_repository_pipeline_manifests_are_semantically_valid() -> None:
    for pipeline_name in list_pipelines():
        load_pipeline(pipeline_name)


def test_load_pipeline_accepts_consistent_cross_references(tmp_path: Path) -> None:
    defs_dir = _write_pipeline_repo(tmp_path, stages=_valid_stages())

    manifest = load_pipeline("test-pipeline", defs_dir)

    assert manifest["name"] == "test-pipeline"


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (
            lambda stages: stages.append(
                {
                    "name": "script",
                    "skill": "pipelines/test/director",
                    "tools_available": [],
                }
            ),
            "duplicate stage name: script",
        ),
        (
            lambda stages: stages[1]["produces"].append("script"),
            "artifact 'script' has multiple producing stages",
        ),
        (
            lambda stages: stages[0].update(
                {"required_artifacts_in": ["render_report"]}
            ),
            "requires artifact 'render_report' before its producer",
        ),
        (
            lambda stages: stages[0]["required_tools"].append("missing_tool"),
            "missing_tool in required_tools but not tools_available",
        ),
    ],
)
def test_load_pipeline_rejects_cross_field_conflicts(
    tmp_path: Path,
    mutate,
    expected_error: str,
) -> None:
    stages = _valid_stages()
    mutate(stages)
    defs_dir = _write_pipeline_repo(tmp_path, stages=stages)

    with pytest.raises(PipelineSemanticError, match=expected_error):
        load_pipeline("test-pipeline", defs_dir)


def test_load_pipeline_rejects_undeclared_stage_skill(tmp_path: Path) -> None:
    stages = _valid_stages()
    stages[1]["skill"] = "pipelines/test/compose-director"
    defs_dir = _write_pipeline_repo(tmp_path, stages=stages)
    compose_skill = tmp_path / "skills" / "pipelines" / "test" / "compose-director.md"
    compose_skill.write_text("# Compose skill\n", encoding="utf-8")

    with pytest.raises(
        PipelineSemanticError,
        match="referenced skill 'pipelines/test/compose-director' is not listed",
    ):
        load_pipeline("test-pipeline", defs_dir)


def test_load_pipeline_rejects_missing_skill_file(tmp_path: Path) -> None:
    defs_dir = _write_pipeline_repo(tmp_path, stages=_valid_stages())
    (tmp_path / "skills" / "pipelines" / "test" / "director.md").unlink()

    with pytest.raises(PipelineSemanticError, match="skill path does not exist"):
        load_pipeline("test-pipeline", defs_dir)


def test_load_pipeline_rejects_missing_artifact_schema(tmp_path: Path) -> None:
    defs_dir = _write_pipeline_repo(tmp_path, stages=_valid_stages())
    (tmp_path / "schemas" / "artifacts" / "script.schema.json").unlink()

    with pytest.raises(PipelineSemanticError, match="artifact 'script' has no schema"):
        load_pipeline("test-pipeline", defs_dir)
