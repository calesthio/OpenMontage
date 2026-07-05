"""Create reference-video projects and import local reference sources."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROJECTS_ROOT = ROOT / "projects"
SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug.lower() or "reference-project"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _project_dirs(project_dir: Path) -> list[Path]:
    return [
        project_dir / "artifacts",
        project_dir / "artifacts" / "reference-source",
        project_dir / "source",
        project_dir / "assets" / "images",
        project_dir / "assets" / "video",
        project_dir / "assets" / "audio",
        project_dir / "renders",
        project_dir / "deliveries",
    ]


def create_reference_project(
    *,
    project_name: str,
    projects_root: str | Path | None = None,
) -> dict[str, Any]:
    name = project_name.strip()
    if not name:
        raise ValueError("project_name is required")

    root = Path(projects_root or DEFAULT_PROJECTS_ROOT).expanduser().resolve()
    project_slug = _safe_slug(name)
    project_dir = root / project_slug
    for directory in _project_dirs(project_dir):
        directory.mkdir(parents=True, exist_ok=True)

    metadata = {
        "version": "1.0",
        "project_name": name,
        "project_slug": project_slug,
        "pipeline": "reference-video-analysis",
        "status": "created",
    }
    metadata_path = project_dir / "project.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "version": "1.0",
        "status": "created",
        "project_name": name,
        "project_slug": project_slug,
        "project_dir": str(project_dir),
        "metadata_path": str(metadata_path),
        "created_dirs": [str(directory) for directory in _project_dirs(project_dir)],
        "next_step": "import_reference_source",
    }


def import_reference_source(
    *,
    project_dir: str | Path,
    source_path: str | Path,
) -> dict[str, Any]:
    project_path = Path(project_dir).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"source_path does not exist or is not a file: {source}")
    if source.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_VIDEO_SUFFIXES))
        raise ValueError(f"source_path must be a supported video file: {supported}")

    for directory in _project_dirs(project_path):
        directory.mkdir(parents=True, exist_ok=True)

    destination = _unique_path(project_path / "source" / (_safe_slug(source.stem) + source.suffix.lower()))
    if source != destination.resolve():
        shutil.copy2(source, destination)

    artifact_dir = project_path / "artifacts" / "reference-source"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{_safe_slug(destination.stem)}-source-import.json"
    payload = {
        "version": "1.0",
        "status": "imported",
        "source_type": "reference_video",
        "original_path": str(source),
        "local_video_path": str(destination),
        "project_dir": str(project_path),
        "next_step": "analyze_reference",
    }
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        **payload,
        "artifact_path": str(artifact_path),
    }
