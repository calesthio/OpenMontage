"""Cross-project media library (roadmap 3.3).

asset_manifest was already the perfect library index — id/prompt/model/cost/
provenance per asset — written on every run and never aggregated. This
read-only router aggregates every project's manifest into one searchable
list. Substring search over prompt/model/project covers the base retrieval
loop; embedding search (clip_embedder) can slot in behind the same endpoint
later without changing the contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter

OM_ROOT = Path(__file__).parent.parent.parent.parent

router = APIRouter()


def _iter_manifest_assets() -> list[dict[str, Any]]:
    projects_dir = OM_ROOT / "projects"
    results: list[dict[str, Any]] = []
    if not projects_dir.is_dir():
        return results
    for manifest_path in sorted(projects_dir.glob("*/artifacts/asset_manifest.json")):
        project = manifest_path.parent.parent.name
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for a in manifest.get("assets", []) or []:
            if not isinstance(a, dict):
                continue
            path = str(a.get("path") or "")
            # Best-effort /media URL (same convention as tool_bridge's
            # asset_ready media_url): only project-workspace files are
            # servable.
            media_url = None
            norm = path.replace("\\", "/")
            marker = f"projects/{project}/"
            if marker in norm:
                media_url = f"/media/{project}/{norm.split(marker, 1)[1]}"
            elif norm and not norm.startswith("/"):
                media_url = f"/media/{project}/{norm}"
            results.append({
                "project": project,
                "id": a.get("id"),
                "type": a.get("type"),
                "path": path,
                "media_url": media_url,
                "prompt": a.get("prompt"),
                "model": a.get("model"),
                "provider": a.get("provider"),
                "cost_usd": a.get("cost_usd"),
                "scene_id": a.get("scene_id"),
                "license": a.get("license"),
                "quality_score": a.get("quality_score"),
            })
    return results


@router.get("/assets")
async def list_library_assets(
    q: Optional[str] = None,
    model: Optional[str] = None,
    project: Optional[str] = None,
    type: Optional[str] = None,   # noqa: A002 - FastAPI query param name
    limit: int = 200,
):
    assets = _iter_manifest_assets()
    if project:
        assets = [a for a in assets if a["project"] == project]
    if model:
        assets = [a for a in assets if (a.get("model") or "") == model]
    if type:
        assets = [a for a in assets if type in (a.get("type") or "")]
    if q:
        needle = q.lower()
        assets = [
            a for a in assets
            if needle in (a.get("prompt") or "").lower()
            or needle in (a.get("model") or "").lower()
            or needle in a["project"].lower()
        ]
    return {
        "total": len(assets),
        "assets": assets[: max(1, min(limit, 1000))],
        "projects": sorted({a["project"] for a in _iter_manifest_assets()}),
    }
