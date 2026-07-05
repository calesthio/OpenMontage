"""Import user-supplied assets into an OpenMontage project workspace."""

from __future__ import annotations

import re
import shutil
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


_MEDIA_TYPES = {
    ".jpg": ("image", "images"),
    ".jpeg": ("image", "images"),
    ".png": ("image", "images"),
    ".webp": ("image", "images"),
    ".bmp": ("image", "images"),
    ".tiff": ("image", "images"),
    ".svg": ("image", "images"),
    ".mp4": ("video", "video"),
    ".mov": ("video", "video"),
    ".webm": ("video", "video"),
    ".avi": ("video", "video"),
    ".mkv": ("video", "video"),
    ".m4v": ("video", "video"),
    ".mp3": ("audio", "audio"),
    ".wav": ("audio", "audio"),
    ".aac": ("audio", "audio"),
    ".flac": ("audio", "audio"),
    ".ogg": ("audio", "audio"),
    ".m4a": ("audio", "audio"),
    ".opus": ("audio", "audio"),
    ".srt": ("subtitle", "."),
    ".vtt": ("subtitle", "."),
    ".ass": ("subtitle", "."),
    ".ttf": ("font", "fonts"),
    ".otf": ("font", "fonts"),
    ".cube": ("lut", "luts"),
}


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "asset"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


class CustomAssetImport(BaseTool):
    name = "custom_asset_import"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "asset_management"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "No external dependencies. Provide existing local file paths."
    capabilities = ["import_user_asset", "asset_manifest_entries", "copy_to_project"]
    supports = {
        "images": True,
        "video": True,
        "audio": True,
        "subtitles": True,
        "fonts": True,
        "luts": True,
    }
    best_for = [
        "bringing user-provided footage, images, audio, and brand files into a project",
        "creator-video pipelines where custom assets should be preferred before generation",
    ]
    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=128,
        vram_mb=0,
        disk_mb=500,
        network_required=False,
    )

    input_schema = {
        "type": "object",
        "required": ["project_dir", "assets"],
        "properties": {
            "project_dir": {
                "type": "string",
                "description": "Project workspace root, for example projects/my-video",
            },
            "assets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path", "scene_id"],
                    "properties": {
                        "path": {"type": "string"},
                        "scene_id": {"type": "string"},
                        "id": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": [
                                "image",
                                "video",
                                "audio",
                                "narration",
                                "music",
                                "sfx",
                                "diagram",
                                "animation",
                                "code_snippet",
                                "subtitle",
                                "font",
                                "lut",
                            ],
                        },
                        "subtype": {"type": "string"},
                        "license": {"type": "string"},
                        "original_url": {"type": "string"},
                        "duration_seconds": {"type": "number"},
                        "resolution": {"type": "string"},
                        "format": {"type": "string"},
                    },
                },
            },
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "asset_manifest": {"type": "object"},
        },
    }
    idempotency_key_fields = ["project_dir", "assets"]
    side_effects = ["copies user files into project asset directories"]
    user_visible_verification = [
        "Confirm imported assets appear under the project assets directory",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        project_dir = Path(inputs["project_dir"])
        assets = inputs.get("assets") or []
        if not isinstance(assets, list) or not assets:
            return ToolResult(success=False, error="assets must be a non-empty list")

        manifest_assets: list[dict[str, Any]] = []
        copied_paths: list[str] = []

        for index, item in enumerate(assets, start=1):
            source = Path(item["path"]).expanduser()
            if not source.is_file():
                return ToolResult(success=False, error=f"Asset file not found: {source}")

            inferred = _MEDIA_TYPES.get(source.suffix.lower())
            if not inferred and not item.get("type"):
                return ToolResult(
                    success=False,
                    error=f"Unsupported asset type for {source.name}",
                )

            asset_type = item.get("type") or inferred[0]
            folder = inferred[1] if inferred else "misc"
            destination_dir = project_dir / "assets" / folder
            destination_dir.mkdir(parents=True, exist_ok=True)

            destination_name = _safe_slug(source.stem) + source.suffix.lower()
            destination = _unique_path(destination_dir / destination_name)
            shutil.copy2(source, destination)
            copied_paths.append(str(destination))

            rel_path = destination.relative_to(project_dir).as_posix()
            asset_id = item.get("id") or f"user-{asset_type}-{index}"
            manifest_asset = {
                "id": asset_id,
                "type": asset_type,
                "path": rel_path,
                "source_tool": self.name,
                "scene_id": item["scene_id"],
                "subtype": item.get("subtype", "user_provided"),
                "provider": "user",
                "cost_usd": 0.0,
                "format": item.get("format", source.suffix.lower().lstrip(".")),
                "generation_summary": f"Imported user-provided asset from {source.name}.",
            }
            for optional_key in (
                "license",
                "original_url",
                "duration_seconds",
                "resolution",
            ):
                if optional_key in item:
                    manifest_asset[optional_key] = item[optional_key]
            manifest_assets.append(manifest_asset)

        manifest = {
            "version": "1.0",
            "assets": manifest_assets,
            "total_cost_usd": 0.0,
            "metadata": {
                "source": self.name,
                "user_asset_count": len(manifest_assets),
            },
        }

        return ToolResult(
            success=True,
            data={"asset_manifest": manifest},
            artifacts=copied_paths,
            cost_usd=0.0,
        )
