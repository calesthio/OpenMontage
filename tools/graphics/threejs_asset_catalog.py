"""Licensed local GLTF/PBR catalog ingestion for Three.js worlds.

This module intentionally handles acquisition and provenance only. Creative
selection and placement remain agent decisions expressed through world_spec.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
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


CATALOGS: dict[str, dict[str, Any]] = {
    "kenney-nature-kit": {
        "title": "Kenney Nature Kit",
        "source_url": "https://kenney.nl/assets/nature-kit",
        "download_url": "https://kenney.nl/media/pages/assets/nature-kit/37ac38a37b-1677698939/kenney_nature-kit.zip",
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "tags": ["nature", "tree", "rock", "foliage"],
    },
    "kenney-fantasy-town-kit": {
        "title": "Kenney Fantasy Town Kit 2.0",
        "source_url": "https://kenney.nl/assets/fantasy-town-kit",
        "download_url": "https://kenney.nl/media/pages/assets/fantasy-town-kit/efe948d309-1754222374/kenney_fantasy-town-kit_2.0.zip",
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "tags": ["medieval", "village", "building", "wall", "prop"],
    },
    "kenney-survival-kit": {
        "title": "Kenney Survival Kit 2.0",
        "source_url": "https://kenney.nl/assets/survival-kit",
        "download_url": "https://kenney.nl/media/pages/assets/survival-kit/4065a8185b-1712149243/kenney_survival-kit.zip",
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "tags": ["survival", "camp", "nature", "prop"],
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "OpenMontage/threejs-asset-catalog"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


class ThreeJSAssetCatalog(BaseTool):
    """Install inspectable, rights-safe world asset catalogs."""

    name = "threejs_asset_catalog"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "3d_asset_acquisition"
    provider = "multi"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.HYBRID
    dependencies: list[str] = []
    install_instructions = "Network access for install; no API key. Bundled catalogs are CC0."
    agent_skills = ["threejs-world-generation", "threejs-loaders", "threejs-materials", "threejs-textures"]
    best_for = [
        "Installing rights-safe GLTF/GLB libraries for detailed Three.js worlds",
        "Recording model-level provenance before asset-gate review",
    ]
    not_good_for = [
        "Generating a unique mesh from text or an image",
        "Downloading assets whose license is absent or incompatible",
    ]
    capabilities = ["cc0_catalog_install", "gltf_inventory", "asset_provenance"]
    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {"type": "string", "enum": ["list", "install", "inspect"]},
            "catalog_id": {"type": "string"},
            "output_path": {"type": "string"},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"artifact": "3d_world"}
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=1000, network_required=True)
    idempotency_key_fields = ["operation", "catalog_id", "output_path"]
    side_effects = ["downloads and extracts a licensed asset archive for install operations"]
    fallback_tools: list[str] = []
    user_visible_verification = ["Review catalog-manifest.json and the model inventory before production use"]

    def execute(self, params: dict[str, Any]) -> ToolResult:
        operation = params.get("operation")
        if operation == "list":
            return ToolResult(success=True, data={"catalogs": CATALOGS})

        catalog_id = str(params.get("catalog_id") or "")
        if catalog_id not in CATALOGS:
            return ToolResult(success=False, error=f"Unknown catalog_id {catalog_id!r}; choose one of {sorted(CATALOGS)}")

        output_path = params.get("output_path")
        if not output_path:
            return ToolResult(success=False, error="output_path is required for install and inspect")
        root = Path(output_path).expanduser().resolve()
        manifest_path = root / "catalog-manifest.json"

        if operation == "inspect":
            if not manifest_path.exists():
                return ToolResult(success=False, error=f"No installed catalog manifest at {manifest_path}")
            return ToolResult(success=True, data=json.loads(manifest_path.read_text(encoding="utf-8")))

        if operation != "install":
            return ToolResult(success=False, error=f"Unsupported operation {operation!r}")

        source = CATALOGS[catalog_id]
        root.mkdir(parents=True, exist_ok=True)
        archive = root / f"{catalog_id}.zip"
        if not archive.exists():
            _download(source["download_url"], archive)
        extract_root = root / "source"
        if not extract_root.exists():
            extract_root.mkdir(parents=True)
            with zipfile.ZipFile(archive) as package:
                package.extractall(extract_root)

        models = sorted(
            path for path in extract_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".gltf", ".glb"}
        )
        textures = sorted(
            path for path in extract_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
        manifest = {
            "version": "1.0",
            "catalog_id": catalog_id,
            **source,
            "archive_sha256": _sha256(archive),
            "model_count": len(models),
            "texture_count": len(textures),
            "models": [
                {
                    "id": path.stem.lower().replace(" ", "-"),
                    "path": path.relative_to(root).as_posix(),
                    "format": path.suffix.lower().lstrip("."),
                }
                for path in models
            ],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return ToolResult(success=True, data=manifest, artifacts=[str(manifest_path)])
